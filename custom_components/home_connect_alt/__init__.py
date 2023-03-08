"""The Home Connect New integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import voluptuous as vol
from home_connect_async import Appliance, HomeConnect, Events, ConditionalLogger
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import Event, HomeAssistant, HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import storage
from homeassistant.helpers.typing import ConfigType

from . import api, config_flow
from .common import Configuration
from .const import *
from .services import Services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Optional(CONF_API_HOST, default=None): vol.Any(str, None),
                vol.Optional(CONF_CACHE, default=True): cv.boolean,
                vol.Optional(CONF_LANG, default=None): vol.Any(str, None),
                vol.Optional(CONF_SENSORS_TRANSLATION, default=None): vol.Any(str, None),
                vol.Optional(CONF_NAME_TEMPLATE, default=None): vol.Any(str, None),
                vol.Optional(CONF_LOG_MODE, default=None): vol.Any(int, None),
                vol.Optional(CONF_ENTITY_SETTINGS, default={}): vol.Any(dict, None)
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# For your initial PR, limit it to 1 platform.
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.NUMBER, Platform.BUTTON, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Home Connect New component."""
    hass.data[DOMAIN] = config[DOMAIN]

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    api_host = conf[CONF_API_HOST] if conf[CONF_API_HOST] else DEFAULT_API_HOST

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        HomeConnectOauth2Impl(
            hass,
            DOMAIN,
            conf[CONF_CLIENT_ID],
            conf[CONF_CLIENT_SECRET],
            f'{api_host}{ENDPOINT_AUTHORIZE}',
            f'{api_host}{ENDPOINT_TOKEN}',
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
    api_host = conf[CONF_API_HOST] if conf[CONF_API_HOST] else DEFAULT_API_HOST
    lang = conf[CONF_LANG] # if conf[CONF_LANG] != "" else None
    use_cache = conf[CONF_CACHE]
    logmode = conf[CONF_LOG_MODE] if conf[CONF_LOG_MODE] else ConditionalLogger.LogMode.REQUESTS
    Configuration.set_global_config(conf)

    # If using an aiohttp-based API lib
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session, api_host
    )

    # homeconnect:HomeConnect = None
    # if use_cache:
    #     homeconnect = await async_load_from_cache(hass, auth, lang)
    # if not homeconnect:
    #     # Create normally if failed to create from cache
    #     try:
    #         homeconnect = await HomeConnect.async_create(auth, delayed_load=True, lang=lang)
    #         _LOGGER.debug("The HomeConnect object was created from scratch (without cache)")
    #     except HomeConnectError as ex:
    #         _LOGGER.warning("Failed to create the HomeConnect object", exc_info=ex)
    #         return False
    ConditionalLogger.mode(logmode)
    homeconnect = await HomeConnect.async_create(auth, delayed_load=True, lang=lang)

    conf[entry.entry_id] = auth
    conf['homeconnect'] = homeconnect
    conf['services'] = register_services(hass, homeconnect)

    #region internal event hadlers
    # async def async_delayed_update_cache(delay:float = 0):
    #     asyncio.sleep(delay)
    #     await async_save_to_cache(hass, homeconnect)

    async def on_data_loaded(homeconnect:HomeConnect):
        # Save the state of the HomeConnect object to cache
        # if use_cache:
        #     await async_save_to_cache(hass, homeconnect)
        # else:
        #     _LOGGER.debug("Not saving to cache, it is disabled")
        homeconnect.register_callback(on_device_removed, Events.DEPAIRED)
        #homeconnect.register_callback(on_device_added, [Events.PAIRED, Events.DATA_CHANGED] )
        homeconnect.subscribe_for_updates()

    async def on_data_load_error(homeconnect:HomeConnect, ex:Exception):
        _LOGGER.error("Failed to load data for the HomeConnect object", exc_info=ex)

    # async def on_device_added(appliance:Appliance, event:str):
    #     if use_cache:
    #         await async_save_to_cache(hass, homeconnect)
    #     else:
    #         _LOGGER.debug("Not saving to cache, it is disabled")

    async def on_device_removed(appliance:Appliance):
        devreg = dr.async_get(hass)
        device = devreg.async_get_device({(DOMAIN, appliance.haId.lower().replace('-','_'))})
        devreg.async_remove_device(device.id)

        # We need to wait for the appliance to be removed from the HomeConnect data
        # this is not 100% fail-safe but good enough for a cache
        # asyncio.create_task(async_delayed_update_cache(30))

    #endregion


    # Setup all the callback listeners before starting to load the data

    #hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    register_events_publisher(hass, homeconnect)

    # Continue loading the HomeConnect data model and set the callback to be notified when done
    homeconnect.start_load_data_task(on_complete=on_data_loaded, on_error= on_data_load_error)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    conf = hass.data[DOMAIN]
    homeconnect:HomeConnect = conf['homeconnect']
    homeconnect.close()

    # await async_save_to_cache(hass, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_load_from_cache(hass:HomeAssistant, auth:api.AsyncConfigEntryAuth, lang:str|None) -> HomeConnect | None:
    """ Helper function to load cached Home Connect data for storage """
    cache = storage.Store(hass, version=1, key=f"{DOMAIN}_cache", private=True)
    try:
        refresh = HomeConnect.RefreshMode.ALL
        json_data = None

        cached_data = await cache.async_load()
        if cached_data:
            json_data = cached_data.get('json_data')

            last_update = datetime.fromisoformat(cached_data['last_update'])
            delta = (datetime.now()-last_update).total_seconds()
            if delta < 60:
                refresh = HomeConnect.RefreshMode.NOTHING
            elif delta < 3600*24*30:
                refresh = HomeConnect.RefreshMode.DYNAMIC_ONLY

        homeconnect:HomeConnect = await HomeConnect.async_create(auth, json_data=json_data, refresh=refresh, delayed_load=True, lang=lang)
        _LOGGER.debug("Loaded HomeConnect from cache")
        return homeconnect
    except Exception as ex:
        # If there is any exception when creating the object from cache then clear the cache and continue
        await cache.async_remove()
        _LOGGER.debug("Exception while loading HomeConnect from cache, clearing cache and contiuing", exc_info=ex)
        return None

