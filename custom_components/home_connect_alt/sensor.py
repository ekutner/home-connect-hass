""" Implement the Sensor entities of this implementation """
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Mapping
from home_connect_async import Appliance, HomeConnect, Events, HealthStatus
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .common import Configuration, EntityBase, EntityManager
from .consumption import async_get_program_reference
from .const import (
    CONF_CONSUMPTION_MODE,
    CONF_CONSUMPTION_MODE_DEFAULT,
    CONF_CONSUMPTION_MODE_LINEAR,
    CONF_TRANSLATION_MODE_SERVER,
    CONSUMPTION_APPLIANCE_TYPES,
    DEVICE_ICON_MAP,
    DOMAIN,
    CONF_TRANSLATION_MODE,
    HOME_CONNECT_DEVICE,
)

# How often linear-mode sensors recompute their ramped value while a cycle runs
RAMP_UPDATE_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigType, async_add_entities: AddEntitiesCallback,) -> None:
    """Add sensors for passed config_entry in HA"""
    #homeconnect: HomeConnect = hass.data[DOMAIN]["homeconnect"]
    entry_conf:Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = entry_conf["homeconnect"]

    entity_manager = EntityManager(async_add_entities, "Sensor")
    auth = entry_conf.get("auth")

    def add_appliance(appliance: Appliance) -> None:

        if auth is not None and appliance.type in CONSUMPTION_APPLIANCE_TYPES:
            conf = entry_conf.get_config()
            for kind in ("energy", "water"):
                entity_manager.add(ConsumptionSensor(appliance, conf, auth, kind))

        if appliance.selected_program:
            conf = entry_conf.get_config({"program_type": "selected"})
            device = ProgramSensor(appliance, None, conf)
            entity_manager.add(device)
        if appliance.active_program:
            conf = entry_conf.get_config({"program_type": "active"})
            device = ProgramSensor(appliance, None, conf)
            entity_manager.add(device)

        conf = entry_conf.get_config()
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
                conf = entry_conf.get_config()
                if setting.type != "Boolean" and not isinstance(setting.value, bool) and conf.get_entity_setting(setting.key, "type") != "Boolean":
                    device = SettingsSensor(appliance, setting.key, conf)
                    entity_manager.add(device)

        entity_manager.register()

    def remove_appliance(appliance: Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    # First add the global home connect status sensor
    async_add_entities( [ HomeConnectStatusSensor(homeconnect, "" if entry_conf["primary_config_entry"] else "_"+config_entry.entry_id) ] )

    # Subscribe for events and register the existing appliances
    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED, Events.PROGRAM_STARTED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class ProgramSensor(EntityBase, SensorEntity):
    """Selected program sensor"""

    @property
    def unique_id(self) -> str:
        return f"{self.safe_haId}_{self._conf['program_type']}_program"

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
        if self.device_class and "timespan" in self.device_class:
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

    def __init__(self, homeconnect: HomeConnect, name_suffix:str) -> None:
        self._homeconnect = homeconnect
        self._name_suffix = name_suffix
        self.entity_id = f"sensor.{self.unique_id}"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return "homeconnect_status" + self._name_suffix

    @property
    def translation_key(self) -> str:
        return "homeconnect_status"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self._homeconnect.health.get_status().name

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return {
            "blocked_until": self._homeconnect.health.get_blocked_until(),
            "blocked_for": self._homeconnect.health.get_block_time_str(),
        }


class ConsumptionSensor(EntityBase, RestoreEntity, SensorEntity):
    """Cumulative energy/water consumption for the HA Energy Dashboard.

    The Home Connect cloud API exposes no metered consumption for most appliances
    (only the EnergyForecast/WaterForecast percentages). This sensor reproduces what
    the official app's usage statistics show: on every completed program it looks up
    that program's reference consumption (kWh / liters) from the program-assistant
    service and adds it to a persistent running total, published with
    state_class=total_increasing so it can feed the Energy Dashboard.
    """

    # kind -> (device_class, unit, result field, icon)
    _KINDS = {
        "energy": (SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, "energy_kwh", "mdi:lightning-bolt"),
        "water": (SensorDeviceClass.WATER, UnitOfVolume.LITERS, "water_liters", "mdi:water"),
    }

    def __init__(self, appliance: Appliance, conf: Configuration, auth, kind: str, region: str | None = None) -> None:
        self._kind = kind
        self._auth = auth
        self._region = region
        self._mode = conf.get(CONF_CONSUMPTION_MODE, CONF_CONSUMPTION_MODE_DEFAULT)
        self._base = 0.0        # settled total from completed cycles
        self._cycle = None      # {"target","start","duration"} while a program runs (linear)
        self._running_program = None
        self._running_options = None
        self._unsub_timer = None
        super().__init__(appliance, f"consumption_{kind}_total", conf)

    @property
    def device_class(self) -> str:
        return self._KINDS[self._kind][0]

    @property
    def native_unit_of_measurement(self) -> str:
        return self._KINDS[self._kind][1]

    @property
    def state_class(self) -> str:
        return SensorStateClass.TOTAL_INCREASING

    @property
    def icon(self) -> str:
        return self._KINDS[self._kind][3]

    @property
    def name_ext(self) -> str:
        return f"Total {self._kind.capitalize()} Consumption"

    @property
    def available(self) -> bool:
        # The accumulated total stays valid even when the appliance is offline.
        return True

    @property
    def native_value(self):
        return round(self._current_total(), 3)

    def _current_total(self) -> float:
        """Current cumulative value; ramps within the active cycle in linear mode."""
        if self._mode == CONF_CONSUMPTION_MODE_LINEAR and self._cycle and self._cycle["duration"] > 0:
            elapsed = (datetime.now(timezone.utc) - self._cycle["start"]).total_seconds()
            frac = min(max(elapsed / self._cycle["duration"], 0.0), 1.0)
            return self._base + self._cycle["target"] * frac
        return self._base

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        # Persisted by RestoreEntity so a restart can resume correctly.
        attrs = {"mode": self._mode, "base": round(self._base, 3)}
        if self._cycle:
            attrs["cycle_target"] = round(self._cycle["target"], 3)
            attrs["cycle_start"] = self._cycle["start"].isoformat()
            attrs["cycle_duration"] = self._cycle["duration"]
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_restore_state()
        self._appliance.register_callback(self._on_program_started, Events.PROGRAM_STARTED)
        self._appliance.register_callback(self._on_program_finished, Events.PROGRAM_FINISHED)

    async def _async_restore_state(self) -> None:
        """Restore the settled total (and an in-progress linear ramp) after a restart."""
        last_state = await self.async_get_last_state()
        if not last_state:
            return
        attrs = last_state.attributes or {}
        base = attrs.get("base")
        if base is None and last_state.state not in (None, "unknown", "unavailable"):
            base = last_state.state
        try:
            self._base = float(base)
        except (TypeError, ValueError):
            self._base = 0.0
        # Resume a linear ramp only if the appliance is still running the same cycle.
        if self._mode == CONF_CONSUMPTION_MODE_LINEAR and self._appliance.active_program \
                and attrs.get("cycle_start") and attrs.get("cycle_target") is not None:
            try:
                self._cycle = {
                    "target": float(attrs["cycle_target"]),
                    "start": datetime.fromisoformat(attrs["cycle_start"]),
                    "duration": int(attrs.get("cycle_duration") or 0),
                }
                self._start_ramp_timer()
            except (TypeError, ValueError):
                self._cycle = None

    async def async_will_remove_from_hass(self) -> None:
        self._stop_ramp_timer()
        self._appliance.deregister_callback(self._on_program_started, Events.PROGRAM_STARTED)
        self._appliance.deregister_callback(self._on_program_finished, Events.PROGRAM_FINISHED)
        await super().async_will_remove_from_hass()

    def _start_ramp_timer(self) -> None:
        if self._unsub_timer is None and self.hass is not None:
            self._unsub_timer = async_track_time_interval(self.hass, self._async_ramp_tick, RAMP_UPDATE_INTERVAL)

    def _stop_ramp_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def _async_ramp_tick(self, now) -> None:
        self.async_write_ha_state()

    def _settle_cycle(self) -> None:
        """Fold an in-progress linear cycle into the settled base total."""
        if self._cycle:
            self._base += self._cycle["target"]
            self._cycle = None
        self._stop_ramp_timer()

    async def async_on_update(self, appliance: Appliance, key: str, value) -> None:
        self.async_write_ha_state()

    async def _async_fetch(self, appliance: Appliance, program_key, options):
        try:
            return await async_get_program_reference(
                self._auth, appliance.haId, appliance.type, program_key, options, self._region
            )
        except Exception as ex:  # noqa: BLE001 - never let a fetch error break the event
            _LOGGER.debug("Failed to fetch consumption for %s: %s", program_key, ex)
            return None

    async def _on_program_started(self, appliance: Appliance, key, value=None) -> None:
        # Cache the running program + options (active_program is cleared by the time
        # PROGRAM_FINISHED fires) so we know what was consumed on finish.
        prog = appliance.active_program
        if not prog:
            return
        self._running_program = prog.key
        self._running_options = [{"key": o.key, "value": o.value} for o in (prog.options or {}).values()]
        if self._mode != CONF_CONSUMPTION_MODE_LINEAR:
            return
        self._settle_cycle()  # never lose a still-open previous cycle
        ref = await self._async_fetch(appliance, prog.key, self._running_options)
        field = self._KINDS[self._kind][2]
        if ref and field in ref:
            self._cycle = {
                "target": ref[field],
                "start": datetime.now(timezone.utc),
                "duration": int(ref.get("runtime_seconds") or 0),
            }
            self._start_ramp_timer()
            self.async_write_ha_state()

    async def _on_program_finished(self, appliance: Appliance, key, value=None) -> None:
        field = self._KINDS[self._kind][2]
        # Linear mode: target already fetched at start, just settle it.
        if self._mode == CONF_CONSUMPTION_MODE_LINEAR and self._cycle:
            self._settle_cycle()
            self.async_write_ha_state()
            return
        # Step mode (or linear with no captured cycle): fetch the reference and add it.
        program_key = value or self._running_program
        if not program_key:
            return
        options = self._running_options if program_key == self._running_program else None
        ref = await self._async_fetch(appliance, program_key, options)
        if ref and field in ref:
            self._base += ref[field]
            self.async_write_ha_state()
            _LOGGER.debug("%s: added %.3f %s from program %s (total=%.3f)",
                          self.unique_id, ref[field], self._kind, program_key, self._base)
