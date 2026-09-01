import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .airbalticcard_api import (
    AirBalticCardAPI,
    AirBalticCardAuthError,
    AirBalticCardConnectionError,
)
from .const import (
    CONF_PASSWORD,
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class AirBalticCardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for AirBalticCard."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            errors = await self._async_validate(username, password)
            if not errors:
                return self.async_create_entry(
                    title=f"AirBalticCard ({username})",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data):
        """Start the flow that asks for a new password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Check the new password and reload the entry."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            errors = await self._async_validate(entry.data[CONF_USERNAME], password)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
        )

    async def _async_validate(self, username, password):
        """Try to log in and return the form errors, empty when it worked."""
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            await AirBalticCardAPI(username, password, session).login()
        except AirBalticCardAuthError:
            return {"base": "invalid_auth"}
        except AirBalticCardConnectionError:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while validating AirBalticCard login")
            return {"base": "unknown"}
        finally:
            # detach, not close: the connector is shared with the rest of HA.
            session.detach()

        return {}

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
