from __future__ import annotations
import logging
from math import log
import re
from abc import ABC, abstractmethod

from home_connect_async import Appliance, Events
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import CONF_NAME_TEMPLATE, CONF_NAME_TEMPLATE_DEFAULT, DOMAIN, DEFAULT_SETTINGS, CONF_ENTITY_SETTINGS, CONF_APPLIANCE_SETTINGS

_LOGGER = logging.getLogger(__name__)

def is_boolean_enum(values:list[str]) -> bool:
    """ Check if the list of enum values represents a boolean on/off option"""
    if not values or len(values) != 2:
        return False

    for v in values:
        v = v.lower()
        if not v.endswith(".off") and not v.endswith(".on") and not v.endswith(".standby"):
            return False
    return True

class EntityBase(ABC):
    """Base class with common methods for all the entities """

   #_attr_has_entity_name = True
    should_poll = False

    _appliance: Appliance = None

    def __init__(self, appliance:Appliance, key:str, conf:Configuration, hc_obj=None) -> None:
        """Initialize the sensor."""
        self._appliance = appliance
        self._homeconnect = appliance._homeconnect
        self._key = key
        self._conf = conf
        self._haid = None
        self._unique_id = None
        self.entity_id = f'home_connect.{self.unique_id}'
        self._hc_obj = hc_obj


    def get_entity_setting(self, option, default=None):
        """ Gets the specified configuration option for the entity """
        return self._conf.get_entity_setting(self._key, option, default)

    def has_entity_setting(self, option, default=None) -> bool:
        """ Checks if the specified configuration option exists for the entity """
        return self._conf.has_entity_setting(self._key, option)

    @staticmethod
    def get_non_numeric_haID(hass: HomeAssistant, haid:str, brand:str) -> str:
        """ Returns a haID that doesn't start with a digit by adding the brand as a prefix if needed """
        if haid[0].isdigit():
            # if the haID starts with a digit and there aren't entities that use that haid already then add the brand as a prefix to the haId
            # This is to avoid issues with using such entities in templates
            ent_reg = er.async_get(hass)
            if ent_reg.entities.get(f"binary_sensor.{haid}_connected") is None:
                # Use the "connected" entity as a representative of the IDs of all the other entities
                # This is done to avoid breaking existing implementations that already use the haId without the brand prefix
                haid = brand.lower() + "_" + haid
            else:
                _LOGGER.debug("Not adding brand prefix to haID %s because there are existing entities without it", haid)

        return haid

    @property
    def haId(self) -> str:
        """ The haID of the appliance """
        if not self._haid:
            self._haid =  self._appliance.haId.lower().replace('-','_')
        return self._haid


    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.haId)},
            "name": self._appliance.name,
            "manufacturer": self._appliance.brand,
            "model": self._appliance.vib,
        }

    @property
    def device_class(self) -> str|None:
        """ Return the device class, if defined """
        if self._conf:
            return self._conf.get_entity_setting(self._key, "class")
        return None

    @property
    def unique_id(self) -> str:
        """" The unique ID of the entity """

        if not self._unique_id:
            haid = self._appliance.normalized_haId
            unique_id = f"{haid}_{self._key.lower().replace('.','_')}"

            if haid[0].isdigit():
                # Don't create new entities with IDs that start with a digit
                # but leave existing entities as they are to avoid breaking changes

                ent_reg = er.async_get(self._conf.hass)
                all_entities_ids = ent_reg.entities.keys()
                existing_entities = [eid for eid in all_entities_ids if eid.endswith(f".{unique_id}")]
                if not existing_entities:
                    unique_id = f"{self._appliance.brand.lower()}_{unique_id}"

            self._unique_id =  unique_id
        return self._unique_id

    @property
    def name_ext(self) -> str|None:
        """Provide the suffix of the name, can be be overridden by sub-classes to provide a custom or translated display name."""
        return None

    @property
    def name(self) -> str:
        """" The name of the entity """
        # haId = self._appliance.haId
        if self._conf and CONF_APPLIANCE_SETTINGS in self._conf and self._conf[CONF_APPLIANCE_SETTINGS] \
            and self.haId in self._conf[CONF_APPLIANCE_SETTINGS] and CONF_NAME_TEMPLATE in self._conf[CONF_APPLIANCE_SETTINGS][self.haId]:
            template = self._conf[CONF_APPLIANCE_SETTINGS][self.haId][CONF_NAME_TEMPLATE]
        elif self._conf and CONF_NAME_TEMPLATE in self._conf and self._conf[CONF_NAME_TEMPLATE]:
            template = self._conf[CONF_NAME_TEMPLATE]
        else:
            template = CONF_NAME_TEMPLATE_DEFAULT

        appliance_name = self._appliance.name if self._appliance.name else self._appliance.type
        name = self.name_ext if self.name_ext else self.pretty_enum(self._key)
        return template.replace("$brand", self._appliance.brand).replace("$appliance", appliance_name).replace("$name", name)


    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will reflect this.
    @property
    def available(self) -> bool:
        """Availability of the entity."""
        return self._appliance.connected

    @property
    def program_option_available(self) -> bool:
        """ Helper to be used for program options controls """
        return (
            self._appliance.connected
            and self._appliance.is_available_option(self._key)
            and  (
                "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
                self._appliance.status["BSH.Common.Status.RemoteControlActive"].value
            )
        )

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        events = [Events.CONNECTION_CHANGED, Events.DATA_CHANGED, Events.PROGRAM_SELECTED]
        if self._key:
            events.append(self._key)
        self._appliance.register_callback(self.async_on_update, events)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        events = [Events.CONNECTION_CHANGED, Events.DATA_CHANGED, Events.PROGRAM_SELECTED]
        if self._key:
            events.append(self._key)
        self._appliance.deregister_callback(self.async_on_update, events)

    @abstractmethod
    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        pass

    def pretty_enum(self, val:str) -> str:
        """Extract display string from a Home Connect Enum string."""
        name = val.split('.')[-1]
        parts = re.findall('[A-Z0-9]+[^A-Z]*', name)
        return' '.join(parts)


