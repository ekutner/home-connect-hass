
from home_connect_async import Appliance, HomeConnect
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.binary_sensor import BinarySensorEntity

from .common import EntityBase
from .const import DOMAIN, SPECIAL_ENTITIES


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    added_appliances = []

    def add_appliance(appliance:Appliance, event:str = None) -> None:
        if event=="DEPAIRED":
            added_appliances.remove(appliance.haId)
            return
        elif appliance.haId in added_appliances:
            return

        new_entities = []
        for (key, value) in appliance.status.items():
            device = None
            if key in SPECIAL_ENTITIES['status']:
                conf = SPECIAL_ENTITIES['status'][key]
                if conf['type'] == 'binary_sensor':
                    device = StatusBinarySensor(appliance, key, conf)
            else:
                if isinstance(value, bool): # should be a binary sensor if it has a boolean value
                    device = StatusBinarySensor(appliance, key)
            if device:
                new_entities.append(device)

        new_entities.append(ConnectionBinarySensor(appliance, "Connected"))

        if len(new_entities)>0:
            async_add_entities(new_entities)

    homeconnect.register_callback(add_appliance, ["PAIRED", "DEPAIRED"] )
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        added_appliances.append(appliance.haId)



class StatusBinarySensor(EntityBase, BinarySensorEntity):
    @property
    def icon(self) -> str:
        return self._conf.get('icon')

    @property
    def is_on(self) -> bool:
        if 'on_state' in self._conf:
            return self._appliance.status[self._key] == self._conf['on_state']
        else:
            return self._appliance.status[self._key]

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class ConnectionBinarySensor(EntityBase, BinarySensorEntity):

    @property
    def available(self) -> bool:
        return True
        
    @property
    def is_on(self) -> bool:
        return self._appliance.connected

    async def async_added_to_hass(self):
        self._appliance.register_callback(self.async_on_update, "CONNECTION_CHANGED")
    async def async_will_remove_from_hass(self):
        self._appliance.deregister_callback(self.async_on_update, "CONNECTION_CHANGED")
    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()