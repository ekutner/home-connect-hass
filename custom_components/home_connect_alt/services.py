from home_connect_async import HomeConnect

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

class Services():

    def __init__(self, hass:HomeAssistant,  hc:HomeConnect) -> None:
        self.hc = hc
        self.hass = hass
        self.dr = dr.async_get(hass)

    async def async_select_program(self, call) -> None:
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            program_key = data['program_key']
            options = data.get('options')

            await appliance.async_select_program(key=program_key, options=options )

    async def async_start_program(self, call) -> None:
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            await appliance.async_start_program()

    async def async_stop_program(self, call) -> None:
        data = call.data
        appliance = self.get_appliance_from_device_id(data['device_id'])
        if appliance:
            await appliance.async_stop_active_program()

    def get_appliance_from_device_id(self, device_id):
        device = self.dr.devices[device_id]
        haId = list(device.identifiers)[0][1]
        for (key, appliance) in self.hc.appliances.items():
            if key.lower().replace('-','_') == haId:
                return appliance
        return None