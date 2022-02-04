""" Implement the Switch entities of this implementation """

from typing import Any

from home_connect_async import Appliance, HomeConnect, HomeConnectError
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase
from .const import DOMAIN


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    added_appliances = []

    def add_appliance(appliance:Appliance, event:str = None) -> None:
        if event=="DEPAIRED":
            added_appliances.remove(appliance.haId)
            return
        elif appliance.haId in added_appliances:
            return

        new_enities = []

        if appliance.selected_program:
            selected_program = appliance.selected_program
            for key in appliance.available_programs[selected_program.key].options:
                option = appliance.available_programs[selected_program.key].options[key]
                if option.type == "Boolean":
                    device = OptionSwitch(appliance, key, {"opt": option})
                    new_enities.append(device)

        for setting in appliance.settings.values():
            if setting.type == "Boolean":
                device = SettingsSwitch(appliance, setting.key, {"opt": setting})
                new_enities.append(device)

        if len(new_enities)>0:
            async_add_entities(new_enities)

    homeconnect.register_callback(add_appliance, ["PAIRED", "DEPAIRED"] )
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        added_appliances.append(appliance.haId)


class OptionSwitch(EntityBase, SwitchEntity):
    """ Switch for binary options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._key in self._appliance.selected_program.options:
            return self._appliance.selected_program.options[self._key].value
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self._appliance.async_set_option(self._key, True)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to set option ({ex.code})")


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._appliance.async_set_option(self._key, False)


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsSwitch(EntityBase, SwitchEntity):
    """ Switch for binary settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._key in self._appliance.settings:
            return self._appliance.settings[self._key].value
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, True)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to apply setting ({ex.code})")


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._appliance.async_apply_setting(self._key, False)


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
