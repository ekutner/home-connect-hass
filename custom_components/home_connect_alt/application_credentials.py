"""application_credentials platform for Google Assistant SDK."""
from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import CONF_API_HOST, DEFAULT_API_HOST, DOMAIN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""

    api_host = hass.data[DOMAIN].get(CONF_API_HOST, DEFAULT_API_HOST) if DOMAIN in hass.data else DEFAULT_API_HOST

    return AuthorizationServer(
        f"{api_host}/security/oauth/authorize",
        f"{api_host}/security/oauth/token",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "more_info_url": (
            "https://github.com/ekutner/home-connect-hass"
        ),

    }