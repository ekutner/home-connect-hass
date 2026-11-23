""" Implement the services of this implementation """
from home_connect_async import HomeConnectError, Appliance
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


class Services():
    """ Collection of the Services offered by the integration """
    def __init__(self, hass:HomeAssistant) -> None:
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

    def get_appliance_from_device_id(self, device_id) -> Appliance:
        """ Helper function to get an appliance from the Home Assistant device_id """
        # The services are shared by all the config entries, so route the call to the
        # loaded entry that owns the device and has the appliance enabled
        device = self.dr.async_get(device_id)
        haId = next((identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN), None) if device else None
        if not device or not haId:
            raise ServiceValidationError(f"Device {device_id} is not a Home Connect Alt appliance")
        for entry_id in device.config_entries:
            entry_conf = self.hass.data.get(DOMAIN, {}).get(entry_id)
            homeconnect = entry_conf.get("homeconnect") if entry_conf else None
            if homeconnect is None:
                continue
            for (key, appliance) in homeconnect.appliances.items():
                if key.lower().replace('-','_') == haId:
                    return appliance
        raise ServiceValidationError(f"No loaded Home Connect Alt config entry has the appliance {device.name or device_id} enabled")
