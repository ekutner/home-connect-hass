""" Implement the Sensor entities of this implementation """
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
from home_connect_async import Appliance, HomeConnect, Events, GlobalStatus
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DEVICE_ICON_MAP, DOMAIN, CONF_SENSORS_TRANSLATION, HOME_CONNECT_DEVICE, SPECIAL_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """ Add sensors for passed config_entry in HA """
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)
    sensors_translation = hass.data[DOMAIN][CONF_SENSORS_TRANSLATION] == 'server'

    def add_appliance(appliance:Appliance) -> None:
        if appliance.selected_program:
            conf = { 'sensors_translation': sensors_translation, 'program_type': 'selected' }
            device = ProgramSensor(appliance,conf=conf)
            entity_manager.add(device)
        if appliance.active_program:
            conf = { 'sensors_translation': sensors_translation, 'program_type': 'active' }
            device = ProgramSensor(appliance,conf=conf)
            entity_manager.add(device)

        if appliance.selected_program and appliance.selected_program.options:
            for option in appliance.selected_program.options.values():
                if not isinstance(option.value, bool):
                    conf = SPECIAL_ENTITIES['options'].get(option.key, {})
                    conf['sensors_translation'] = sensors_translation
                    device = ProgramOptionSensor(appliance, option.key, conf)
                    entity_manager.add(device)

        if appliance.active_program and appliance.active_program.options:
            for option in appliance.active_program.options.values():
                if not isinstance(option.value, bool):
                    conf = SPECIAL_ENTITIES['options'].get(option.key, {})
                    conf['sensors_translation'] = sensors_translation
                    device = ProgramOptionSensor(appliance, option.key, conf)
                    entity_manager.add(device)

        # if appliance.active_program and appliance.active_program.options:
        #     selected_options = appliance.selected_program.options if appliance.selected_program else None
        #     for option in appliance.active_program.options.values():
        #         if ( (selected_options and option.key not in selected_options) or not selected_options ) \
        #             and not isinstance(option.value, bool) :
        #             conf = SPECIAL_ENTITIES['options'].get(option.key, {})
        #             conf['sensors_translation'] = sensors_translation
        #             device = ActivityOptionSensor(appliance, option.key, conf)
        #             entity_manager.add(device)

        for (key, value) in appliance.status.items():
            device = None
            if key in SPECIAL_ENTITIES['status']:
                conf = SPECIAL_ENTITIES['status'][key]
                conf['sensors_translation'] = sensors_translation
                if conf['type'] == 'sensor':
                    device = StatusSensor(appliance, key, conf)
            else:
                conf = { 'sensors_translation': sensors_translation }
                if not isinstance(value.value, bool): # should be a binary sensor if it has a boolean value
                    if 'temperature' in key.lower():
                        conf['class'] = 'temperature'
                    device = StatusSensor(appliance, key, conf)
            entity_manager.add(device)

        for setting in appliance.settings.values():
            conf = { 'sensors_translation': sensors_translation }
            if setting.type != "Boolean" and not isinstance(setting.value, bool):
                device = SettingsSensor(appliance, setting.key, conf)
                entity_manager.add(device)


        entity_manager.register()


    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)


    # First add the global home connect satus sensor
    async_add_entities([HomeConnectStatusSensor(homeconnect)])

    # Subscribe for events and register the existing appliances
    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.PROGRAM_STARTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)



class ProgramSensor(EntityBase, SensorEntity):
    """ Selected program sensor """
    @property
    def unique_id(self) -> str:
        return f"{self.haId}_{self._conf['program_type']}_program"

    @property
    def name_ext(self) -> str:
        return f"{self._conf['program_type'].capitalize()} Program"

    @property
    def icon(self) -> str:
        if self._appliance.type in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._appliance.type]
        return None

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__programs"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        prog = self._appliance.selected_program if self._conf['program_type'] == 'selected' else self._appliance.active_program
        if prog:
            if prog.name and self._conf['sensors_translation']:
                return prog.name
            else:
                return prog.key
        return None

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()

    # async def async_start_program(self) -> bool:
    #     return await self._appliance.async_start_program()

    # async def async_select_program(self, program, options=None, **kwargs) -> bool:
    #     return await self._appliance.async_select_program(key=program, options=options)


