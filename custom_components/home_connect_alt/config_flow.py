"""Config flow for Home Connect New."""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv

from .const import *

# from homeassistant.helpers import (
#     config_entry_oauth2_flow,
#     config_validation as cv,
# )


# CONFIG_SCHEMA = vol.Schema(
#     {
#         DOMAIN: vol.Schema(
#             {
#                 vol.Required(CONF_CLIENT_ID): cv.string,
#                 vol.Required(CONF_CLIENT_SECRET): cv.string,
#                 vol.Required('simulate'): cv.boolean
#             }
#         )
#     },
#     extra=vol.ALLOW_EXTRA,
# )

class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Home Connect New OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPES}

    


    # async def async_step_user(self, user_input=None):
    #         # Specify items in the order they are to be displayed in the UI
    #         if user_input is None:
    #             data_schema = vol.Schema(
    #                 {
    #                     vol.Required(CONF_CLIENT_ID): cv.string,
    #                     vol.Required(CONF_CLIENT_SECRET, description='Client Secret'): cv.string,
    #                     vol.Required('simulate', msg='its required', description='Simulate'): cv.boolean
    #                 }
    #             )

    #             if self.show_advanced_options:
    #                 pass
    #                 #data_schema["allow_groups"] = bool

    #             return self.async_show_form(step_id="user", data_schema=data_schema)

    #         else:
    #             simulate = user_input['simulate']
    #             OAuth2FlowHandler.async_register_implementation(
    #                 self.hass,
    #                 config_entry_oauth2_flow.LocalOAuth2Implementation(
    #                     self.hass,
    #                     DOMAIN,
    #                     user_input[CONF_CLIENT_ID],
    #                     user_input[CONF_CLIENT_SECRET],
    #                     f'{SIM_HOST if simulate else API_HOST}{ENDPOINT_AUTHORIZE}',
    #                     f'{SIM_HOST if simulate else API_HOST}{ENDPOINT_TOKEN}',
    #                 ),
    #             )
    #             user_input["implementation"] = DOMAIN
    #             return await self.async_step_pick_implementation(user_input)
    #             # res = await self.async_step_auth(user_input)
    #             # return res
    #             # #return self.async_create_entry(title='Home Connect New', data=user_input )


    # # async def async_step_user(self, user_input=None):
    # #     """Handle a flow start."""
    # #     # Only allow 1 instance.
    # #     if self._async_current_entries():
    # #         return self.async_abort(reason="single_instance_allowed")

    # #     return await super().async_step_user(user_input)

    # async def async_step_auth(self, user_input=None):
    #     """Handle authorize step."""
    #     result = await super().async_step_auth(user_input)

    #     # if result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP:
    #     #     self.host = str(URL(result["url"]).with_path("me"))

    #     return result