"""The Home Connect New integration."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime

from home_connect_async.appliance import Appliance

import voluptuous as vol
import homeassistant

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    storage,
    device_registry as dr,
    entity_registry as er
)
from homeassistant.helpers.typing import ConfigType

from . import api, config_flow
from .const import *
from .services import Services

from home_connect_async import HomeConnect

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Optional(CONF_SIMULATE, default=False): cv.boolean
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.NUMBER, Platform.BUTTON, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Home Connect New component."""
    hass.data[DOMAIN] = config[DOMAIN]

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    simulate = conf[CONF_SIMULATE]

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        HomeConnectOauth2Impl(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            f'{SIM_HOST if simulate else API_HOST}{ENDPOINT_AUTHORIZE}',
            f'{SIM_HOST if simulate else API_HOST}{ENDPOINT_TOKEN}',
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    """Set up Home Connect New from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    conf = hass.data[DOMAIN]
    simulate = conf[CONF_SIMULATE]
    host = SIM_HOST if simulate else API_HOST

    # If using an aiohttp-based API lib
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session, host
    )

    hc:HomeConnect = await async_load_from_cache(hass, auth)
    if not hc:
        # Create normally if failed to create from cache
        hc = await HomeConnect.async_create(auth, delayed_load=True)

    conf[entry.entry_id] = auth
    conf['homeconnect'] = hc
    conf['services'] = register_services(hass, hc)

    #region internal event hadlers
    async def async_delayed_update_cache(delay:float = 0):
        asyncio.sleep(delay)
        await async_save_to_cache(hass, hc)

    async def on_data_loaded(hc:HomeConnect):
        # Save the state of the HomeConnect object to cache
        await async_save_to_cache(hass, hc)
        hc.register_callback(on_device_removed, "DEPAIRED")
        hc.register_callback(on_device_added, "PAIRED")
        hc.subscribe_for_updates()

    async def on_device_added(appliance:Appliance, event:str):
        await async_save_to_cache(hass, hc)

    async def on_device_removed(appliance:Appliance, event:str):
        devreg = dr.async_get(hass)
        device = devreg.async_get_device({(DOMAIN, appliance.haId.lower().replace('-','_'))})
        devreg.async_remove_device(device.id)

        # We need to wait for the appliance to be removed from the HomeConnect data
        # this is not 100% fail-safe but good enough for a cache
        asyncio.create_task(async_delayed_update_cache(30))

    #endregion


    # Setup all the callback listeners before starting to load the data
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    register_events_publisher(hass, hc)

    # Continue loading the HomeConnect data model and set the callback to be notified when done
    hc.continue_data_load(on_complete=on_data_loaded)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    conf = hass.data[DOMAIN]
    hc:HomeConnect = conf['homeconnect']
    hc.close()

    await async_save_to_cache(hass, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_load_from_cache(hass:HomeAssistant, auth:api.AsyncConfigEntryAuth) -> HomeConnect | None:
    cache = storage.Store(hass, version=1, key=f"{DOMAIN}_cache", private=True)
    try:
        refresh = HomeConnect.RefreshMode.ALL
        json_data = None

        cached_data = await cache.async_load()
        if cached_data:
            json_data = cached_data.get('json_data')

            last_update = datetime.fromisoformat(cached_data['last_update'])
            delta = (datetime.now()-last_update).total_seconds()
            if delta < 120000:
                refresh = HomeConnect.RefreshMode.NOTHING
            elif delta < 3600*24*30:
                refresh = HomeConnect.RefreshMode.DYNAMIC_ONLY

        hc:HomeConnect = await HomeConnect.async_create(auth, json_data=json_data, refresh=refresh, delayed_load=True)
        return hc
    except Exception as ex:
        # If there is any exception when creating the object from cache just create it normally
        _LOGGER.debug("Exception while reading cached data", exc_info=ex)
        return None

async def async_save_to_cache(hass:HomeAssistant, hc:HomeConnect, cache:storage.Store=None) -> None:
    try:
        if not cache:
            cache = storage.Store(hass, version=1, key=f"{DOMAIN}_cache", private=True)
        if hc:
            cached_data = {
                'last_update': datetime.now().isoformat(),
                'json_data': hc.to_json()
            }
            await cache.async_save(cached_data)
        else:
            await cache.async_remove()
    except Exception as ex:
        _LOGGER.warning("Exception when saving to cache", exc_info=ex)
        pass

def register_services(hass:HomeAssistant, hc:HomeConnect) -> Services:
    services = Services(hass, hc)

    select_program_scema = vol.Schema(
        {
            vol.Required('device_id'): cv.string,
            vol.Required('program_key'): cv.string,
            vol.Optional('options'): vol.Schema(
                [
                    {
                        vol.Required('key'): cv.string,
                        vol.Required('value'): cv.string
                    }
                ]
            )
        }
    )
    hass.services.async_register(DOMAIN, "select_program", services.async_select_program, schema=select_program_scema)

    start_stop_program_schema = vol.Schema(
        {
            vol.Required('device_id'): cv.string
        }
    )
    hass.services.async_register(DOMAIN, "start_program", services.async_start_program, schema=start_stop_program_schema)
    hass.services.async_register(DOMAIN, "stop_program", services.async_stop_program, schema=start_stop_program_schema)

    return services


def register_events_publisher(hass:HomeAssistant, hc:HomeConnect):
    device_reg = dr.async_get(hass)

    async def async_handle_event(appliance:Appliance, key:str, value:str):
        device = device_reg.async_get_device({(DOMAIN, appliance.haId.lower().replace('-','_'))})
        event_data = {
            "device_id": device.id,
            "key": key,
            "value": value
        }
        hass.bus.async_fire(f"{DOMAIN}_event", event_data)


    async def register_appliance(appliance:Appliance, event:str=None):
        appliance.register_callback(async_handle_event, '*.event.*')

        for event in PUBLISHED_EVENTS:
            appliance.register_callback(async_handle_event, event)


    # for appliance in hc.appliances.values():
    #     async_register(appliance)
    hc.register_callback(register_appliance, "PAIRED")


class HomeConnectOauth2Impl(config_entry_oauth2_flow.LocalOAuth2Implementation):
    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Home Connect Appliances"


