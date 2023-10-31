"""Config flow for Home Connect New."""
import logging
from typing import Any, Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, FlowHandler
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.selector import selector


from .const import *


class OAuth2FlowHandler2(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Home Connect New OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPES}

class OAuth2FlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Home Connect New OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPES}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""
        implementations = await config_entry_oauth2_flow.async_get_implementations(self.hass, self.DOMAIN)
        if user_input is None and not implementations:
            data_schema = vol.Schema({
                vol.Required(CONF_API_HOST, default=CONF_API_HOST_OPTIONS[0]):
                    selector(
                    {
                        "select": {
                            "options": CONF_API_HOST_OPTIONS,
                            "mode": "dropdown",
                            "translation_key": CONF_API_HOST,
                        },
                    })
             })
            return self.async_show_form(step_id="user", data_schema=data_schema )

        if user_input and CONF_API_HOST in user_input:
            if DOMAIN not in self.hass.data:
                self.hass.data[DOMAIN] = {}
            self.hass.data[DOMAIN].update(user_input)
            user_input = None
        return await self.async_step_pick_implementation(user_input)


    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        if self.reauth_entry:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        if self._async_current_entries():
            # Config entry already exists, only one allowed.
            return self.async_abort(reason="single_instance_allowed")

        data[CONF_API_HOST] = self.hass.data[DOMAIN][CONF_API_HOST]
        return self.async_create_entry(
            title=NAME,
            data=data,

        )


    def default_language_code(self, hass: HomeAssistant):
        """Get default language code based on Home Assistant config."""
        language_code = f"{hass.config.language}-{hass.config.country}"
        return language_code


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """ Options flow """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """ Manage the options """
        if user_input is not None:
            self.hass.data[DOMAIN].update(user_input)
            return self.async_create_entry(title="", data=user_input)

        data_schema = {
            vol.Optional(CONF_LANG, default="en-GB"): cv.string,
            vol.Optional(CONF_TRANSLATION_MODE):
                selector({
                    "select": {
                        "options": CONF_TRANSLATION_MODES,
                        "mode": "dropdown",
                        "translation_key": CONF_TRANSLATION_MODE
                    },
                }),
        }
        if self.context.get("show_advanced_options"):
            data_schema.update(
                {
                    vol.Optional(CONF_NAME_TEMPLATE, default=CONF_NAME_TEMPLATE_DEFAULT): str,
                    vol.Optional(CONF_LOG_MODE, default=0): vol.All(int, vol.Range(min=0, max=7)),

                    # vol.Optional(CONF_APPLIANCE_SETTINGS): selector({
                    #     "device": {
                    #         "entity": [ {"integration": DOMAIN}],
                    #         "multiple": True,
                    #     }
                    # }),
                }
            )

        defaults = self.hass.data[DOMAIN]
        data_schema = self.add_suggested_values_to_schema(data_schema=vol.Schema(data_schema), suggested_values=defaults)

        return self.async_show_form(step_id="init", data_schema=data_schema)


