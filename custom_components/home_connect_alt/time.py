from __future__ import annotations
import logging
import datetime
from  homeassistant.components.time import TimeEntity, time, timedelta
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events, ConditionalLogger as CL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_registry import async_get

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum, Configuration
from .const import CONF_DELAYED_OPS, CONF_DELAYED_OPS_ABSOLUTE_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    entry_conf:Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = entry_conf["homeconnect"]
    entity_manager = EntityManager(async_add_entities)


    def add_appliance(appliance:Appliance) -> None:
        conf = entry_conf.get_config()

        if appliance.available_programs:
            for program in appliance.available_programs.values():
                if program.options:
                    for option in program.options.values():
                        if conf.get_entity_setting(option.key, "type") == "DelayedOperation" \
                            and entry_conf[CONF_DELAYED_OPS]==CONF_DELAYED_OPS_ABSOLUTE_TIME \
                            and DelayedOperationTime.has_program_run_time(appliance):
                            device = DelayedOperationTime(appliance, option.key, conf, option)
                            # remove the SELECT delayed operation entity if it exists
                            reg = async_get(hass)
                            select_entity = reg.async_get_entity_id("select", DOMAIN, device.unique_id)
                            if select_entity:
                                reg.async_remove(select_entity)
                            entity_manager.add(device)

        entity_manager.register()

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED, Events.PROGRAM_STARTED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class DelayedOperationTime(InteractiveEntityBase, TimeEntity):
    """ Class for setting delayed start by the program end time """
    should_poll = True

    def __init__(self, appliance: Appliance, key: str = None, conf: dict = None, hc_obj = None) -> None:
        super().__init__(appliance, key, conf, hc_obj)
        self._current:time = None
    @property
    def name_ext(self) -> str|None:
        return self._hc_obj.name if self._hc_obj.name else "Delayed operation"

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:clock-outline')


    @property
    def available(self) -> bool:

        # We must have the program run time for this entity to work
        available = super().program_option_available and self.get_program_run_time(self._appliance) is not None

        if not available:
            self._appliance.clear_startonly_option(self._key)
        return available

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        self._current = self.adjust_time(value, True)

        #self.async_write_ha_state()

    @property
    def native_value(self) -> time:
        """Return the entity value to represent the entity state."""
        if self._current is None:
            self._current = self.init_time()

        if self._appliance.startonly_options and self._key in self._appliance.startonly_options:
            self._current = self.adjust_time(self._current, True)
        else:
            self._current = self.adjust_time(self._current, False)
        return self._current


    def adjust_time(self, t:time, set_option:bool) -> time|None:
        """ Adjust the time state when required """

        now = datetime.datetime.now()
        endtime = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=t.hour, minute=t.minute)

        if (now.hour > endtime.hour) or (now.hour == endtime.hour and now.minute > endtime.minute):
            # if the specified time is smaller than now then it means tomorrow
            endtime += datetime.timedelta(days=1)

        program_run_time = self.get_program_run_time(self._appliance)

        if not program_run_time:
            return None

        if endtime < now + timedelta(seconds=program_run_time):
            # the set end time is closer then the program run time so change it to the expected end of the program
            # and cancel the set delay option
            endtime = now + timedelta(seconds=program_run_time)
            #self._current = time(hour=endtime.hour, minute=endtime.minute)
            if self._appliance.startonly_options and self._key in self._appliance.startonly_options:
                _LOGGER.debug("Clearing startonly option %s", self._key)
            self._appliance.clear_startonly_option(self._key)
        elif set_option:
            delay = (endtime-now).total_seconds()
            if "StartInRelative" in self._key:
                delay -= program_run_time

            # round the delay to the stepsize
            stepsize_option = self._appliance.get_applied_program_available_option(self._key)
            stepsize = stepsize_option.stepsize if stepsize_option else 60
            delay = int(delay/stepsize)*stepsize

            _LOGGER.debug("Setting startonly option %s to: %i", self._key, delay)
            self._appliance.set_startonly_option(self._key, delay)

        return time(hour=endtime.hour, minute=endtime.minute)

    def init_time(self) -> time:
        """ Initialize the time state """
        inittime = datetime.datetime.now() + timedelta(minutes=1)
        t = time(hour=inittime.hour, minute=inittime.minute)
        return self.adjust_time(t, False)

    @classmethod
    def get_program_run_time(cls, appliance:Appliance) -> int|None:
        """ Try to get the expected run time of the selected program or the remaining time of the running program """
        time_option_keys = [
            "BSH.Common.Option.RemainingProgramTime",
            "BSH.Common.Option.FinishInRelative",
            "BSH.Common.Option.EstimatedTotalProgramTime",
        ]

        for key in time_option_keys:
            o = appliance.get_applied_program_option(key)
            if o:
                return o.value

        return None

    @classmethod
    def has_program_run_time(cls, appliance:Appliance) ->bool:
        """ Check if it's possible to get a program run time estimate """
        return cls.get_program_run_time(appliance) is not None


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        # reset the end time clock when a different program is selected
        if key == Events.PROGRAM_SELECTED or "RemoteControlStartAllowed" in key:
            self._current = self.init_time()
        self.async_write_ha_state()