class ProgramOptionSensor(EntityBase, SensorEntity):
    """ Special active program sensor """
    @property
    def device_class(self) -> str:
        if "class" in self._conf:
            return self._conf["class"]
        return f"{DOMAIN}__options"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def name_ext(self) -> str:
        if self._appliance.selected_program and (self._key in self._appliance.selected_program.options):
            return self._appliance.selected_program.options[self._key].name
        elif self._appliance.active_program and (self._key in self._appliance.active_program.options):
            return self._appliance.active_program.options[self._key].name
        return None

    @property
    def available(self) -> bool:
        return \
        (
            (self._appliance.selected_program and (self._key in self._appliance.selected_program.options) )
            or (self._appliance.active_program and (self._key in self._appliance.active_program.options) )
        ) and super().available

    @property
    def internal_unit(self) -> str | None:
        """ Get the original unit before manipulations """
        if "unit" in self._conf:
            return self._conf["unit"]
        if self._appliance.active_program and (self._key in  self._appliance.active_program.options):
            return self._appliance.active_program.options[self._key].unit
        if self._appliance.selected_program and (self._key in  self._appliance.selected_program.options):
            return self._appliance.selected_program.options[self._key].unit
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        unit = self.internal_unit
        if unit=="gram":
            return "kg"
        return unit

    @property
    def native_value(self):
        """Return the state of the sensor."""

        program = self._appliance.active_program if self._appliance.active_program else self._appliance.selected_program
        if program is None:
            return None

        if self._key not in program.options:
            _LOGGER.debug("Option key %s is missing from program", self._key)
            return None

        option = program.options[self._key]

        if self.device_class == "timestamp":
            return  datetime.now(timezone.utc).astimezone() + timedelta(seconds=option.value)
        if "timespan" in self.device_class:
            m, s = divmod(option.value, 60)
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}"
        if self.internal_unit=="gram":
            return round(option.value/1000, 1)
        if option.displayvalue and  self._conf['sensors_translation']:
            return option.displayvalue
        if isinstance(option.value, str) and self._conf['sensors_translation']:
            if option.value.endswith(".Off"):
                return "Off"
            if option.value.endswith(".On"):
                return "On"
        return option.value

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


# class ActivityOptionSensor(ProgramOptionSensor):
#     """ Special active program sensor """

#     @property
#     def name_ext(self) -> str:
#         if self._appliance.active_program and (self._key in self._appliance.active_program.options):
#             return self._appliance.active_program.options[self._key].name
#         return None


class StatusSensor(EntityBase, SensorEntity):
    """ Status sensor """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__status"

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.status:
            status = self._appliance.status[self._key]
            if status:
                return status.name
        return None

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:gauge-full')

    @property
    def native_value(self):
        """Return the state of the sensor."""
        status = self._appliance.status.get(self._key)
        if status:
            if status.displayvalue  and self._conf['sensors_translation']:
                return status.displayvalue
            return status.value
        return None

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsSensor(EntityBase, SensorEntity):
    """ Status sensor """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.settings:
            setting = self._appliance.settings[self._key]
            if setting:
                return setting.name
        return None

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def native_value(self):
        """Return the state of the sensor."""
        setting = self._appliance.settings.get(self._key)
        if setting:
            if setting.displayvalue  and self._conf['sensors_translation']:
                return setting.displayvalue
            return setting.value
        return None

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class HomeConnectStatusSensor(SensorEntity):
    """ Global Home Connect status sensor """
    should_poll = True

    def __init__(self, homeconnect:HomeConnect) -> None:
        self._homeconnect = homeconnect

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return "homeconnect_status"

    @property
    def name(self) -> str:
        return "Home Connect Status"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        #return self._homeconnect.status.name
        return GlobalStatus.get_status_str()
