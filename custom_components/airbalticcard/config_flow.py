import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_RETRY_INTERVAL,
)
from .airbalticcard_api import AirBalticCardAPI


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AirBalticCardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for AirBalticCard."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            try:
                await self._async_validate_login(username, password)

                return self.async_create_entry(
                    title=f"AirBalticCard ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _async_validate_login(self, username, password):
        """Validate user credentials."""
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            await AirBalticCardAPI(username, password, session).login()
        except ValueError as err:
            raise InvalidAuth from err
        except ConnectionError as err:
            raise CannotConnect from err
        finally:
            # detach, not close: the connector is shared with the rest of HA.
            session.detach()
        return True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AirBalticCardOptionsFlow()


class AirBalticCardOptionsFlow(OptionsFlowWithReload):
    """Handle AirBalticCard integration options.

    The entry is reloaded when the options change, so a new interval is picked
    up straight away instead of at the end of the pending poll.
    """

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            scan = user_input.get(CONF_SCAN_INTERVAL)
            retry = user_input.get(CONF_RETRY_INTERVAL)

            if scan < 10 or scan > 86400:
                errors["base"] = "scan_too_short"
            elif retry < 5 or retry > 86400:
                errors["base"] = "retry_too_short"
            else:
                return self.async_create_entry(data=user_input)

        current = self.config_entry.options or {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.Coerce(int),
                vol.Required(
                    CONF_RETRY_INTERVAL,
                    default=current.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
                ): vol.Coerce(int),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication."""
