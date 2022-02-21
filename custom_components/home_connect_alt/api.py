"""API for Home Connect New bound to Home Assistant OAuth."""
import home_connect_async
from aiohttp import ClientSession
from homeassistant.helpers import config_entry_oauth2_flow

# TODO the following two API examples are based on our suggested best practices
# for libraries using OAuth2 with requests or aiohttp. Delete the one you won't use.
# For more info see the docs at https://developers.home-assistant.io/docs/api_lib_auth/#oauth2.



class AsyncConfigEntryAuth(home_connect_async.AbstractAuth):
    """Provide Home Connect New authentication tied to an OAuth2 based config entry."""

    def __init__( 
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        host: str
    ) -> None:
        """Initialize Home Connect New auth."""
        super().__init__(websession, host)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
