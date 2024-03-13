""" Implement the Select entities of this implementation """
from __future__ import annotations
import logging
from custom_components.home_connect_alt.time import DelayedOperationTime
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events, ConditionalLogger as CL
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_registry import async_get

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum, Configuration
from .const import CONF_DELAYED_OPS, CONF_DELAYED_OPS_ABSOLUTE_TIME, CONF_DELAYED_OPS_DEFAULT, CONF_TRANSLATION_MODE, CONF_TRANSLATION_MODE_SERVER, DEVICE_ICON_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    #homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entry_conf:Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = entry_conf["homeconnect"]
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        conf = entry_conf.get_config()

        if appliance.available_programs:
            device = ProgramSelect(appliance, None, conf)
            entity_manager.add(device)

        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if conf.get_entity_setting(option.key, "type") == "DelayedOperation" and (
                            entry_conf[CONF_DELAYED_OPS] == CONF_DELAYED_OPS_DEFAULT or not DelayedOperationTime.has_program_run_time(appliance)):
                            device = DelayedOperationSelect(appliance, option.key, conf, option)
                            # remove the TIME delayed operation entity if it exists
                            reg = async_get(hass)
                            time_entity = reg.async_get_entity_id("time", DOMAIN, device.unique_id)
                            if time_entity:
                                reg.async_remove(time_entity)

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

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED, Events.PROGRAM_STARTED, Events.PROGRAM_SELECTED])
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
                self._appliance.status["BSH.Common.Status.RemoteControlActive"].value
            )

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        if self._appliance.available_programs:
            if self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                return [program.name if program.name else program.key for program in self._appliance.available_programs.values()]
            return list(self._appliance.available_programs.keys())
        return []

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        current_program = self._appliance.get_applied_program()
        if current_program:
            if self._appliance.available_programs and current_program.key in self._appliance.available_programs:
                # The API sometimes returns programs which are not one of the available programs so we ignore it
                CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current selected program is %s", current_program.key)
                return current_program.name if current_program.name and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER else current_program.key
            CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current program %s is not in available_programs", current_program.key)
        else:
            CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Current program is None")
        return None


    async def async_select_option(self, option: str) -> None:
        try:
            if self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                program = next((p for p in self._appliance.available_programs.values() if p.name == option), None)
                await self._appliance.async_select_program(program_key=program.key)
            else:
                await self._appliance.async_select_program(program_key=option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the selected program: {ex.error_description} ({ex.code} - {self._key}={option})")
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
            if self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                vals = option.allowedvaluesdisplay.copy() if option.allowedvaluesdisplay else option.allowedvalues.copy()
            else:
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
            if self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                available_option = self._appliance.get_applied_program_available_option(self._key)
                if (available_option.allowedvaluesdisplay):
                    idx = available_option.allowedvalues.index(option.value)
                    return available_option.allowedvaluesdisplay[idx]
            return option.value
        CL.debug(_LOGGER, CL.LogMode.VERBOSE, "Option %s current value is None", self._key)
        return None

    async def async_select_option(self, option: str) -> None:
        if option == '':
            _LOGGER.debug('Tried to set an empty option')
            return
        try:
            if self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                available_option = self._appliance.get_applied_program_available_option(self._key)
                if (available_option.allowedvaluesdisplay):
                    idx = available_option.allowedvaluesdisplay.index(option)
                    option = available_option.allowedvalues[idx]
            await self._appliance.async_set_option(self._key, option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to set the selected option: {ex.error_description} ({ex.code})")
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
            self._appliance.status["BSH.Common.Status.RemoteControlActive"].value
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
        return self._appliance.settings[self._key].value if self._appliance.settings and self._key in self._appliance.settings else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to apply the setting: {ex.error_description} ({ex.code})")
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
