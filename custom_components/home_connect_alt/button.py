import json
import logging
from home_connect_async import Appliance, HomeConnect, HomeConnectError, Events
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import Configuration, EntityBase, EntityManager
from .const import DOMAIN, HOME_CONNECT_DEVICE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass:HomeAssistant , config_entry:ConfigType, async_add_entities:AddEntitiesCallback) -> None:
    """ Add buttons for passed config_entry in HA """
    #homeconnect:HomeConnect = hass.data[DOMAIN]['homeconnect']
    entry_conf:Configuration = hass.data[DOMAIN][config_entry.entry_id]
    homeconnect:HomeConnect = entry_conf["homeconnect"]
    entity_manager = EntityManager(async_add_entities)

    def add_appliance(appliance:Appliance) -> None:
        conf = entry_conf.get_config()

        if appliance.available_programs:
            entity_manager.add(StartButton(appliance, None, conf))
            entity_manager.add(StopButton(appliance, None, conf))
        if appliance.commands:
            for command in appliance.commands.values():
                # The "BSH.Common.Command.AcknowledgeEvent" command is used to acknowledge the ProgramFinished state
                if command.key not in ["BSH.Common.Command.PauseProgram", "BSH.Common.Command.ResumeProgram", "BSH.Common.Command.AcknowledgeEvent"]:
                    button = CommandButton(appliance, command.key, conf, hc_obj=command)
                    entity_manager.add(button)
        entity_manager.register()

    def remove_appliance(appliance:Appliance) -> None:
        entity_manager.remove_appliance(appliance)

    # First add the integration button
    button_name_suffix = "" if entry_conf["primary_config_entry"] else "_"+config_entry.entry_id
    async_add_entities([HomeConnectRefreshButton(homeconnect, button_name_suffix), HomeConnectDebugButton(homeconnect, button_name_suffix)])

    # Subscribe for events and register existing appliances
    homeconnect.register_callback(add_appliance, [Events.PAIRED, Events.DATA_CHANGED, Events.PROGRAM_STARTED, Events.PROGRAM_SELECTED])
    homeconnect.register_callback(remove_appliance, Events.DEPAIRED)
    for appliance in homeconnect.appliances.values():
        add_appliance(appliance)


class StartButton(EntityBase, ButtonEntity):
    """ Class for buttons that start the selected program """
    @property
    def unique_id(self) -> str:
        return f'{self.haId}_start_pause'

    @property
    def name_ext(self) -> str:
        match self.translation_key:
            case "pause_program":
                return "Pause"
            case "resume_program":
                return "Resume"
        return "Start"

    @property
    def translation_key(self) -> str:
        op_state = self._appliance.status.get("BSH.Common.Status.OperationState")
        if op_state and op_state.value == "BSH.Common.EnumType.OperationState.Run" \
            and  "BSH.Common.Command.PauseProgram" in self._appliance.commands:
            return "pause_program"
        if op_state and op_state.value == "BSH.Common.EnumType.OperationState.Pause" \
            and "BSH.Common.Command.ResumeProgram" in self._appliance.commands:
            return "resume_program"
        return "start_program"

    @property
    def available(self) -> bool:
        op_state = self._appliance.status.get("BSH.Common.Status.OperationState")
        return super().available and op_state and \
            (
                (
                    op_state.value in ["BSH.Common.EnumType.OperationState.Ready", "BSH.Common.EnumType.OperationState.Inactive" ]
                    and (
                        "BSH.Common.Status.RemoteControlStartAllowed" not in self._appliance.status or
                        self._appliance.status["BSH.Common.Status.RemoteControlStartAllowed"].value
                    )
                    and (
                        (self._appliance.selected_program or self._appliance.startonly_program)
                        and not self._appliance.active_program
                        # and self._appliance.available_programs and
                        # self._appliance.selected_program.key in self._appliance.available_programs
                    )
                )
                or (
                    op_state.value == "BSH.Common.EnumType.OperationState.Run"
                    and  "BSH.Common.Command.PauseProgram" in self._appliance.commands
                )
                or (
                    op_state.value == "BSH.Common.EnumType.OperationState.Pause"
                    and  "BSH.Common.Command.ResumeProgram" in self._appliance.commands
                )
            )


    @property
    def icon(self) -> str:
        if "BSH.Common.Command.PauseProgram" in self._appliance.commands \
            and "BSH.Common.Status.OperationState" in self._appliance.status \
            and self._appliance.status["BSH.Common.Status.OperationState"].value == "BSH.Common.EnumType.OperationState.Run":
            return "mdi:pause"
        return "mdi:play"

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            op_state = self._appliance.status.get("BSH.Common.Status.OperationState")
            if op_state and op_state.value in ["BSH.Common.EnumType.OperationState.Ready", "BSH.Common.EnumType.OperationState.Inactive" ]:
                await self._appliance.async_start_program()
            elif op_state and op_state.value == "BSH.Common.EnumType.OperationState.Run":
                await self._appliance.async_pause_active_program()
            elif op_state and op_state.value == "BSH.Common.EnumType.OperationState.Pause":
                await self._appliance.async_resume_paused_program()
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to start the selected program: {ex.error_description} ({ex.code})")
            raise HomeAssistantError(f"Failed to start the selected program ({ex.code})")

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        events = [ Events.CONNECTION_CHANGED,
                   Events.DATA_CHANGED,
                   Events.PROGRAM_SELECTED,
                   Events.PROGRAM_STARTED,
                   Events.PROGRAM_FINISHED,
                   "BSH.Common.Status.*",
                   "BSH.Common.Setting.PowerState"
        ]
        self._appliance.register_callback(self.async_on_update, events)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        events = [ Events.CONNECTION_CHANGED,
                   Events.DATA_CHANGED,
                   Events.PROGRAM_SELECTED,
                   Events.PROGRAM_STARTED,
                   Events.PROGRAM_FINISHED,
                   "BSH.Common.Status.*",
                   "BSH.Common.Setting.PowerState"
        ]
        self._appliance.deregister_callback(self.async_on_update, events)

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class StopButton(EntityBase, ButtonEntity):
    """ Class for buttons that start the selected program """
    @property
    def unique_id(self) -> str:
        return f'{self.haId}_stop'

    @property
    def name_ext(self) -> str:
        return "Stop"

    @property
    def translation_key(self) -> str:
        return "stop_program"

    @property
    def available(self) -> bool:
        return super().available \
        and self._appliance.active_program \
        and (
            "BSH.Common.Status.RemoteControlStartAllowed" not in self._appliance.status or
            self._appliance.status["BSH.Common.Status.RemoteControlStartAllowed"].value
        )

    @property
    def icon(self) -> str:
        return "mdi:stop"

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            await self._appliance.async_stop_active_program()
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to stop the selected program: {ex.error_description} ({ex.code})")
            raise HomeAssistantError(f"Failed to stop the selected program ({ex.code})")

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        events = [ Events.CONNECTION_CHANGED,
                   Events.DATA_CHANGED,
                   Events.PROGRAM_SELECTED,
                   Events.PROGRAM_STARTED,
                   Events.PROGRAM_FINISHED,
                   "BSH.Common.Status.*",
                   "BSH.Common.Setting.PowerState"
        ]
        self._appliance.register_callback(self.async_on_update, events)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        events = [ Events.CONNECTION_CHANGED,
                   Events.DATA_CHANGED,
                   Events.PROGRAM_SELECTED,
                   Events.PROGRAM_STARTED,
                   Events.PROGRAM_FINISHED,
                   "BSH.Common.Status.*",
                   "BSH.Common.Setting.PowerState"
        ]
        self._appliance.deregister_callback(self.async_on_update, events)

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()


