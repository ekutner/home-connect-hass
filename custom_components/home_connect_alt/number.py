""" Implement the Number entities of this implementation """

import numbers
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events
from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DOMAIN


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Numbers for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        # if appliance.selected_program:
        #     selected_program_key = appliance.selected_program.key
        #     for key in appliance.available_programs[selected_program_key].options:
        #         option = appliance.available_programs[selected_program_key].options[key]
        #         if option.type in ["Int", "Float", "Double"]:
        #             device = OptionNumber(appliance, key, {"opt": option})
        #             entity_manager.add(device)
        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if option.type in ["Int", "Float", "Double"] or isinstance(option.value, numbers.Number):
                            device = OptionNumber(appliance, option.key)
                            entity_manager.add(device)

        for setting in appliance.settings.values():
            if setting.type in ["Int", "Float", "Double"] or isinstance(setting.value, numbers.Number):
                device = SettingsNumber(appliance, setting.key, {"opt": setting})
                entity_manager.add(device)

        entity_manager.register()


    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, Events.PAIRED)
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class OptionNumber(EntityBase, NumberEntity):
    """ Class for numeric options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        return self._key in self._appliance.selected_program.options \
        and super().available \
        and (
            "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlActive"]
        )

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        try:
            return self._conf['opt'].min
        except Exception as ex:
            pass
        return 0

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._conf['opt'].max

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def value(self) -> float:
        """Return the entity value to represent the entity state."""
        if self._key in self._appliance.selected_program.options:
            return self._appliance.selected_program.options[self._key].value
        return None

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self._appliance.async_set_option(self._key, value)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the option value: {ex.error_description} ({ex.code} - {self._key}={value})")
            else:
                raise HomeAssistantError(f"Failed to set the option value: ({ex.code} - {self._key}={value})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsNumber(EntityBase, NumberEntity):
    """ Class for numeric settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._conf['opt'].min

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._conf['opt'].max

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def value(self) -> float:
        """Return the entity value to represent the entity state."""
        if self._key in self._appliance.settings:
            return self._appliance.settings[self._key].value
        return None

    async def async_set_value(self, value: float) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, value)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting value: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to apply the setting value: ({ex.code})")


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
