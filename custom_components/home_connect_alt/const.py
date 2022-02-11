"""Constants for the Home Connect New integration."""


DOMAIN = "home_connect_alt"
SIM_HOST = "https://simulator.home-connect.com"
API_HOST = "https://api.home-connect.com"
ENDPOINT_AUTHORIZE = "/security/oauth/authorize"
ENDPOINT_TOKEN = "/security/oauth/token"
SCOPES = "IdentifyAppliance Monitor Control Settings"
CONF_SIMULATE = "simulate"
CONF_LANG = "language"

HOME_CONNECT_DEVICE = {
    "identifiers": {(DOMAIN, "homeconnect")},
    "name": "Home Connect Service",
    "manufacturer": "BSH"
}

SPECIAL_ENTITIES = {
    "status": {
        "BSH.Common.Status.DoorState": { "type": "binary_sensor", "class": "door", "on_state": "BSH.Common.EnumType.DoorState.Open" },
    },
    "options": {
        "BSH.Common.Option.FinishInRelative": { "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.ElapsedProgramTime": { "unit": None, "class": f"{DOMAIN}__timespan"},
        "BSH.Common.Option.RemainingProgramTime": {"class": "timestamp" }
    },
    "activity_options": {
        "BSH.Common.Option.ElapsedProgramTime": {
            "type": "sensor", "unit": "seconds", "class": f"{DOMAIN}__timespan",
            "appliances": ["Hood", "Oven", "WarmingDrawer"]
        },
        "BSH.Common.Option.RemainingProgramTime": {
            "type": "sensor", "unit": "seconds", "class": "timestamp",
            "appliances": ["CoffeeMachine", "Hood", "Oven", "Dishwasher", "Dryer", "Washer", "WasherDryer"]
        },
        "BSH.Common.Option.RemainingProgramTimeIsEstimated": {
            "type": "binary_sensor",
            "appliances": ["CoffeeMachine", "Hood", "Oven", "Dishwasher", "Dryer", "Washer", "WasherDryer"]
        },
        "BSH.Common.Option.ProgramProgress": {
            "type": "sensor", "unit": "%",
            "appliances": ["CoffeeMachine", "Hood", "Oven", "WarmingDrawer", "Dishwasher", "Dryer", "Washer", "WasherDryer"]
        },
        "ConsumerProducts.CleaningRobot.Option.ProcessPhase": {
            "type": "Sensor",
            "appliances": ["CleaningRobot"]
        },
        "BSH.Common.Option.Duration": {
            "type": "sensor",
            "appliances": ["Hood", "Oven", "Dryer"]
        },
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
    #"program_started": { "key": "BSH.Common.Event.ProgramFinished" },
    "program_started": { "key": "BSH.Common.Status.OperationState", "value": "BSH.Common.EnumType.OperationState.Run" },
    "program_finished": { "key": "BSH.Common.Status.OperationState", "value": "BSH.Common.EnumType.OperationState.Finished" }
}