class CommandButton(EntityBase, ButtonEntity):
    """ Class for running a HC command """

    @property
    def name_ext(self) -> str|None:
        return self._hc_obj.name

    @property
    def icon(self) -> str:
        return self.get_entity_setting('icon', "mdi:button-pointer")

    @property
    def available(self) -> bool:
        return super().available and self._appliance.commands and self._key in self._appliance.commands

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            await self._appliance.async_send_command(self._key, True)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to stop the selected program: {ex.error_description} ({ex.code})")
            raise HomeAssistantError(f"Failed to stop the selected program ({ex.code})")

    async def async_on_update(self, appliance:Appliance, key:str, value) -> None:
        self.async_write_ha_state()

class HomeConnectRefreshButton(ButtonEntity):
    """ Class for a button to trigger a global refresh of Home Connect data  """
    _attr_has_entity_name = True

    def __init__(self, homeconnect:HomeConnect, name_suffix:str) -> None:
        self._homeconnect = homeconnect
        self._name_suffix = name_suffix
        self.entity_id = f'home_connect.{self.unique_id}'

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return "homeconnect_refresh" + self._name_suffix

    @property
    def translation_key(self) -> str:
        return "homeconnect_refresh"

    @property
    def icon(self) -> str:
        return "mdi:cloud-refresh"

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            self._homeconnect.start_load_data_task(refresh=HomeConnect.RefreshMode.ALL)
        except HomeConnectError as ex:
            if ex.error_description:
                raise HomeAssistantError(f"Failed to refresh the Home Connect data: {ex.error_description} ({ex.code})")
            raise HomeAssistantError(f"Failed to refresh the Home Connect data ({ex.code})")


class HomeConnectDebugButton(ButtonEntity):
    """ Class for a button to trigger a global refresh of Home Connect data  """
    _attr_has_entity_name = True

    def __init__(self, homeconnect:HomeConnect, name_suffix:str) -> None:
        self._homeconnect = homeconnect
        self._name_suffix = name_suffix
        self.entity_id = f'home_connect.{self.unique_id}'

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return HOME_CONNECT_DEVICE

    @property
    def unique_id(self) -> str:
        return "homeconnect_debug" + self._name_suffix

    # @property
    # def name(self) -> str:
    #     return "homeconnect_debug"
    #     return None
        #return "Home Connect Debug Info"

    @property
    def translation_key(self) -> str:
        return "homeconnect_debug"

    @property
    def icon(self) -> str:
        return "mdi:bug-check"

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        """ Handle button press """
        try:
            conf = {k:v for (k,v) in self.hass.data[DOMAIN].items() if isinstance(v, (str, int, float, dict, list)) and k not in [CONF_CLIENT_ID, CONF_CLIENT_SECRET] }
            js=json.dumps(conf, indent=2, default=lambda o: '<not serializable>')
            #js=json.dumps(self.hass.data[DOMAIN], indent=2, default=lambda o: '<not serializable>')
            _LOGGER.error(js)
            js=self._homeconnect.to_json(indent=2)
            _LOGGER.error(js)
        except Exception as ex:
            raise HomeAssistantError("Failed to serialize to JSON")
