from __future__ import annotations
import logging
import datetime
from datetime import time, timedelta
from  homeassistant.components.time import TimeEntity
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events, ConditionalLogger as CL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_registry import async_get

from .common import InteractiveEntityBase, EntityManager, is_boolean_enum, Configuration, find_delayed_operation_option
from .const import CONF_DELAYED_OPS, CONF_DELAYED_OPS_ABSOLUTE_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    entry_conf:Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = entry_conf["homeconnect"]
    entity_manager = EntityManager(async_add_entities, "Time")


    def add_appliance(appliance:Appliance) -> None:
        conf = entry_conf.get_config()

        delayed_option = find_delayed_operation_option(appliance, conf)
        if delayed_option \
            and entry_conf[CONF_DELAYED_OPS]==CONF_DELAYED_OPS_ABSOLUTE_TIME:
            device = DelayedOperationTime(appliance, delayed_option.key, conf, delayed_option)
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
    """ Class for setting a delayed start by an absolute time.

    The time is interpreted using the appliance's native delay option: the program start
    time for appliances that accept a start delay and the program finish time for those that
    accept a finish delay.
    """
    should_poll = True

    def __init__(self, appliance: Appliance, key: str = None, conf: dict = None, hc_obj = None) -> None:
        super().__init__(appliance, key, conf, hc_obj)
        self._current:time = None
    @property
    def name_ext(self) -> str|None:
        # Name the control after what the user actually sets, so it stays consistent with its
        # operation regardless of the (possibly missing or inconsistent) name the API returns:
        # appliances with a finish delay set the program end time, all others set the start time.
        if self._key and "FinishInRelative" in self._key:
            return "End time"
        return "Start time"

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', 'mdi:clock-outline')


    @property
    def available(self) -> bool:

        available = super().program_option_available

        if not available:
            self._appliance.clear_startonly_option(self._key)
        return available

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        self._current = self.adjust_time(value, True)
        # Notify related entities (e.g. the "Cancel delayed start" button) that a delay is now armed
        await self._appliance._callbacks.async_broadcast_event(self._appliance, Events.DATA_CHANGED)
        self.async_write_ha_state()

    @property
    def native_value(self) -> time|None:
        """Return the entity value to represent the entity state.

        No delay is scheduled unless the user has armed one. While a delay is armed the value
        is kept in sync with the wall clock; when nothing is armed the entity has no value and
        is shown as "unknown", so it's clear that no delayed start/finish is set.
        """
        if self._appliance.startonly_options and self._key in self._appliance.startonly_options:
            if self._current is None:
                self._current = self.init_time()
            self._current = self.adjust_time(self._current, True)
            return self._current

        self._current = None
        return None


    def adjust_time(self, t:time, set_option:bool) -> time|None:
        """ Adjust the time state and set the delay option when required.

        The time represents the appliance's native delayed-operation moment: the start time
        for appliances that accept a start delay and the finish time for appliances that
        accept a finish delay. The delay sent to the appliance is simply the number of
        seconds from now until that time, so no program run time estimate is needed.
        """

        now = datetime.datetime.now()
        target = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=t.hour, minute=t.minute)

        if target <= now:
            # a time earlier than now is interpreted as tomorrow
            target += datetime.timedelta(days=1)

        if set_option:
            delay = (target - now).total_seconds()

            # round the delay to the stepsize and clamp it to the option's allowed range
            option = self._appliance.get_applied_program_available_option(self._key)
            stepsize = option.stepsize if option and option.stepsize and option.stepsize != 0 else 60
            delay = int(delay/stepsize)*stepsize
            if option:
                if option.min is not None and delay < option.min:
                    delay = option.min
                if option.max is not None and delay > option.max:
                    delay = option.max

            _LOGGER.debug("Setting startonly option %s to: %i", self._key, delay)
            self._appliance.set_startonly_option(self._key, delay)

        return time(hour=target.hour, minute=target.minute)

    def init_time(self) -> time:
        """ Initialize the time state """
        inittime = datetime.datetime.now() + timedelta(minutes=1)
        t = time(hour=inittime.hour, minute=inittime.minute)
        return self.adjust_time(t, False)


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        # An armed delay is kept as-is across program changes (it applies to whatever program is
        # started next); when nothing is armed native_value reports "unknown". So just refresh.
        self.async_write_ha_state()