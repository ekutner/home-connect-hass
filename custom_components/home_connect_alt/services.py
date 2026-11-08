""" Implement the services of this implementation """
from home_connect_async import HomeConnect, HomeConnectError, Appliance
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


class Services():
    """ Collection of the Services offered by the integration """
    def __init__(self, hass:HomeAssistant,  homeconnect:HomeConnect) -> None:
        self.homeconnect = homeconnect
        self.hass = hass
        self.dr = dr.async_get(hass)

    async def async_select_program(self, call) -> None:
        """ Service for selecting a program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            program_key = data['program_key']
            options = data.get('options')
            validate = data.get('validate')
            try:
                await appliance.async_select_program(program_key, options, validate)
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex

    async def async_start_program(self, call) -> None:
        """ Service for starting the currently selected program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            program_key = data.get('program_key')
            options = data.get('options')
            validate = data.get('validate')
            try:
                await appliance.async_start_program(program_key, options, validate)
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex


    async def async_stop_program(self, call) -> None:
        """ Service for stopping the currently active program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_stop_active_program()
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex

    async def async_pause_program(self, call) -> None:
        """ Service for pausing the currently active program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_pause_active_program()
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex

    async def async_resume_program(self, call) -> None:
        """ Service for stopping the currently active program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_resume_paused_program()
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex

    async def async_set_program_option(self, call) -> None:
        """ Service for setting an option on the current program """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_set_option(data['key'], data['value'])
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex
            except ValueError as ex:
                raise HomeAssistantError(str(ex)) from ex


    async def async_apply_setting(self, call) -> None:
        """ Service for applying an appliance setting """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_apply_setting(data['key'], data['value'])
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex
            except ValueError as ex:
                raise HomeAssistantError(str(ex)) from ex

    async def async_run_command(self, call) -> None:
        """ Service for running a command on an appliance """
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            try:
                await appliance.async_send_command(data['key'], data['value'])
            except HomeConnectError as ex:
                raise HomeAssistantError(ex.error_description if ex.error_description else ex.msg) from ex
            except ValueError as ex:
                raise HomeAssistantError(str(ex)) from ex

    def get_appliance_from_device_id(self, device_id) -> Appliance|None:
        """ Helper function to get an appliance from the Home Assistant device_id """
        device = self.dr.devices[device_id]
        haId = list(device.identifiers)[0][1]
        # Every config entry has its own HomeConnect instance, but the services are registered by each entry setup
        # and the last one wins, so look in all the loaded entries and not only in self.homeconnect
        instances = [self.homeconnect]
        for entry_conf in self.hass.data.get(DOMAIN, {}).values():
            homeconnect = entry_conf.get("homeconnect") if isinstance(entry_conf, dict) else None
            if homeconnect is not None and not any(homeconnect is i for i in instances):
                instances.append(homeconnect)
        for homeconnect in instances:
            for (key, appliance) in homeconnect.appliances.items():
                if key.lower().replace('-','_') == haId:
                    return appliance
        raise ServiceValidationError(f"No Home Connect appliance found for device {device.name or device_id}")
