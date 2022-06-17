
import logging
from home_connect_async import Appliance, HomeConnect, Events
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import Configuration, EntityBase, EntityManager
from .const import DOMAIN, SPECIAL_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        for (key, status) in appliance.status.items():
            device = None
            if key in SPECIAL_ENTITIES['status']:
                conf = Configuration(SPECIAL_ENTITIES['status'][key])
                if conf['type'] == 'binary_sensor':
                    device = StatusBinarySensor(appliance, key, conf)
            else:
                if isinstance(status.value, bool): # should be a binary sensor if it has a boolean value
                    device = StatusBinarySensor(appliance, key)
            entity_manager.add(device)

        if appliance.selected_program and appliance.selected_program.options:
            for option in appliance.selected_program.options.values():
                if isinstance(option.value, bool):
                    device = ProgramOptionBinarySensor(appliance, option.key)
                    entity_manager.add(device)

        if appliance.active_program and appliance.active_program.options:
            for option in appliance.active_program.options.values():
                if isinstance(option.value, bool):
                    device = ProgramOptionBinarySensor(appliance, option.key, SPECIAL_ENTITIES['options'].get(option.key, {}))
                    entity_manager.add(device)

        if appliance.settings:
            for setting in appliance.settings.values():
                if setting.type == "Boolean" or isinstance(setting.value, bool):
                    device = SettingsBinarySensor(appliance, setting.key)
                    entity_manager.add(device)

        entity_manager.add(ConnectionBinarySensor(appliance, "Connected"))

        # if len(new_entities)>0:
        #     entity_manager.register_entities(new_entities, async_add_entities)
        entity_manager.register()

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.PROGRAM_STARTED] )
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)

class ProgramOptionBinarySensor(EntityBase, BinarySensorEntity):
    """ Program option binary sensor """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def name_ext(self) -> str:
        current_program = self._appliance.get_applied_program()

        if current_program and current_program.options and self._key in current_program.options:
            return current_program.options[self._key].name
        return None

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        current_program = self._appliance.get_applied_program()
        return super().available and current_program and current_program.options and self._key in current_program.options

    @property
    def is_on(self):
        current_program = self._appliance.get_applied_program()
        if current_program and current_program.options and self._key in current_program.options:
            return current_program.options[self._key].value
        return None

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()

class ActivityOptionBinarySensor(ProgramOptionBinarySensor):
    """ Special active program sensor """

    @property
    def available(self) -> bool:
        return self._appliance.active_program and self._key in self._appliance.active_program.options

    @property
    def name_ext(self) -> str:
        if self._appliance.active_program and (self._key in self._appliance.active_program.options):
            return self._appliance.active_program.options[self._key].name
        return None


class StatusBinarySensor(EntityBase, BinarySensorEntity):
    """ Status binary sensor """
    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:gauge-full')

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.status:
            status = self._appliance.status[self._key]
            if status:
                return status.name
        return None

    @property
    def is_on(self) -> bool:
        if self._key in self._appliance.status:
            if 'on_state' in self._conf:
                return self._appliance.status[self._key].value == self._conf['on_state']
            else:
                return self._appliance.status[self._key].value
        return None

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsBinarySensor(EntityBase, BinarySensorEntity):
    """ Status sensor """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def name_ext(self) -> str:
        if self._key in self._appliance.settings:
            setting = self._appliance.settings[self._key]
            if setting:
                return setting.name
        return None

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def is_on(self):
        if self._key in self._appliance.settings:
            if 'on_state' in self._conf:
                return self._appliance.settings[self._key].value == self._conf['on_state']
            else:
                return self._appliance.settings[self._key].value
        return None

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