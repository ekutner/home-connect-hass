from abc import ABC, abstractmethod, abstractproperty
import re
from home_connect_async import Appliance
from homeassistant.core import callback
from .const import DOMAIN

class EntityBase(ABC):
    """Base representation of a Hello World Sensor."""

    should_poll = False
    _appliance: Appliance = None

    def __init__(self, appliance:Appliance, key:str=None, conf:dict={}) -> None:
        """Initialize the sensor."""
        self._appliance = appliance
        self._key = key
        self._conf = conf
        self.entity_id = f'home_connect.{self.unique_id}'

    @property
    def haId(self) -> str:
        return self._appliance.haId.lower().replace('-','_')


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
    def device_class(self) -> str:
        if self._conf:
            return self._conf.get('class')
        else:
            return None

    @property
    def unique_id(self) -> str:
        return f"{self.haId}_{self._key.lower().replace('.','_')}"

    @property
    def name(self) -> str:
        return f"{self._appliance.brand} {self._appliance.type} - {self.pretty_enum(self._key)}"

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        return self._appliance.connected


    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._appliance.register_callback(self.async_on_update, [self._key, "CONNECTION_CHANGED"])

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._appliance.deregister_callback(self.async_on_update, [self._key, "CONNECTION_CHANGED"])

    @abstractmethod
    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        pass

    def pretty_enum(self, val:str) -> str:
        name = val.split('.')[-1]
        parts = re.findall('[A-Z0-9]+[^A-Z]*', name)
        return' '.join(parts)




