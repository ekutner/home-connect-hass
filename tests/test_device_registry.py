"""Device lookup behavior across Home Assistant registry versions."""

import socket
import tempfile
import unittest
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from home_connect_async import Appliance, Events, HomeConnect
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components import home_connect_alt as integration


class RegistryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="home-connect-test-")
        self.addCleanup(self.directory.cleanup)
        self.hass = HomeAssistant(self.directory.name)
        self.hass.config.skip_pip = True
        self.hass.config_entries = ConfigEntries(self.hass, {})
        for name in ("connect", "connect_ex", "sendto", "sendmsg"):
            guard = patch.object(
                socket.socket, name, side_effect=AssertionError("network disabled")
            )
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(
            socket, "getaddrinfo", side_effect=AssertionError("DNS disabled")
        )
        guard.start()
        self.addCleanup(guard.stop)
        loader.async_setup(self.hass)
        self.assertTrue(await async_load_base_functionality(self.hass))
        self.entry = self.make_entry("first")
        self.other_entry = self.make_entry("second")
        self.registry = dr.async_get(self.hass)
        self.hc = await HomeConnect.async_create(SimpleNamespace(), delayed_load=True)
        self.appliance = Appliance(
            name="Test",
            brand="Bosch",
            vib="",
            connected=True,
            type="Dishwasher",
            enumber="",
            haId="123-SYNTHETIC",
            uri="",
        )
        self.appliance._callbacks = self.hc._callbacks
        self.hc.appliances = {self.appliance.haId: self.appliance}
        self.events = []
        self.addCleanup(
            self.hass.bus.async_listen(
                "home_connect_alt_event", lambda event: self.events.append(event.data)
            )
        )

    async def asyncTearDown(self):
        await self.hass.async_stop(force=True)
        await self.hass.async_block_till_done()

    def make_entry(self, name):
        entry = ConfigEntry(
            domain="home_connect_alt",
            title=name,
            data={},
            options={},
            source="user",
            version=1,
            minor_version=1,
            unique_id=name,
            discovery_keys=MappingProxyType({}),
            subentries_data=(),
        )
        self.hass.config_entries._entries[entry.entry_id] = entry
        return entry

    def device(self, identifier, entry):
        return self.registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("home_connect_alt", identifier)},
            name="Test",
        )

    async def test_events_use_the_owning_entry_for_both_identifiers(self):
        identifier = self.appliance.normalized_haId
        other = self.device(identifier, self.other_entry)
        own = self.device(identifier, self.entry)
        self.assertNotEqual(other.id, own.id)
        integration.register_events_publisher(self.hass, self.hc, self.entry.entry_id)
        key = integration.PUBLISHED_EVENTS[-1]
        await self.hc._callbacks.async_broadcast_event(self.appliance, key, "open")
        await self.hass.async_block_till_done()
        self.assertEqual(own.id, self.events[-1]["device_id"])

        self.registry.async_remove_device(own.id)
        safe_id = integration.EntityBase.get_safe_haID(self.hass, self.appliance)
        self.device(safe_id, self.other_entry)
        fallback = self.device(safe_id, self.entry)
        await self.hc._callbacks.async_broadcast_event(self.appliance, key, "closed")
        await self.hass.async_block_till_done()
        self.assertEqual(fallback.id, self.events[-1]["device_id"])

    async def test_depair_ignores_other_entry_and_missing_device(self):
        identifier = self.appliance.normalized_haId
        other = self.device(identifier, self.other_entry)
        own = self.device(identifier, self.entry)
        session = SimpleNamespace(async_ensure_token_valid=AsyncMock())
        loaded = {}
        with (
            patch.object(
                integration.config_entry_oauth2_flow,
                "async_get_config_entry_implementation",
                AsyncMock(return_value=object()),
            ),
            patch.object(
                integration.config_entry_oauth2_flow,
                "OAuth2Session",
                return_value=session,
            ),
            patch.object(HomeConnect, "async_create", AsyncMock(return_value=self.hc)),
            patch.object(
                HomeConnect,
                "start_load_data_task",
                side_effect=lambda **kwargs: loaded.update(kwargs),
            ),
            patch.object(HomeConnect, "subscribe_for_updates"),
            patch.object(
                integration.aiohttp_client,
                "async_get_clientsession",
                return_value=Mock(),
            ),
            patch.object(
                self.hass.config_entries, "async_forward_entry_setups", AsyncMock()
            ),
        ):
            self.assertTrue(await integration.async_setup(self.hass, {}))
            self.assertTrue(await integration.async_setup_entry(self.hass, self.entry))
            await loaded["on_complete"](self.hc)
            await self.hc._callbacks.async_broadcast_event(
                self.appliance, Events.DEPAIRED
            )
            await self.hc._callbacks.async_broadcast_event(
                self.appliance, Events.DEPAIRED
            )
        self.assertIsNone(self.registry.async_get(own.id))
        self.assertIsNotNone(self.registry.async_get(other.id))

    def test_legacy_registry_lookup(self):
        expected = object()
        lookup = Mock(return_value=expected)
        registry = SimpleNamespace(async_get_device=lookup)
        identifier = ("home_connect_alt", "device")
        self.assertIs(
            expected,
            integration._get_device_by_identifier(registry, identifier, "entry"),
        )
        lookup.assert_called_once_with({identifier})
