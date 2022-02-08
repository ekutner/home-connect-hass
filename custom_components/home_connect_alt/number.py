""" Implement the Number entities of this implementation """

from home_connect_async import Appliance, HomeConnect, HomeConnectError
from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DOMAIN


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Numbers for passed config_entry in HA."""
    #auth = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager()

    def add_appliance(appliance:Appliance) -> None:
        new_entities = []
        if appliance.selected_program:
            selected_program = appliance.selected_program
            for key in appliance.available_programs[selected_program.key].options:
                option = appliance.available_programs[selected_program.key].options[key]
                if option.type in ["Int", "Float", "Double"]:
                    device = OptionNumber(appliance, key, {"opt": option})
                    new_entities.append(device)

        for setting in appliance.settings.values():
            if setting.type in ["Int", "Float", "Double"]:
                device = SettingsNumber(appliance, setting.key, {"opt": setting})
                new_entities.append(device)

        if len(new_entities)>0:
            entity_manager.register_entities(new_entities, async_add_entities)

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, "PAIRED")
    homeconnect.register_callback(remove_appliance, "DEPAIRED")
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        #added_appliances.append(appliance.haId)


class OptionNumber(EntityBase, NumberEntity):
    """ Class for numeric options """
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
    def min_value(self) -> float:
        """Return the minimum value."""
        try:
            return self._conf['opt'].min
        except Exception as ex:
            pass
        return 0

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._conf['opt'].max

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def value(self) -> float:
        """Return the entity value to represent the entity state."""
        if self._key in self._appliance.selected_program.options:
            return self._appliance.selected_program.options[self._key].value
        return None

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self._appliance.async_set_option(self._key, value)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to set option value ({ex.code})") from ex

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsNumber(EntityBase, NumberEntity):
    """ Class for numeric settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._conf['opt'].min

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._conf['opt'].max

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._conf['opt'].stepsize

    @property
    def unit_of_measurement(self) -> str:
        return self._conf['opt'].unit

    @property
    def value(self) -> float:
        """Return the entity value to represent the entity state."""
        if self._key in self._appliance.settings:
            return self._appliance.settings[self._key].value
        return None

    async def async_set_value(self, value: float) -> None:
        try:
            await self._appliance.async_apply_setting(self._key, value)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to apply setting value ({ex.code})") from ex


    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