async def async_save_to_cache(hass:HomeAssistant, homeconnect:HomeConnect, cache:storage.Store=None) -> None:
    """ Helper function to save the Home Connect data to Home Assistant storage """
    try:
        if not cache:
            cache = storage.Store(hass, version=1, key=f"{DOMAIN}_cache", private=True)
        if homeconnect:
            cached_data = {
                'last_update': datetime.now().isoformat(),
                'json_data': homeconnect.to_json()
            }
            await cache.async_save(cached_data)
            _LOGGER.debug("Saved HomeConnect to cache")
        else:
            await cache.async_remove()
            _LOGGER.debug("Cleared HomeConnect from cache")

    except Exception as ex:
        _LOGGER.debug("Exception when saving HomeConnect to cache", exc_info=ex)


def register_services(hass:HomeAssistant, homeconnect:HomeConnect) -> Services:
    """ Register the services offered by this integration """
    services = Services(hass, homeconnect)

    select_program_scema = vol.Schema(
        {
            vol.Required('device_id'): cv.string,
            vol.Required('program_key'): cv.string,
            vol.Optional('validate', default=True): cv.boolean,
            vol.Optional('options'): vol.Schema(
                [
                    {
                        vol.Required('key'): cv.string,
                        vol.Required('value'): vol.Any(str, int, float, bool)
                    }
                ]
            )
        }
    )
    hass.services.async_register(DOMAIN, "select_program", services.async_select_program, schema=select_program_scema)

    start_program_scema = vol.Schema(
        {
            vol.Required('device_id'): cv.string,
            vol.Optional('program_key'): cv.string,
            vol.Optional('validate', default=True): cv.boolean,
            vol.Optional('options'): vol.Schema(
                [
                    {
                        vol.Required('key'): cv.string,
                        vol.Required('value'): vol.Any(str, int, float, bool)
                    }
                ]
            )
        }
    )
    hass.services.async_register(DOMAIN, "start_program", services.async_start_program, schema=start_program_scema)

    stop_program_schema = vol.Schema(
        {
            vol.Required('device_id'): cv.string
        }
    )
    hass.services.async_register(DOMAIN, "stop_program", services.async_stop_program, schema=stop_program_schema)

    set_program_option_schema = vol.Schema(
        {
            vol.Required('device_id'): cv.string,
            vol.Required('key'): cv.string,
            vol.Required('value'): vol.Any(str, int, float, bool)
        }
    )
    hass.services.async_register(DOMAIN, "set_program_option", services.async_set_program_option, schema=set_program_option_schema)

    apply_setting_schema = vol.Schema(
        {
            vol.Required('device_id'): cv.string,
            vol.Required('key'): cv.string,
            vol.Required('value'): vol.Any(str, int, float, bool)
        }
    )
    hass.services.async_register(DOMAIN, "apply_setting", services.async_apply_setting, schema=apply_setting_schema)

    return services


def register_events_publisher(hass:HomeAssistant, homeconnect:HomeConnect):
    """ Register for publishing events that are offered by this integration """
    device_reg = dr.async_get(hass)
    last_event = { 'key': None, 'value': None}    # Used to filter out duplicate events

    async def async_handle_event(appliance:Appliance, key:str, value:str):
        if key != last_event['key'] or value != last_event['value']:
            last_event['key'] = key
            last_event['value'] = value
            device = device_reg.async_get_device({(DOMAIN, appliance.haId.lower().replace('-','_'))})
            event_data = {
                "device_id": device.id,
                "key": key,
                "value": value
            }
            hass.bus.async_fire(f"{DOMAIN}_event", event_data)
            _LOGGER.debug("Published event to Home Assistant event bus: %s = %s", key, str(value))
        else:
            _LOGGER.debug("Skipped publishing of duplicate event to Home Assistant event bus: %s = %s", key, str(value))


    def register_appliance(appliance:Appliance):
        for event in PUBLISHED_EVENTS:
            appliance.register_callback(async_handle_event, event)


    homeconnect.register_callback(register_appliance, [Events.PAIRED, Events.CONNECTED])
    for appliance in homeconnect.appliances.values():
        register_appliance(appliance)



class HomeConnectOauth2Impl(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """" Implement that OAuth2 class """
    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Home Connect Appliances"
