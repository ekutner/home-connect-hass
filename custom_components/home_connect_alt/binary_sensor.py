
from home_connect_async import Appliance, HomeConnect
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DOMAIN, SPECIAL_ENTITIES


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager()

    def add_appliance(appliance:Appliance) -> None:
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

        if appliance.selected_program:
            for option in appliance.selected_program.options.values():
                if isinstance(option.value, bool):
                    device = ProgramOptionBinarySensor(appliance, option.key)
                    new_entities.append(device)

        new_entities.append(ConnectionBinarySensor(appliance, "Connected"))

        if len(new_entities)>0:
            entity_manager.register_entities(new_entities, async_add_entities)

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, "PAIRED")
    homeconnect.register_callback(remove_appliance, "DEPAIRED")
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)

class ProgramOptionBinarySensor(EntityBase, BinarySensorEntity):
    """ Program option binary sensor """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        return self._key in self._appliance.selected_program.options and super().available

    @property
    def is_on(self):
        if self._appliance.active_program and self._key in  self._appliance.active_program.options:
            sensor_value = self._appliance.active_program.options[self._key].value
        else:
            sensor_value = self._appliance.selected_program.options[self._key].value
        return sensor_value

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()

class StatusBinarySensor(EntityBase, BinarySensorEntity):
    """ Status binary sensor """
    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:gauge-full')

    @property
    def is_on(self) -> bool:
        if 'on_state' in self._conf:
            return self._appliance.status[self._key] == self._conf['on_state']
        else:
            return self._appliance.status[self._key]

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class ConnectionBinarySensor(EntityBase, BinarySensorEntity):
    """ Appliance connected state binary sensor """
    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._appliance.connected

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()