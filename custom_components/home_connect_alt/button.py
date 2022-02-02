from home_connect_async import Appliance, HomeConnect, HomeConnectError
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase
from .const import DEVICE_ICON_MAP, DOMAIN, SPECIAL_ENTITIES


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    added_appliances = []

    def add_appliance(appliance:Appliance, event:str = None) -> None:
        if event=="DEPAIRED":
            added_appliances.remove(appliance.haId)
            return
        elif appliance.haId in added_appliances:
            return

        new_enities = []
        if appliance.available_programs:
            device = StartButton(appliance)
            new_enities.append(device)

        if len(new_enities)>0:
            async_add_entities(new_enities)

    homeconnect.register_callback(add_appliance, ["PAIRED", "DEPAIRED"] )
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        added_appliances.append(appliance.haId)


class StartButton(EntityBase, ButtonEntity):
    @property
    def unique_id(self) -> str:
        return f'{self.haId}_start'

    @property
    def name(self) -> str:
        return f"{self._appliance.brand} {self._appliance.type} - Start"

    @property
    def icon(self) -> str:
        if self._key in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._key]
        return None

    async def async_press(self) -> None:
        try:
            await self._appliance.async_start_program()
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"{ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to start the current program ({ex.code})")


    async def async_added_to_hass(self):
        self._appliance.register_callback(self.async_on_update, "CONNECTION_CHANGED")
    async def async_will_remove_from_hass(self):
        self._appliance.deregister_callback(self.async_on_update, "CONNECTION_CHANGED")
    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()