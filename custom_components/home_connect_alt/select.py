""" Implement the Select entities of this implementation """
from __future__ import annotations
import logging
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events, ConditionalLogger as CL
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum, Configuration
from .const import DEVICE_ICON_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        if appliance.available_programs:
            device = ProgramSelect(appliance)
            entity_manager.add(device)

        conf = Configuration()
        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if conf.get_entity_setting(option.key, "type") == "DelayedOperation":
                            device = DelayedOperationSelect(appliance, option.key, conf, option)
                            entity_manager.add(device)
                        elif option.allowedvalues and len(option.allowedvalues)>1:
                            device = OptionSelect(appliance, option.key, conf)
                            entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                if (setting.allowedvalues and len(setting.allowedvalues)>1 and not is_boolean_enum(setting.allowedvalues)) \
                    and setting.access != "read" :
                    device = SettingsSelect(appliance, setting.key, conf)
                    entity_manager.add(device)

        entity_manager.register()

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.PROGRAM_SELECTED, Events.PROGRAM_STARTED ,Events.PROGRAM_FINISHED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)

class ProgramSelect(InteractiveEntityBase, SelectEntity):
    """ Selection of available programs """

    @property
    def unique_id(self) -> str:
        return f'{self.haId}_programs'

    @property
    def translation_key(self) -> str:
        return "programs"

    @property
    def name_ext(self) -> str:
        return "Programs"

    @property
    def icon(self) -> str:
        if self._appliance.type in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._appliance.type]
        return None

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__programs"

    @property
    def available(self) -> bool:
        return super().available \
            and self._appliance.available_programs \
            and  (
                "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
                self._appliance.status["BSH.Common.Status.RemoteControlActive"]
            )

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        if self._appliance.available_programs:
            return list(self._appliance.available_programs.keys())
        return []

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        current_program = self._appliance.get_applied_program()
        if current_program:
            if self._appliance.available_programs and current_program.key in self._appliance.available_programs:
                # The API sometimes returns programs which are not one of the avilable programs so we ignore it
                CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current selected program is %s", current_program.key)
                return current_program.key
            else:
                CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current program %s is not in available_programs", current_program.key)
        else:
            CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current program is None")
        return None

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_select_program(program_key=option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the selected program: {ex.error_description} ({ex.code} - {self._key}={option})")
            else:
                raise HomeAssistantError(f"Failed to set the selected program ({ex.code} - {self._key}={option})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class OptionSelect(InteractiveEntityBase, SelectEntity):
    """ Selection of program options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def translation_key(self) -> str:
        return "options"

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
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        # if self.program_option_available:
        #     selected_program_key = self._appliance.selected_program.key
        #     available_program = self._appliance.available_programs.get(selected_program_key)
        #     if available_program:
        #         option = available_program.options.get(self._key)
        #         if option:
        #             #_LOGGER.info("Allowed values for %s : %s", self._key, str(option.allowedvalues))
        #             vals = option.allowedvalues.copy()
        #             vals.append('')
        #             return vals
        # #_LOGGER.info("Allowed values for %s : %s", self._key, None)
        option = self._appliance.get_applied_program_available_option(self._key)
        if option:
            vals = option.allowedvalues.copy()
            #vals.append('')
            return vals

        return []

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        # if self._appliance.selected_program.options[self._key].value not in self.options:
        #     _LOGGER.debug("The current option is not in the list of available options")
        option = self._appliance.get_applied_program_option(self._key)
        if option:
            CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Option %s current value: %s", self._key, option.value)
            return option.value
        CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Option %s current value is None", self._key)
        return None

    async def async_select_option(self, option: str) -> None:
        if option == '':
            _LOGGER.debug('Tried to set an empty option')
            return
        try:
            await self._appliance.async_set_option(self._key, option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the selected option: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to set the selected option: ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsSelect(InteractiveEntityBase, SelectEntity):
    """ Selection of settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def translation_key(self) -> str:
        return "settings"

    @property
    def name_ext(self) -> str|None:
        if self._key in self._appliance.settings and self._appliance.settings[self._key].name:
            return self._appliance.settings[self._key].name
        return None

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:tune')

    @property
    def available(self) -> bool:
        return super().available \
        and (
            "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlActive"]
        )

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        try:
            return self._appliance.settings[self._key].allowedvalues
        except Exception as ex:
            pass
        return []

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self._appliance.settings[self._key].value

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting: {ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to apply the setting: ({ex.code})")


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class DelayedOperationSelect(InteractiveEntityBase, SelectEntity):
    """ Class for delayed start select box """
    def __init__(self, appliance: Appliance, key: str = None, conf: dict = None, hc_obj = None) -> None:
        super().__init__(appliance, key, conf, hc_obj)
        self._current = '0:00'

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:clock-outline')

    @property
    def name_ext(self) -> str|None:
        """ Provide the suffix of the name, can be be overriden by sub-classes to provide a custom or translated display name """
        return self._hc_obj.name if self._hc_obj.name else "Delayed operation"

    @property
    def available(self) -> bool:
        available = super().program_option_available
        if not available:
            self._current = '0:00'
            self._appliance.clear_startonly_option(self._key)
        return available

    @property
    def options(self) -> list[str]:
        options = [ "0:00" ]

        if self._appliance.selected_program and self._appliance.selected_program.options and self._key in self._appliance.selected_program.options:
            selected_program_time = self._appliance.selected_program.options[self._key].value
            start = 1 if "StartInRelative" in self._key else selected_program_time//1800 + (selected_program_time % 1800 > 0)
            #end = self._appliance.available_programs[self._appliance.selected_program.key].options[self._key].max
            end = 49
            for t in range(start, end):
                options.append(f"{int(t/2)}:{(t%2)*30:02}")
        else:
            self._current = '0:00'
            self._appliance.clear_startonly_option(self._key)
        return options

    @property
    def current_option(self) -> str | None:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        if option == '0:00':
            self._appliance.clear_startonly_option(self._key)
            return
        parts = option.split(':')
        delay = int(parts[0])*3600 + int(parts[1])*60
        self._appliance.set_startonly_option(self._key, delay)

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        if key == Events.PROGRAM_FINISHED:
            self._current = '0:00'
        self.async_write_ha_state()