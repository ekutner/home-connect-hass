""" Implement the Number entities of this implementation """
from __future__ import annotations
import sys
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events
from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import Configuration, InteractiveEntityBase, EntityManager
from .const import DOMAIN, SPECIAL_ENTITIES


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Numbers for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if option.key not in SPECIAL_ENTITIES['ignore'] and option.type in ["Int", "Float", "Double"]:
                            device = OptionNumber(appliance, option.key, Configuration({"opt": option}))
                            entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                if setting.key not in SPECIAL_ENTITIES['ignore'] and setting.type in ["Int", "Float", "Double"]:
                    device = SettingsNumber(appliance, setting.key, Configuration({"opt": setting}))
                    entity_manager.add(device)

        entity_manager.register()


    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class OptionNumber(InteractiveEntityBase, NumberEntity):
    """ Class for numeric options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def name_ext(self) -> str|None:
        if self._appliance.available_programs:
            for program in self._appliance.available_programs.values():
                if program.options and self._key in program.options and program.options[self._key].name:
                    return program.options[self._key].name
        return None


    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        return self.program_option_available

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self._conf['opt'].min:
            return self._conf['opt'].min
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self._conf['opt'].max:
            return self._conf['opt'].max
        return sys.maxsize

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def native_unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        option = self._appliance.get_applied_program_option(self._key)
        if option:
            return option.value
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            if self._conf['opt'].type == 'Int':
                value = int(value)
            await self._appliance.async_set_option(self._key, value)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the option value: {ex.error_description} ({ex.code} - {self._key}={value})")
            else:
                raise HomeAssistantError(f"Failed to set the option value: ({ex.code} - {self._key}={value})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsNumber(InteractiveEntityBase, NumberEntity):
    """ Class for numeric settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def name_ext(self) -> str|None:
        if self._key in self._appliance.settings and self._appliance.settings[self._key].name:
            return self._appliance.settings[self._key].name
        return None

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self._conf['opt'].min:
            return self._conf['opt'].min
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self._conf['opt'].max:
            return self._conf['opt'].max
        return sys.maxsize

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def native_unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        if self._key in self._appliance.settings:
            return self._appliance.settings[self._key].value
        return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, value)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting value: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to apply the setting value: ({ex.code})")


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
