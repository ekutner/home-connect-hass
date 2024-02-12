from __future__ import annotations
import logging
import datetime
from  homeassistant.components.time import TimeEntity, time, timedelta
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events, ConditionalLogger as CL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum, Configuration
from .const import DOMAIN

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
                        if conf.get_entity_setting(option.key, "type") == "DelayedOperation":
                            device = DelayedOperationTime(appliance, option.key, conf, option)
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
        self._current:time = self.init_time()

    @property
    def name_ext(self) -> str|None:
        return self._hc_obj.name if self._hc_obj.name else "Delayed operation"

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:clock-outline')


    @property
    def available(self) -> bool:

        # We must have the program run time for this entity to work
        available = super().program_option_available and self.get_program_run_time()

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
        if self._appliance.startonly_options and self._key in self._appliance.startonly_options:
            self._current = self.adjust_time(self._current, True)
        else:
            self._current = self.adjust_time(self._current, False)
        return self._current

    def adjust_time(self, t:time, set_option:bool) -> time:

        now = datetime.datetime.now()
        endtime = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=t.hour, minute=t.minute)

        if (now.hour > endtime.hour) or (now.hour == endtime.hour and now.minute > endtime.minute):
            # if the specified time is smaller than now then it means tomorrow
            endtime += datetime.timedelta(days=1)

        program_run_time = self.get_program_run_time()

        if endtime < now + timedelta(seconds=program_run_time):
            # the set end time is closer then the program run time so change it to the expected end of the program
            # and cancel the set delay option
            endtime = now + timedelta(seconds=program_run_time)
            #self._current = time(hour=endtime.hour, minute=endtime.minute)
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
        inittime = datetime.datetime.now() + timedelta(minutes=1)
        t = time(hour=inittime.hour, minute=inittime.minute)
        return self.adjust_time(t, False)

    def get_program_run_time(self) -> int|None:

        # There seems to be a bug in HC which returns the remaining time for the previous program when there isn't an dactive one
        prog_time_option = self._appliance.get_applied_program_option("BSH.Common.Option.RemainingProgramTime")
        if prog_time_option and self._appliance.active_program:
            return prog_time_option.value

        prog_time_option = self._appliance.get_applied_program_option("BSH.Common.Option.FinishInRelative")
        if prog_time_option:
            return prog_time_option.value

        prog_time_option = self._appliance.get_applied_program_option("BSH.Common.Option.EstimatedTotalProgramTime")
        if prog_time_option:
            return prog_time_option.value

        return None


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        # reset the end time clock when a different program is selected
        if key == Events.PROGRAM_SELECTED:
            self._current = self.init_time()
        self.async_write_ha_state()