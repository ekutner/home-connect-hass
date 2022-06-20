""" Implement the Switch entities of this implementation """

from __future__ import annotations
import logging
from typing import Any

from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum
from .const import DOMAIN, SPECIAL_ENTITIES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if option.key not in SPECIAL_ENTITIES['ignore'] and (option.type == "Boolean" or isinstance(option.value, bool)):
                            device = OptionSwitch(appliance, option.key)
                            entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                if setting.key not in SPECIAL_ENTITIES['ignore'] and \
                    ( setting.type == "Boolean" or isinstance(setting.value, bool) or is_boolean_enum(setting.allowedvalues) ):
                    device = SettingsSwitch(appliance, setting.key)
                    entity_manager.add(device)

        entity_manager.register()


    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class OptionSwitch(InteractiveEntityBase, SwitchEntity):
    """ Switch for binary options """
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
    def is_on(self) -> bool:
        """Return True if entity is on."""
        option = self._appliance.get_applied_program_option(self._key)
        if option:
            return option.value
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self._appliance.async_set_option(self._key, True)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the option: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to set the option: ({ex.code})")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self._appliance.async_set_option(self._key, False)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the option: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to set the option: ({ex.code})")


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsSwitch(InteractiveEntityBase, SwitchEntity):
    """ Switch for binary settings """
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
    def available(self) -> bool:
        return self._key in self._appliance.settings \
        and super().available \
        and (
            "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlActive"]
        )

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._key in self._appliance.settings:
            setting = self._appliance.settings[self._key]
            if setting.allowedvalues and setting.value.lower().endswith(".off"):
                return False
            elif setting.allowedvalues and setting.value.lower().endswith(".on"):
                return True
            else:
                return setting.value
        return None

    def bool_to_enum(self, allowedvalues, val:bool) -> str:
        """ Get the matching enum value for the provided boolean value """
        for av in allowedvalues:
            if (val and av.lower().endswith('.on')) or (not val and av.lower().endswith('.off')) :
                return av
        _LOGGER.error("Unexpected Error: couldn't find a boolean enum value in allowedvalues: %s", allowedvalues)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            setting = self._appliance.settings[self._key]
            if setting.allowedvalues:
                await self._appliance.async_apply_setting(self._key, self.bool_to_enum(setting.allowedvalues, True))
            else:
                await self._appliance.async_apply_setting(self._key, True)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to apply the setting: ({ex.code})")


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            setting = self._appliance.settings[self._key]
            if setting.allowedvalues:
                await self._appliance.async_apply_setting(self._key, self.bool_to_enum(setting.allowedvalues, False))
            else:
                await self._appliance.async_apply_setting(self._key, False)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to apply the setting: ({ex.code})")


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
