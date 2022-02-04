""" Implement the Select entities of this implementation """

from home_connect_async import Appliance, HomeConnect, HomeConnectError
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import EntityBase
from .const import DEVICE_ICON_MAP, DOMAIN


async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """Add Selects for passed config_entry in HA."""
    homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    added_appliances = []

    def add_appliance(appliance:Appliance, event:str = None) -> None:
        if event=="DEPAIRED":
            added_appliances.remove(appliance.haId)
            return
        elif appliance.haId in added_appliances:
            return

        new_enities = []
        if appliance.available_programs:
            device = ProgramSelect(appliance)
            new_enities.append(device)

        if appliance.selected_program:
            selected_program = appliance.selected_program
            for key in appliance.available_programs[selected_program.key].options:
                option = appliance.available_programs[selected_program.key].options[key]
                if option.allowedvalues:
                    device = OptionSelect(appliance, key, {"opt": option})
                    new_enities.append(device)

        for setting in appliance.settings.values():
            if setting.allowedvalues:
                device = SettingsSelect(appliance, setting.key)
                new_enities.append(device)

        if len(new_enities)>0:
            async_add_entities(new_enities)

    homeconnect.register_callback(add_appliance, ["PAIRED", "DEPAIRED"] )
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)
        added_appliances.append(appliance.haId)

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
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return list(self._appliance.available_programs.keys())

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self._appliance.selected_program.key

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_select_program(key=option)
        except HomeConnectError as ex:
            raise HomeAssistantError(f"Failed to set selected program ({ex.code})")

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._appliance.register_callback(self.async_on_update, ["BSH.Common.Root.SelectedProgram", "CONNECTION_CHANGED"] )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._appliance.deregister_callback(self.async_on_update, ["BSH.Common.Root.SelectedProgram", "CONNECTION_CHANGED"])

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class OptionSelect(EntityBase, SelectEntity):
    """ Selection of program options """
    @property
    def device_class(self) -> str:
        return f"{DOMAIN}__options"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self._conf['opt'].allowedvalues

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self._appliance.selected_program.options[self._key].value

    async def async_select_option(self, option: str) -> None:
        try:
            await self._appliance.async_select_option(key=self._key, value=option)
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
