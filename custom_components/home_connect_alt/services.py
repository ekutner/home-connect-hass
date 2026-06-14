""" Implement the services of this implementation """
from home_connect_async import HomeConnect, HomeConnectError, Appliance
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .api import PrivateCameraAuthError
from .const import DOMAIN, PRIVATE_CAMERA_AUTH_NOTIFICATION_ID


class Services():
    """ Collection of the Services offered by the integration """
    def __init__(self, hass:HomeAssistant,  homeconnect:HomeConnect) -> None:
        self.homeconnect = homeconnect
        self.hass = hass
        self.dr = dr.async_get(hass)

    async def async_start_private_camera_auth(self, call) -> None:
        """ Service for starting the private camera auth flow """
        private_api = self._get_private_api(call.data.get('config_entry_id'))
        auth_url = await private_api.async_build_authorize_url()
        persistent_notification.async_create(
            self.hass,
            (
                "1. Open the link below in a browser and sign in to Home Connect.\n"
                "2. After the final redirect reaches `https://qr.home-connect.com/authorize/prod/`, copy the full callback URL.\n"
                "3. Call `home_connect_alt.finish_private_camera_auth` with that callback URL.\n\n"
                f"{auth_url}"
            ),
            title="Home Connect Alt private camera auth",
            notification_id=PRIVATE_CAMERA_AUTH_NOTIFICATION_ID,
        )

    async def async_finish_private_camera_auth(self, call) -> None:
        """ Service for completing the private camera auth flow """
        private_api = self._get_private_api(call.data.get('config_entry_id'))
        try:
            await private_api.async_exchange_callback_url(call.data['callback_url'])
        except PrivateCameraAuthError as ex:
            raise HomeAssistantError(str(ex)) from ex
        persistent_notification.async_dismiss(self.hass, PRIVATE_CAMERA_AUTH_NOTIFICATION_ID)

    def _get_private_api(self, config_entry_id):
        """ Helper function to get the private API wrapper for a config entry """
        entry_id = config_entry_id
        if not entry_id:
            entry_id = next(
                (
                    key
                    for key, value in self.hass.data[DOMAIN].items()
                    if key != "global" and isinstance(value, dict) and "private_api" in value
                ),
                None,
            )
        if not entry_id or entry_id not in self.hass.data[DOMAIN]:
            raise HomeAssistantError("No Home Connect Alt config entry found for private camera auth")

        conf = self.hass.data[DOMAIN][entry_id]
        if "private_api" not in conf:
            raise HomeAssistantError("Private camera API is not initialized for this config entry")
        return conf["private_api"]

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
        for (key, appliance) in self.homeconnect.appliances.items():
            if key.lower().replace('-','_') == haId:
                return appliance
        return None
