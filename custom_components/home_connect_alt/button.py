import logging
from sys import exc_info
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DEVICE_ICON_MAP, DOMAIN, HOME_CONNECT_DEVICE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """ Add buttons for passed config_entry in HA """
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        if appliance.available_programs:
            device = StartButton(appliance)
            entity_manager.add(device)
        entity_manager.register()
        
    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    # First add the integration button
    async_add_entities([HomeConnectRefreshButton(homeconnect), HomeConnecDebugButton(homeconnect)])

    # Subscribe for events and register existing appliances
    homeconnect.register_callback(add_appliance, Events.PAIRED)
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class StartButton(EntityBase, ButtonEntity):
    """ Class for buttons that start the selected program """
    @property
    def unique_id(self) -> str:
        return f'{self.haId}_start'

    # @property
    # def name(self) -> str:
    #     appliance_name = self._appliance.name if self._appliance.name else self._appliance.type
    #     return f"{self._appliance.brand} {appliance_name} - Start"

    @property
    def name_ext(self) -> str:
        return "Start"


    @property
    def available(self) -> bool:
        return super().available \
        and (
            "BSH.Common.Status.RemoteControlStartAllowed" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlStartAllowed"]
        )

    @property
    def icon(self) -> str:
        if self._key in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._key]
        return None

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            await self._appliance.async_start_program()
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to start the current program: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to start the current program ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class HomeConnectRefreshButton(ButtonEntity):
    """ Class for a button to trigger a global refresh of Home Connect data  """

    def __init__(self, homeconnect:HomeConnect) -> None:
        self._homeconnect = homeconnect

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return 'homeconnect_refresh'

    @property
    def name(self) -> str:
        return "Home Connect Refresh"

    @property
    def icon(self) -> str:
        return "mdi:cloud-refresh"

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            self._homeconnect.start_load_data_task(refresh=HomeConnect.RefreshMode.ALL)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to refresh the Home Connect data: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to refresh the Home Connect data ({ex.code})")


class HomeConnecDebugButton(ButtonEntity):
    """ Class for a button to trigger a global refresh of Home Connect data  """

    def __init__(self, homeconnect:HomeConnect) -> None:
        self._homeconnect = homeconnect

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return 'homeconnect_debug'

    @property
    def name(self) -> str:
        return "Home Connect Debug Info"

    @property
    def icon(self) -> str:
        return "mdi:bug-check"

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            js=self._homeconnect.to_json(indent=2)
            _LOGGER.error(js)
        except Exception as ex:
            raise HomeAssistantError("Failed to serialize to JSON", exc_info=ex)
