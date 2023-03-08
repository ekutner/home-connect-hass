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
from .const import DOMAIN, ENTITY_SETTINGS


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Numbers for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    conf = Configuration()
    number_types = ["Int", "Float", "Double"]
    def add_appliance(appliance:Appliance) -> None:
        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if (not conf.has_entity_setting(option.key, "type") and option.type in number_types) or conf.has_entity_setting(option.key, "type") in number_types:
                            device = OptionNumber(appliance, option.key, hc_obj=option)
                            entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                if ((not conf.has_entity_setting(setting.key, "type") and setting.type in number_types) or conf.has_entity_setting(setting.key, "type") in number_types) \
                    and "writ" in setting.access :
                    device = SettingsNumber(appliance, setting.key, hc_obj=setting)
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
        return self.get_entity_setting('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        return self.program_option_available

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self._hc_obj.min:
            return self._hc_obj.min
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self._hc_obj.max:
            return self._hc_obj.max
        return sys.maxsize

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._hc_obj.stepsize

    @property
    def native_unit_of_measurement(self) -> str:
        if self.has_entity_setting("unit"):
            return self.get_entity_setting("unit")
        if self._hc_obj.unit:
            return self._hc_obj.unit
        return ""

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
            if self._hc_obj.type == 'Int':
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
        return self._hc_obj.name

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:tune')

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self._hc_obj.min:
            return self._hc_obj.min
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self._hc_obj.max:
            return self._hc_obj.max
        return sys.maxsize

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._hc_obj.stepsize

    @property
    def native_unit_of_measurement(self) -> str:
        if self.has_entity_setting("unit"):
            return self.get_entity_setting("unit")
        if self._hc_obj.unit:
            return self._hc_obj.unit
        return ""

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        return self._hc_obj.value

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
