"""Camera platform for the Home Connect Alt integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import ClientResponseError
from home_connect_async import Appliance, Events, HomeConnect
from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .api import (
    AsyncMobilePrivateApi,
    PrivateCameraAuthRequiredError,
    PrivateSnapshot,
)
from .common import Configuration, EntityBase, EntityManager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The private backend only exposes still snapshots. Polling more frequently than
# this adds noise without improving the user-visible refresh behavior.
MIN_IMAGE_INTERVAL = 5
PLACEHOLDER_IMAGE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<rect width="1280" height="720" fill="#181818"/>
<rect x="70" y="70" width="1140" height="580" rx="42" fill="#242424" stroke="#d7aa58" stroke-width="6"/>
<text x="640" y="250" fill="#f8f1df" font-family="Verdana, sans-serif" font-size="52" text-anchor="middle">Home Connect Oven Camera</text>
<text x="640" y="340" fill="#f8f1df" font-family="Verdana, sans-serif" font-size="34" text-anchor="middle">No private snapshot is available yet.</text>
<text x="640" y="405" fill="#c9c1b0" font-family="Verdana, sans-serif" font-size="26" text-anchor="middle">Run the private camera auth services to enable oven snapshots.</text>
</svg>"""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Connect camera entities."""
    entry_conf: Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect: HomeConnect = entry_conf["homeconnect"]
    private_api: AsyncMobilePrivateApi = entry_conf["private_api"]
    entity_manager = EntityManager(async_add_entities, "Camera")

    def add_appliance(appliance: Appliance) -> None:
        if appliance.type.lower() != "oven":
            return
        entity_manager.add(
            HomeConnectCamera(appliance, "camera", entry_conf, private_api)
        )
        entity_manager.register()

    def remove_appliance(appliance: Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class HomeConnectCamera(EntityBase, Camera):
    """A camera entity backed by the private Home Connect oven snapshot feed."""

    def __init__(
        self,
        appliance: Appliance,
        key: str,
        conf: Configuration,
        private_api: AsyncMobilePrivateApi,
    ) -> None:
        EntityBase.__init__(self, appliance, key, conf)
        self._content_type = "image/svg+xml"
        Camera.__init__(self)
        self._private_api = private_api
        self._downloaded_identifier: str | None = None
        self._image: bytes | None = None
        self._last_error: str | None = None
        self._last_fetch: float = 0.0
        self._last_snapshot_id: str | None = None
        self._last_snapshot_status: int | None = None
        self._last_snapshot_timestamp_ms: int | None = None
        self._private_ha_id: str | None = None
        self._refreshing = False

    @property
    def unique_id(self) -> str:
        return f"{self.safe_haId}_camera"

    @property
    def name_ext(self) -> str:
        return "Camera"

    @property
    def icon(self) -> str:
        return "mdi:camera"

    @property
    def available(self) -> bool:
        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "downloaded_identifier": self._downloaded_identifier,
            "last_error": self._last_error,
            "last_snapshot_id": self._last_snapshot_id,
            "last_snapshot_status": self._last_snapshot_status,
            "last_snapshot_timestamp_ms": self._last_snapshot_timestamp_ms,
            "private_ha_id": self._private_ha_id,
            "private_auth_configured": self._private_api.is_configured,
        }

    @property
    def is_streaming(self) -> bool:
        return False

    @property
    def content_type(self) -> str:
        return self._content_type

    @content_type.setter
    def content_type(self, value: str) -> None:
        self._content_type = value

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to Home Assistant."""
        await super().async_added_to_hass()
        self.hass.async_create_task(self._async_refresh_latest_snapshot())

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the most recent oven snapshot."""
        if (
            self._appliance.connected
            and (time.monotonic() - self._last_fetch) >= MIN_IMAGE_INTERVAL
        ):
            await self._async_refresh_latest_snapshot()
        return self._image or PLACEHOLDER_IMAGE

    async def _async_refresh_latest_snapshot(self) -> None:
        """Refresh the private snapshot feed and update the cached image if needed."""
        if self._refreshing or not self._appliance.connected:
            return

        self._refreshing = True
        try:
            snapshot = await self._private_api.async_get_latest_snapshot(
                self._appliance.haId,
                self._appliance.type,
            )
            self._last_snapshot_status = 200
            self._last_fetch = time.monotonic()

            if snapshot is None:
                self._last_error = "Private media backend returned no snapshot items"
                self.async_write_ha_state()
                return

            self._private_ha_id = snapshot.private_ha_id
            self._last_snapshot_id = snapshot.identifier
            self._last_snapshot_timestamp_ms = snapshot.timestamp_ms

            if snapshot.identifier == self._downloaded_identifier and self._image:
                self._last_error = None
                self.async_write_ha_state()
                return

            image_bytes, content_type, downloaded_identifier = (
                await self._async_download_snapshot(snapshot)
            )
            self._image = image_bytes
            self._content_type = content_type
            self._downloaded_identifier = downloaded_identifier
            self._last_error = None
            self.async_write_ha_state()
        except PrivateCameraAuthRequiredError:
            self._last_error = (
                "Private camera auth is not configured. Run the auth services first."
            )
            self.async_write_ha_state()
        except ClientResponseError as err:
            self._last_snapshot_status = err.status
            self._last_error = f"Private media request failed with {err.status}"
            _LOGGER.debug(
                "Private media request failed for %s",
                self._appliance.name,
                exc_info=True,
            )
            self.async_write_ha_state()
        except Exception:
            self._last_error = "Error downloading private oven snapshot"
            _LOGGER.debug(
                "Error downloading private oven snapshot for %s",
                self._appliance.name,
                exc_info=True,
            )
            self.async_write_ha_state()
        finally:
            self._refreshing = False

    async def _async_download_snapshot(
        self,
        snapshot: PrivateSnapshot,
    ) -> tuple[bytes, str, str]:
        """Download the full-size snapshot and fall back to the preview when needed."""
        try:
            image_bytes, content_type = await self._private_api.async_download_media(
                snapshot.private_ha_id,
                snapshot.identifier,
            )
            return (
                image_bytes,
                _guess_content_type(image_bytes, content_type),
                snapshot.identifier,
            )
        except ClientResponseError:
            if not snapshot.preview_identifier:
                raise

        image_bytes, content_type = await self._private_api.async_download_media(
            snapshot.private_ha_id,
            snapshot.preview_identifier,
        )
        return (
            image_bytes,
            _guess_content_type(image_bytes, content_type),
            snapshot.preview_identifier,
        )

    async def async_on_update(self, appliance: Appliance, key: str, value: Any) -> None:
        if (
            appliance.connected
            and (time.monotonic() - self._last_fetch) >= MIN_IMAGE_INTERVAL
        ):
            self.hass.async_create_task(self._async_refresh_latest_snapshot())
            return
        self.async_write_ha_state()


def _guess_content_type(image_bytes: bytes, response_content_type: str) -> str:
    """Prefer signature-based detection so HA renders octet-stream payloads correctly."""
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return response_content_type or "application/octet-stream"
