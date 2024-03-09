"""Constants for the Home Connect Alt integration."""


DOMAIN = "home_connect_alt"
NAME = "Home Connect Alt"
DEFAULT_API_HOST = "https://api.home-connect.com"

ENDPOINT_AUTHORIZE = "/security/oauth/authorize"
ENDPOINT_TOKEN = "/security/oauth/token"
SCOPES = "IdentifyAppliance Monitor Control Settings"
CONF_API_HOST = "api_host"
CONF_API_HOST_OPTIONS = [ "https://api.home-connect.com", "https://api.home-connect.cn" ]
# CONF_API_HOST_OPTIONS = [
#     {"label": "default", "value": "https://api.home-connect.com"},
#     {"label": "china", "value": "https://api.home-connect.cn"}
# ]
CONF_LANG = "language"
CONF_LANG_DEFAULT = "en-GB"
CONF_CACHE = "cache"
CONF_TRANSLATION_MODE = "translation_mode"
CONF_TRANSLATION_MODES = ["local", "server"]
CONF_TRANSLATION_MODE_SERVER = "server"
CONF_SENSORS_TRANSLATION = "sensor_value_translation"
CONF_NAME_TEMPLATE = "name_template"
CONF_NAME_TEMPLATE_DEFAULT = "$brand $appliance - $name"
CONF_LOG_MODE = "log_mode"
CONF_SSE_TIMEOUT = "sse_timeout"
CONF_SSE_TIMEOUT_DEFAULT = 15
CONF_ENTITY_SETTINGS = "entity_settings"
CONF_APPLIANCE_SETTINGS = "appliance_settings"
CONF_DELAYED_OPS = "delayed_ops"
CONF_DELAYED_OPS_DEFAULT = "default"
CONF_DELAYED_OPS_ABSOLUTE_TIME = "absolute_time"

HOME_CONNECT_DEVICE = {
    "identifiers": {(DOMAIN, "homeconnect")},
    "name": "Home Connect Service",
    "manufacturer": "BSH"
}

DEFAULT_SETTINGS = {
    CONF_ENTITY_SETTINGS: {
        "BSH.Common.Option.FinishInRelative": { "type": "DelayedOperation", "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.StartInRelative": { "type": "DelayedOperation", "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.ElapsedProgramTime": { "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.EstimatedTotalProgramTime": { "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.RemainingProgramTime": {"unit": None, "class": "timestamp" },
        "BSH.Common.Status.DoorState": { "type": "Boolean", "class": "door", "icon": None, "on_state": "BSH.Common.EnumType.DoorState.Open" },
        "Refrigeration.Common.Status.Door.Freezer": { "type": "Boolean", "class": "door", "icon": None, "on_state": "Refrigeration.Common.EnumType.Door.States.Open" },
        "Refrigeration.Common.Status.Door.Refrigerator": { "type": "Boolean", "class": "door", "icon": None, "on_state": "Refrigeration.Common.EnumType.Door.States.Open" },
        "Connected": { "class": "connectivity" },
    }
}

DEVICE_ICON_MAP = {
    "Dryer": "mdi:tumble-dryer",
    "Washer": "mdi:washing-machine",
    "Dishwasher": "mdi:dishwasher",
    "CoffeeMaker": "mdi:coffee-maker",
    "Oven": "mdi:stove",
    "FridgeFreezer": "mdi:fridge",
    "Fridge": "mdi:fridge",
    "Refrigerator": "mdi:fridge",
    "Freezer": "mdi:fridge",
    "CleaningRobot": "mdi:robot-vacuum",
    "Hood": "mdi:hvac"
}

PUBLISHED_EVENTS = [
    "BSH.Common.Status.OperationState",
    "*.event.*"
]

TRIGGERS_CONFIG = {
    "program_started": { "key": "BSH.Common.Status.OperationState", "value": "BSH.Common.EnumType.OperationState.Run" },
    "program_finished": { "key": "BSH.Common.Status.OperationState", "value": "BSH.Common.EnumType.OperationState.Finished" }
}

