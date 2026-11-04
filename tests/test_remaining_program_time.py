"""Remaining-program timestamps using real Home Connect callback delivery."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from home_connect_async import Appliance, Events, HomeConnect
from home_connect_async.appliance import Option, Program

from custom_components.home_connect_alt import sensor as sensor_module


KEY = "BSH.Common.Option.RemainingProgramTime"


class Settings:
    hass = None

    def __init__(self, device_class="timestamp"):
        self.device_class = device_class

    def has_entity_setting(self, key, setting):
        return setting == "class"

    def get_entity_setting(self, key, setting, default=None):
        return self.device_class if setting == "class" else default


class RemainingProgramTimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.option = Option(key=KEY, value=9900, type="Int", unit="seconds")
        self.program = Program(
            key="Dishcare.Dishwasher.Program.Auto2", options={KEY: self.option}
        )
        self.appliance = Appliance(
            name="Test",
            brand="Bosch",
            vib="",
            connected=True,
            type="Dishwasher",
            enumber="",
            haId="bosch-test",
            uri="",
            active_program=self.program,
        )
        homeconnect = await HomeConnect.async_create(
            SimpleNamespace(), delayed_load=True
        )
        self.appliance._callbacks = homeconnect._callbacks
        self.sensor = sensor_module.ProgramOptionSensor(self.appliance, KEY, Settings())
        self.sensor.async_write_ha_state = Mock()
        await self.sensor.async_added_to_hass()
        self.now = datetime(2026, 10, 26, 10, 27, 20, tzinfo=timezone.utc)
        clock = SimpleNamespace(
            now=lambda tz: SimpleNamespace(astimezone=lambda: self.now)
        )
        self.clock = patch.object(sensor_module, "datetime", clock)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    async def asyncTearDown(self):
        self.sensor._key = KEY
        await self.sensor.async_will_remove_from_hass()

    async def event(self, key, value=None):
        await self.appliance._callbacks.async_broadcast_event(
            self.appliance, key, value
        )

    async def test_stale_generic_event_does_not_reanchor_finish(self):
        first = self.sensor.native_value
        self.assertEqual(datetime(2026, 10, 26, 13, 12, 20, tzinfo=timezone.utc), first)
        self.now += timedelta(seconds=65)
        await self.event(Events.DATA_CHANGED)
        self.assertEqual(first, self.sensor.native_value)
        self.option.value = 9840
        await self.event(KEY, 9840)
        self.assertEqual(self.now + timedelta(seconds=9840), self.sensor.native_value)

    async def test_full_snapshot_can_update_countdown_without_specific_event(self):
        first = self.sensor.native_value
        self.now += timedelta(minutes=2)
        replacement = Option(key=KEY, value=9840, type="Int", unit="seconds")
        self.appliance.active_program = Program(
            key=self.program.key, options={KEY: replacement}
        )
        await self.event(Events.DATA_CHANGED)
        self.assertNotEqual(first, self.sensor.native_value)
        self.assertEqual(self.now + timedelta(seconds=9840), self.sensor.native_value)

    async def test_new_snapshot_with_unchanged_countdown_is_a_new_sample(self):
        self.sensor.native_value
        self.now += timedelta(minutes=2)
        replacement = Option(key=KEY, value=9900, type="Int", unit="seconds")
        self.appliance.active_program = Program(
            key=self.program.key, options={KEY: replacement}
        )
        await self.event(Events.DATA_CHANGED)
        self.assertEqual(self.now + timedelta(seconds=9900), self.sensor.native_value)

    async def test_program_context_and_connection_reset_the_cached_finish(self):
        first = self.sensor.native_value
        self.appliance.connected = False
        await self.event(Events.CONNECTION_CHANGED, False)
        self.assertIsNone(self.sensor.native_value)
        self.now += timedelta(minutes=1)
        self.appliance.connected = True
        await self.event(Events.CONNECTION_CHANGED, True)
        self.assertEqual(first + timedelta(minutes=1), self.sensor.native_value)
        self.appliance.active_program = None
        self.appliance.selected_program = Program(
            key="Other", options={KEY: Option(key=KEY, value=1800)}
        )
        await self.event(Events.PROGRAM_SELECTED, "Other")
        self.assertEqual(self.now + timedelta(minutes=30), self.sensor.native_value)

    async def test_other_timestamp_options_keep_existing_calculation(self):
        key = "BSH.Common.Option.StartInRelative"
        self.sensor._key = key
        self.program.options[key] = Option(
            key=key, value=30, type="Int", unit="seconds"
        )
        self.assertEqual(self.now + timedelta(seconds=30), self.sensor.native_value)
        self.now += timedelta(seconds=10)
        self.assertEqual(self.now + timedelta(seconds=30), self.sensor.native_value)
