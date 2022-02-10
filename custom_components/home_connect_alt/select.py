""" Implement the Select entities of this implementation """

from home_connect_async import Appliance, HomeConnect, HomeConnectError
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase, EntityManager
from .const import DEVICE_ICON_MAP, DOMAIN


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entity_manager = EntityManager()

    def add_appliance(appliance:Appliance) -> None:
        new_entities = []
        if appliance.available_programs:
            device = ProgramSelect(appliance)
            new_entities.append(device)

        if appliance.selected_program:
            selected_program = appliance.selected_program
            for key in appliance.available_programs[selected_program.key].options:
                option = appliance.available_programs[selected_program.key].options[key]
                if option.allowedvalues:
                    device = OptionSelect(appliance, key)
                    new_entities.append(device)

        for setting in appliance.settings.values():
            if setting.allowedvalues:
                device = SettingsSelect(appliance, setting.key)
                new_entities.append(device)

        if len(new_entities)>0:
            entity_manager.register_entities(new_entities, async_add_entities)

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    homeconnect.register_callback(add_appliance, "PAIRED")
    homeconnect.register_callback(remove_appliance, "DEPAIRED")
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)

class ProgramSelect(EntityBase, SelectEntity):
    """ Selection of available programs """
    @property
    def unique_id(self) -> str:
        return f'{self.haId}_programs'

    @property
    def name(self) -> str:
        return f"{self._appliance.brand} {self._appliance.type} - Programs"

    @property
    def icon(self) -> str:
        if self._appliance.type in DEVICE_ICON_MAP:
            return DEVICE_ICON_MAP[self._appliance.type]
        return None

    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__programs"

    @property
    def available(self) -> bool:
        return super().available \
            and self._appliance.available_programs \
            and not self._appliance.active_program \
            and  (
                "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
                self._appliance.status["BSH.Common.Status.RemoteControlActive"]
            )

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return list(self._appliance.available_programs.keys())

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        if self._appliance.selected_program.key not in self._appliance.available_programs:
            # The API sometimes returns programs which are not one of the avilable programs so we ignore it
            return None
        return self._appliance.selected_program.key

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_select_program(key=option)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to set selected program ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class OptionSelect(EntityBase, SelectEntity):
    """ Selection of program options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:office-building-cog')

    @property
    def available(self) -> bool:
        return self._appliance.selected_program \
            and (self._key in self._appliance.selected_program.options) \
            and self._appliance.available_programs \
            and (self._appliance.selected_program.key in self._appliance.available_programs) \
            and (self._key in  self._appliance.available_programs[self._appliance.selected_program.key].options) \
            and super().available \
            and  (
                "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
                self._appliance.status["BSH.Common.Status.RemoteControlActive"]
            )


    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        selected_program_key = self._appliance.selected_program.key
        available_program = self._appliance.available_programs.get(selected_program_key)
        if available_program:
            option = available_program.options.get(self._key)
            if option:
                return option.allowedvalues
        return None

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self._appliance.selected_program.options[self._key].value

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_set_option(key=self._key, value=option)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"{ex.error_description} ({ex.code})")
            else:
                raise HomeAssistantError(f"Failed to set selected option ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class SettingsSelect(EntityBase, SelectEntity):
    """ Selection of settings """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__settings"

    @property
    def icon(self) -> str:
        return self._conf.get('icon', 'mdi:tune')

    @property
    def available(self) -> bool:
        return super().available \
        and (
            "BSH.Common.Status.RemoteControlActive" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlActive"]
        )

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        try:
            return self._appliance.settings[self._key].allowedvalues
        except Exception as ex:
            pass
        return []

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self._appliance.settings[self._key].value

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_apply_setting(key=self._key, value=option)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to set selected setting ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()
