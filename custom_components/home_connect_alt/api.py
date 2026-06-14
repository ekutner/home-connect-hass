"""API for Home Connect New bound to Home Assistant OAuth."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import home_connect_async
from aiohttp import ClientResponse, ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.storage import Store

from .const import (
    ENDPOINT_AUTHORIZE,
    ENDPOINT_TOKEN,
    PRIVATE_API_HOST,
    PRIVATE_CAMERA_AUTH_STORAGE_KEY,
    PRIVATE_CAMERA_AUTH_STORAGE_VERSION,
    PRIVATE_CAMERA_CLIENT_ID,
    PRIVATE_CAMERA_REDIRECT_URI,
    PRIVATE_CAMERA_SCOPES,
)

# TODO the following two API examples are based on our suggested best practices
# for libraries using OAuth2 with requests or aiohttp. Delete the one you won't use.
# For more info see the docs at https://developers.home-assistant.io/docs/api_lib_auth/#oauth2.


class AsyncConfigEntryAuth(home_connect_async.AbstractAuth):
    """Provide Home Connect New authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        host: str,
    ) -> None:
        """Initialize Home Connect New auth."""
        super().__init__(websession, host)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class PrivateCameraAuthError(RuntimeError):
    """Base exception for private camera authentication problems."""


class PrivateCameraAuthRequiredError(PrivateCameraAuthError):
    """Raised when the user has not configured private camera auth yet."""


@dataclass(slots=True)
class PrivateSnapshot:
    """Snapshot metadata returned by the private Home Connect media backend."""

    appliance_type: str
    content_type: str
    hash_value: str | None
    identifier: str
    media_type: str
    object_detection_identifier: str | None
    preview_identifier: str | None
    private_ha_id: str
    timestamp_ms: int
    upload_status: str | None
    metadata: dict[str, Any]


