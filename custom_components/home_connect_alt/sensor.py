from home_connect_async import HomeConnect,Appliance
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.sensor import SensorEntity

from .common import EntityBase
from .const import DEVICE_ICON_MAP, DOMAIN, SPECIAL_ENTITIES


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add sensors for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    added_appliances = []   # avoid duplication of entities for the same appliance (see  race condition below)

    def add_appliance(appliance:Appliance, event:str = None) -> None:
        if event=="DEPAIRED":
            added_appliances.remove(appliance.haId)
            return
        elif appliance.haId in added_appliances:
            return

        new_enities = []
        if appliance.available_programs:
            device = CurrentProgramSensor(appliance)
            new_enities.append(device)

        for (key, value) in appliance.status.items():
            device = None
            if key in SPECIAL_ENTITIES['status']:
                conf = SPECIAL_ENTITIES['status'][key]
                if conf['type'] == 'sensor':
                    device = StatusSensor(appliance, key, conf)
            else:
                conf = {}
                if not isinstance(value, bool): # should be a binary sensor if it has a boolean value
                    if 'temperature' in key.lower():
                        conf['class'] = 'temperature'
                    device = StatusSensor(appliance, key, conf)
            if device:
                new_enities.append(device)

        for (key, conf) in SPECIAL_ENTITIES['activity_options'].items():
            if appliance.type in conf['appliances'] and conf['type']=='sensor':
                device = ActivityOptionSensor(appliance, key, conf)
                new_enities.append(device)

        if len(new_enities)>0:
            async_add_entities(new_enities)

    # There is a race condition between the task that loads data from the Home Connect service
    # and the initialization of the platforms, so we set up an event listener and create the entities for all
    # the appliances that have alreday been loaded
    homeconnect.register_callback(add_appliance, ["PAIRED", "DEPAIRED"] )
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        added_appliances.append(appliance.haId)

    # Add the global home connect satus sensor
    async_add_entities([HomeConnectSensor(homeconnect)])


class CurrentProgramSensor(EntityBase, SensorEntity):

    @property
    def unique_id(self) -> str:
        return f'{self.haId}_current_program'

    @property
    def name(self) -> str:
        return f"{self._appliance.brand} {self._appliance.type} - Current Program"

    @property
    def icon(self) -> str:
        if self._appliance.type in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._appliance.type]
        return None

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__programs"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._appliance.selected_program.key if self._appliance.selected_program else None

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._appliance.register_callback(self.async_on_update, ["BSH.Common.Root.SelectedProgram", "CONNECTION_CHANGED"])

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._appliance.deregister_callback(self.async_on_update,  ["BSH.Common.Root.SelectedProgram", "CONNECTION_CHANGED"])

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()

    # async def async_start_program(self) -> bool:
    #     return await self._appliance.async_start_program()

    # async def async_select_program(self, program, options=None, **kwargs) -> bool:
    #     return await self._appliance.async_select_program(key=program, options=options)


class ActivityOptionSensor(EntityBase, SensorEntity):
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__status"

    @property
    def icon(self) -> str:
        return self._conf.get('icon')

    @property
    def available(self) -> bool:
        return self._appliance.active_program and self._key in self._appliance.active_program.options

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._appliance.active_program.options[self._key].value

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class StatusSensor(EntityBase, SensorEntity):
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__status"

    @property
    def icon(self) -> str:
        return self._conf.get('icon')

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._appliance.status.get(self._key)

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class HomeConnectSensor(SensorEntity):
    should_poll = True

    def __init__(self, homeconnect:HomeConnect) -> None:
        self._homeconnect = homeconnect

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": "Home Connect Service",
            "manufacturer": "BSH"
        }

    @property
    def unique_id(self) -> str:
        return "homeconnect_status"

    @property
    def name(self) -> str:
        return "Home Connect Status"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self._homeconnect.status.name