class InteractiveEntityBase(EntityBase):
    """ Base class for interactive entities (select, switch and number) """

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._key != "BSH.Common.Status.RemoteControlActive":
            self._appliance.register_callback(self.async_on_update, "BSH.Common.Status.RemoteControlActive")

    async def async_will_remove_from_hass(self):
        await super().async_will_remove_from_hass()
        if self._key != "BSH.Common.Status.RemoteControlActive":
            self._appliance.deregister_callback(self.async_on_update, "BSH.Common.Status.RemoteControlActive")


class EntityManager():
    """Helper class for managing entity registration.

    Duplication might happen because there is a race condition between the task that
    loads data from the Home Connect service and the initialization of the platforms.
    This class prevents that from happening.
    """
    def __init__(self, async_add_entities:AddEntitiesCallback, platform:str):
        self._existing_ids = set()
        self._pending_entities:dict[str, Entity] = {}
        self._entity_appliance_map = {}
        self._async_add_entities = async_add_entities
        self._platform = platform

    def add(self, entity:Entity) -> None:
        """Add a new entity unless it already exists."""
        if entity and (entity.unique_id not in self._existing_ids) and (entity.unique_id not in self._pending_entities):
            self._pending_entities[entity.unique_id] = entity

    def register(self) -> None:
        """ register the pending entities with Home Assistant """
        new_ids = set(self._pending_entities.keys())
        new_entities = list(self._pending_entities.values())
        for entity in new_entities:
            if entity.haId not in self._entity_appliance_map:
                self._entity_appliance_map[entity.haId] = set()
            self._entity_appliance_map[entity.haId].add(entity.unique_id)
        if len(new_ids)>0:
            _LOGGER.debug("Registering new entities for platform=%s: %s", self._platform, new_ids)
            _LOGGER.debug("Already registered entities for platform=%s: %s", self._platform, self._existing_ids)
            self._async_add_entities(new_entities)
            self._existing_ids |= new_ids
            self._pending_entities = {}

    def remove_appliance(self, appliance:Appliance):
        """ Remove an appliance and all its registered entities """
        if appliance.haId in self._entity_appliance_map:
            self._existing_ids -= self._entity_appliance_map[appliance.haId]
            del self._entity_appliance_map[appliance.haId]


class Configuration(dict):
    """ A class to handle both global config coming from configuration.yaml and the local config of each entity """
    _global_config:dict = None
    _hass:HomeAssistant = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update(self.__merge(self, DEFAULT_SETTINGS, overwrite=False))
        if Configuration._global_config:
            self.update(self.__merge(self, Configuration._global_config, overwrite=False))

    def __merge(self, destination:dict, source:dict, overwrite:bool=True ):
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                self.__merge(node, value, overwrite)
            else:
                if key not in destination or overwrite:
                    destination[key] = value

        return destination

    def get_entity_setting(self, key:str, option:str, default=None):
        """ Retrun an entity config setting or None if it doesn't exist """
        if CONF_ENTITY_SETTINGS in self and  self[CONF_ENTITY_SETTINGS] and key in self[CONF_ENTITY_SETTINGS] and option in self[CONF_ENTITY_SETTINGS][key]:
            return self[CONF_ENTITY_SETTINGS][key][option]
        return default

    def has_entity_setting(self, key:str, option:str) -> bool:
        """Checks if the entity config setting exist """
        if CONF_ENTITY_SETTINGS in self and self[CONF_ENTITY_SETTINGS] and key in self[CONF_ENTITY_SETTINGS] and option in self[CONF_ENTITY_SETTINGS][key]:
            return True
        return False

    def set_entity_setting(self, key:str, option:str, value):
        """Return an entity config setting or None if it doesn't exist."""
        if CONF_ENTITY_SETTINGS not in self:
            self[CONF_ENTITY_SETTINGS] = {}
        if key not in self[CONF_ENTITY_SETTINGS]:
            self[CONF_ENTITY_SETTINGS][key] = {}
        self[CONF_ENTITY_SETTINGS][key][option] = value

    def get_entity_settings(self, key:str):
        """Return an entity config setting or None if it doesn't exist."""
        if CONF_ENTITY_SETTINGS in self and  key in self[CONF_ENTITY_SETTINGS]:
            return self[key]
        return None

    def get_config(self, extra_conf:dict=None):
        """Return a new config object which is the merging of the current one with the extra configuration"""
        c = Configuration(self)
        if extra_conf:
            c.update(extra_conf)
        return c

    @property
    def hass(self) -> HomeAssistant | None:
        """Return the Home Assistant instance."""
        return Configuration._hass

    @classmethod
    def set_global_config(cls, hass:HomeAssistant, global_config:dict):
        """Set the global config once as a static member that will be appended automatically to each config object."""
        cls._global_config = global_config
        cls._hass = hass

    @classmethod
    def get_global_config(cls):
        """Return the global config"""
        return cls._global_config if cls._global_config else {}