class MobilePrivateAuth:
    """Manage PKCE OAuth and token persistence for the private mobile API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        websession: ClientSession,
    ) -> None:
        self._entry_id = entry_id
        self._websession = websession
        self._store = Store(
            hass,
            version=PRIVATE_CAMERA_AUTH_STORAGE_VERSION,
            key=f"{PRIVATE_CAMERA_AUTH_STORAGE_KEY}_{entry_id}",
            private=True,
        )
        self._data: dict[str, Any] = {}

    async def async_initialize(self) -> None:
        """Load persisted auth data into memory."""
        self._data = await self._store.async_load() or {}

    @property
    def is_configured(self) -> bool:
        """Return whether a refresh token is available."""
        token = self._data.get("token") or {}
        return bool(token.get("refresh_token"))

    async def async_build_authorize_url(self) -> str:
        """Create a PKCE authorize URL and persist the verifier for the callback step."""
        verifier = _generate_code_verifier()
        challenge = _generate_code_challenge(verifier)
        state = f"hcapp-{secrets.token_urlsafe(18)}"

        self._data["pkce"] = {
            "code_verifier": verifier,
            "created_at": int(time.time()),
            "state": state,
        }
        await self._async_save()

        params = {
            "client_id": PRIVATE_CAMERA_CLIENT_ID,
            "redirect_uri": PRIVATE_CAMERA_REDIRECT_URI,
            "response_type": "code",
            "scope": PRIVATE_CAMERA_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"https://api.home-connect.com{ENDPOINT_AUTHORIZE}?{urlencode(params)}"

    async def async_exchange_callback_url(self, callback_url: str) -> None:
        """Exchange the QR redirect callback into a persisted mobile-app token."""
        code, returned_state = _extract_code_and_state(callback_url)
        pkce = self._data.get("pkce") or {}
        if not pkce.get("code_verifier") or not pkce.get("state"):
            raise PrivateCameraAuthError(
                "No pending private camera auth session found. Start auth first."
            )
        if returned_state and returned_state != pkce["state"]:
            raise PrivateCameraAuthError("Private camera auth state mismatch")

        payload = await self._async_form_post(
            "https://api.home-connect.com" + ENDPOINT_TOKEN,
            {
                "grant_type": "authorization_code",
                "client_id": PRIVATE_CAMERA_CLIENT_ID,
                "code": code,
                "redirect_uri": PRIVATE_CAMERA_REDIRECT_URI,
                "code_verifier": pkce["code_verifier"],
            },
        )
        self._data["token"] = _normalize_token_payload(payload)
        self._data.pop("pkce", None)
        await self._async_save()

    async def async_get_access_token(self) -> str:
        """Return a valid private mobile access token, refreshing as needed."""
        token = self._data.get("token") or {}
        refresh_token = token.get("refresh_token")
        access_token = token.get("access_token")
        expires_at = int(token.get("expires_at", 0) or 0)

        if not refresh_token:
            raise PrivateCameraAuthRequiredError(
                "Private camera auth is not configured for this config entry"
            )

        if not access_token or (expires_at - time.time()) < 120:
            payload = await self._async_form_post(
                "https://api.home-connect.com" + ENDPOINT_TOKEN,
                {
                    "grant_type": "refresh_token",
                    "client_id": PRIVATE_CAMERA_CLIENT_ID,
                    "refresh_token": refresh_token,
                },
            )
            token = _normalize_token_payload(payload)
            self._data["token"] = token
            await self._async_save()
            access_token = token["access_token"]

        return access_token

    async def _async_form_post(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        """Submit a form request and decode the returned JSON payload."""
        async with self._websession.post(url, data=data) as response:
            response.raise_for_status()
            return await response.json()

    async def _async_save(self) -> None:
        """Persist the current auth state privately in Home Assistant storage."""
        await self._store.async_save(self._data)


class AsyncMobilePrivateApi:
    """Access the private mobile-app endpoints that expose oven snapshots."""

    def __init__(self, auth: MobilePrivateAuth, websession: ClientSession) -> None:
        self._auth = auth
        self._websession = websession

    @property
    def is_configured(self) -> bool:
        """Return whether private camera auth is available."""
        return self._auth.is_configured

    async def async_build_authorize_url(self) -> str:
        """Start the PKCE login flow for the private mobile API."""
        return await self._auth.async_build_authorize_url()

    async def async_exchange_callback_url(self, callback_url: str) -> None:
        """Finish the PKCE login flow and persist the resulting token."""
        await self._auth.async_exchange_callback_url(callback_url)

    async def async_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> ClientResponse:
        """Call a private Home Connect backend endpoint using the stored mobile token."""
        token = await self._auth.async_get_access_token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        return await self._websession.request(
            method,
            f"{PRIVATE_API_HOST}{endpoint}",
            headers=headers,
            **kwargs,
        )

    async def async_get_latest_snapshot(
        self,
        appliance_ha_id: str,
        appliance_type: str | None,
    ) -> PrivateSnapshot | None:
        """Return the most recent snapshot for a private mobile appliance feed."""
        private_ha_id = _normalize_private_ha_id(appliance_ha_id)
        private_type = _normalize_private_appliance_type(appliance_type)
        response = await self.async_request(
            "GET",
            (
                f"/ui/app/v1/appliances/{private_ha_id}/{private_type}/media/latest"
                "?type=image"
            ),
        )
        response.raise_for_status()
        payload = await response.json()
        response.close()

        items = payload.get("items") or []
        if not items:
            return None

        latest = max(items, key=lambda item: int(item.get("timestamp", 0) or 0))
        hash_data = latest.get("hash") or {}
        return PrivateSnapshot(
            appliance_type=str(latest.get("haType") or appliance_type or private_type),
            content_type=str(latest.get("mediaType") or "image/jpeg"),
            hash_value=hash_data.get("value"),
            identifier=str(latest["identifier"]),
            media_type=str(latest.get("type") or "image"),
            object_detection_identifier=latest.get("objectDetectionImageId"),
            preview_identifier=latest.get("previewImageIdentifier"),
            private_ha_id=private_ha_id,
            timestamp_ms=int(latest.get("timestamp", 0) or 0),
            upload_status=latest.get("uploadStatus"),
            metadata=_metadata_list_to_dict(latest.get("metaData") or []),
        )

    async def async_download_media(
        self,
        private_ha_id: str,
        media_identifier: str,
    ) -> tuple[bytes, str]:
        """Download a private media object and return its bytes and content type."""
        response = await self.async_request(
            "GET",
            f"/api/media/v1/{private_ha_id}/media/{media_identifier}",
        )
        response.raise_for_status()
        data = await response.read()
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        response.close()
        return data, content_type


class PrivateSnapshotCoordinator:
    """Cache private snapshot metadata so camera and sensors share one request path."""

    def __init__(self, private_api: AsyncMobilePrivateApi) -> None:
        self._private_api = private_api
        self._snapshots: dict[str, PrivateSnapshot | None] = {}
        self._last_fetch: dict[str, float] = {}

    @property
    def is_configured(self) -> bool:
        """Return whether private camera auth is available."""
        return self._private_api.is_configured

    async def async_get_snapshot(
        self,
        appliance_ha_id: str,
        appliance_type: str | None,
        min_interval: int = 5,
    ) -> PrivateSnapshot | None:
        """Return cached snapshot metadata, refreshing when the cache is stale."""
        now = time.monotonic()
        last_fetch = self._last_fetch.get(appliance_ha_id, 0)
        if appliance_ha_id in self._snapshots and (now - last_fetch) < min_interval:
            return self._snapshots[appliance_ha_id]

        snapshot = await self._private_api.async_get_latest_snapshot(
            appliance_ha_id,
            appliance_type,
        )
        self._snapshots[appliance_ha_id] = snapshot
        self._last_fetch[appliance_ha_id] = now
        return snapshot

    async def async_download_media(
        self,
        private_ha_id: str,
        media_identifier: str,
    ) -> tuple[bytes, str]:
        """Download a private media object through the shared private API."""
        return await self._private_api.async_download_media(
            private_ha_id,
            media_identifier,
        )


def _generate_code_verifier() -> str:
    """Generate an RFC 7636-compatible PKCE verifier."""
    raw = secrets.token_bytes(48)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _generate_code_challenge(verifier: str) -> str:
    """Generate the S256 code challenge for a PKCE verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _extract_code_and_state(callback_url: str) -> tuple[str, str | None]:
    """Parse the mobile OAuth callback URL returned by the browser flow."""
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)

    error = params.get("error", [None])[0]
    if error:
        description = params.get("error_description", [""])[0]
        raise PrivateCameraAuthError(
            f"Private camera authorization failed: {error} {description}".strip()
        )

    code = params.get("code", [None])[0]
    state = params.get("state", [None])[0]
    if not code:
        raise PrivateCameraAuthError("No authorization code found in callback URL")
    return code, state


def _normalize_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Store token timestamps in a form that can be refreshed later."""
    fetched_at = int(time.time())
    normalized = dict(payload)
    normalized["fetched_at"] = fetched_at
    if "expires_in" in payload:
        normalized["expires_at"] = fetched_at + int(payload["expires_in"])
    return normalized


def _metadata_list_to_dict(metadata: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert the mobile backend metadata list into a convenient dictionary."""
    return {
        item["key"]: item.get("value")
        for item in metadata
        if isinstance(item, dict) and item.get("key")
    }


def _normalize_private_ha_id(appliance_ha_id: str) -> str:
    """Convert the public HA appliance id into the private media-service id."""
    prefix, separator, suffix = appliance_ha_id.rpartition("-")
    if separator and suffix.isdigit():
        return prefix
    return appliance_ha_id


def _normalize_private_appliance_type(appliance_type: str | None) -> str:
    """Map appliance types to the names used by the mobile media backend."""
    normalized = (appliance_type or "").strip().lower()
    if normalized == "oven":
        return "oven"
    return normalized or "appliance"
