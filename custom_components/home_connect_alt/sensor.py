""" Implement the Sensor entities of this implementation """
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Mapping
from home_connect_async import Appliance, HomeConnect, Events, GlobalStatus
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import Configuration, EntityBase, EntityManager
from .const import (
    CONF_TRANSLATION_MODE_SERVER,
    DEVICE_ICON_MAP,
    DOMAIN,
    CONF_TRANSLATION_MODE,
    HOME_CONNECT_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA"""
    homeconnect: HomeConnect = hass.data[DOMAIN]["homeconnect"]
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance: Appliance) -> None:

        if appliance.selected_program:
            conf = Configuration({"program_type": "selected"})
            device = ProgramSensor(appliance, conf=conf)
            entity_manager.add(device)
        if appliance.active_program:
            conf = Configuration({"program_type": "active"})
            device = ProgramSensor(appliance, conf=conf)
            entity_manager.add(device)

        conf = Configuration()
        if appliance.selected_program and appliance.selected_program.options:
            for option in appliance.selected_program.options.values():
                if not isinstance(option.value, bool):
                    device = ProgramOptionSensor(appliance, option.key, conf)
                    entity_manager.add(device)

        if appliance.active_program and appliance.active_program.options:
            for option in appliance.active_program.options.values():
                if not isinstance(option.value, bool):
                    device = ProgramOptionSensor(appliance, option.key, conf)
                    entity_manager.add(device)

        if appliance.status:
            for (key, value) in appliance.status.items():
                device = None
                if not isinstance(value.value, bool) and conf.get_entity_setting(key, "type") != "Boolean":  # should be a binary sensor if it has a boolean value
                    if "temperature" in key.lower():
                        conf.set_entity_setting(key,"class","temperature")
                    device = StatusSensor(appliance, key, conf)
                    entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                conf = Configuration()
                if setting.type != "Boolean" and not isinstance(setting.value, bool) and conf.get_entity_setting(setting.key, "type") != "Boolean":
                    device = SettingsSensor(appliance, setting.key, conf)
                    entity_manager.add(device)

        entity_manager.register()

    def remove_appliance(appliance: Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    # First add the global home connect status sensor
    async_add_entities([HomeConnectStatusSensor(homeconnect)])

    # Subscribe for events and register the existing appliances
    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED, Events.PROGRAM_STARTED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class ProgramSensor(EntityBase, SensorEntity):
    """Selected program sensor"""

    @property
    def unique_id(self) -> str:
        return f"{self.haId}_{self._conf['program_type']}_program"

    @property
    def name_ext(self) -> str:
        return f"{self._conf['program_type'].capitalize()} Program"

    @property
    def translation_key(self) -> str:
        return "programs"

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
        prog = self._appliance.selected_program if self._conf["program_type"] == "selected" else self._appliance.active_program
        if prog:
            if (prog.name and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER):
                return prog.name
            return prog.key
        return None

    async def async_on_update(self, appliance: Appliance, key: str, value) -> None:
        _LOGGER.debug("Updating sensor %s => %s", self.unique_id, self.native_value)
        self.async_write_ha_state()


class ProgramOptionSensor(EntityBase, SensorEntity):
    """Special active program sensor"""

    @property
    def device_class(self) -> str:
        if self.has_entity_setting("class"):
            return self.get_entity_setting("class")
        return f"{DOMAIN}__options"

    @property
    def translation_key(self) -> str:
        return "options"

    @property
    def icon(self) -> str:
        return self.get_entity_setting("icon", "mdi:office-building-cog")

    @property
    def name_ext(self) -> str:
        if self._appliance.selected_program and self._key in self._appliance.selected_program.options:
            return self._appliance.selected_program.options[self._key].name
        if self._appliance.active_program and self._key in self._appliance.active_program.options:
            return self._appliance.active_program.options[self._key].name
        return None

    @property
    def available(self) -> bool:
        return (
            (
                self._appliance.selected_program
                and (self._key in self._appliance.selected_program.options)
            )
            or (
                self._appliance.active_program
                and (self._key in self._appliance.active_program.options)
            )
        ) and super().available

    @property
    def internal_unit(self) -> str | None:
        """Get the original unit before manipulations"""
        unit = None
        t = None
        if self._appliance.active_program and self._key in self._appliance.active_program.options:
            t = self._appliance.active_program.options[self._key].type
            unit = self._appliance.active_program.options[self._key].unit
        elif self._appliance.selected_program and self._key in self._appliance.selected_program.options:
            t = self._appliance.selected_program.options[self._key].type
            unit = self._appliance.selected_program.options[self._key].unit
        if unit is None and t in ["Double", "Float", "Int"]:
            return ""

        return unit

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.has_entity_setting("unit"):
            return self.get_entity_setting("unit")

        unit = self.internal_unit
        if unit == "gram":
            return "kg"

        return unit

    @property
    def native_value(self):
        """Return the state of the sensor."""

        program = (
            self._appliance.active_program
            if self._appliance.active_program
            else self._appliance.selected_program
        )
        if program is None:
            return None

        if self._key not in program.options:
            _LOGGER.debug("Option key %s is missing from program", self._key)
            return None

        option = program.options[self._key]

        if self.device_class == "timestamp":
            return datetime.now(timezone.utc).astimezone() + timedelta(
                seconds=option.value
            )
        if "timespan" in self.device_class:
            m, s = divmod(option.value, 60)
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}"
        if self.internal_unit == "gram":
            return round(option.value / 1000, 1)
        if (
            option.displayvalue
            and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER
        ):
            return option.displayvalue
        if (
            isinstance(option.value, str)
            and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER
        ):
            if option.value.endswith(".Off"):
                return "Off"
            if option.value.endswith(".On"):
                return "On"
        return option.value

    async def async_on_update(self, appliance: Appliance, key: str, value) -> None:
        self.async_write_ha_state()


class StatusSensor(EntityBase, SensorEntity):
    """Status sensor"""

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__status"

    @property
    def translation_key(self) -> str:
        return "statuses"

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.status:
            status = self._appliance.status[self._key]
            if status:
                return status.name
        return None

    @property
    def icon(self) -> str:
        return self.get_entity_setting("icon", "mdi:gauge-full")

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.has_entity_setting("unit"):
            return self.get_entity_setting("unit")
        status = self._appliance.status.get(self._key)
        if status:
            return status.unit
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        status = self._appliance.status.get(self._key)
        if status:
            if status.displayvalue and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                return status.displayvalue
            return status.value
        return None

    async def async_on_update(self, appliance: Appliance, key: str, value) -> None:
        self.async_write_ha_state()


class SettingsSensor(EntityBase, SensorEntity):
    """Settings sensor"""

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def translation_key(self) -> str:
        return "settings"

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.settings:
            setting = self._appliance.settings[self._key]
            if setting:
                return setting.name
        return None

    @property
    def icon(self) -> str:
        return self.get_entity_setting("icon", "mdi:tune")

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.has_entity_setting("unit"):
            return self.get_entity_setting("unit")

        setting = self._appliance.settings.get(self._key)
        if setting:
            if setting.unit is None and setting.type in ["Double", "Float", "Int"]:
                return ""
            return setting.unit
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        setting = self._appliance.settings.get(self._key)
        if setting:
            if setting.displayvalue and self._conf[CONF_TRANSLATION_MODE] == CONF_TRANSLATION_MODE_SERVER:
                return setting.displayvalue
            return setting.value
        return None

    async def async_on_update(self, appliance: Appliance, key: str, value) -> None:
        self.async_write_ha_state()


class HomeConnectStatusSensor(SensorEntity):
    """Global Home Connect status sensor"""

    should_poll = True
    _attr_has_entity_name = True

    def __init__(self, homeconnect: HomeConnect) -> None:
        self._homeconnect = homeconnect
        self.entity_id = f'home_connect.{self.unique_id}'

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return "homeconnect_status"

    @property
    def translation_key(self) -> str:
        return "homeconnect_status"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return GlobalStatus.get_status().name
        # return GlobalStatus.get_status_str()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return {
            "blocked_until": GlobalStatus.get_blocked_until(),
            "blocked_for": GlobalStatus.get_block_time_str(),
        }
