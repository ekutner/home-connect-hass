"""Provides device triggers for Home Connect New."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.automation import (AutomationActionType,
                                                 AutomationTriggerInfo)
from homeassistant.components.device_automation import \
    DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import \
    event as event_trigger
from homeassistant.components.homeassistant.triggers import \
    state as state_trigger
from homeassistant.const import (CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM,
                                 CONF_TYPE)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, TRIGGERS_CONFIG

# TODO specify your supported trigger types.

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGERS_CONFIG.keys()),
    }
)

async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Home Connect New devices."""
    #registry = await entity_registry.async_get_registry(hass)
    triggers = []

    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN
    }
    for trigger_type in TRIGGERS_CONFIG.keys():
        triggers.append({**base_trigger, CONF_TYPE: trigger_type})

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    trigger_type = config[CONF_TYPE]

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                "key": TRIGGERS_CONFIG[trigger_type]["key"],
                "value": TRIGGERS_CONFIG[trigger_type]["value"]
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )