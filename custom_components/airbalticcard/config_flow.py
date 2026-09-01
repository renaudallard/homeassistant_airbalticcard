"""Config and options flows for the AirBalticCard integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .airbalticcard_api import (
    AirBalticCardAPI,
    AirBalticCardAuthError,
    AirBalticCardConnectionError,
)
from .const import (
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_INTERVAL,
    MIN_RETRY_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class AirBalticCardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for AirBalticCard."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the account credentials and check them."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            # The portal treats the login as case insensitive, so match on the
            # lowercased form to keep one entry per account.
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_validate(username, password)
            if not errors:
                return self.async_create_entry(
                    title=f"AirBalticCard ({username})",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the flow that asks for a new password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check the new password and reload the entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            errors = await self._async_validate(entry.data[CONF_USERNAME], password)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
        )

    async def _async_validate(self, username: str, password: str) -> dict[str, str]:
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
    def async_get_options_flow(config_entry: ConfigEntry) -> AirBalticCardOptionsFlow:
        """Return the options flow handler."""
        return AirBalticCardOptionsFlow()


class AirBalticCardOptionsFlow(OptionsFlowWithReload):
    """Handle the AirBalticCard options.

    The entry is reloaded when the options change, so a new interval is picked
    up straight away instead of at the end of the pending poll.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the polling intervals."""
        errors: dict[str, str] = {}

        if user_input is not None:
            scan = user_input[CONF_SCAN_INTERVAL]
            retry = user_input[CONF_RETRY_INTERVAL]

            if not MIN_SCAN_INTERVAL <= scan <= MAX_INTERVAL:
                errors["base"] = "scan_out_of_range"
            elif not MIN_RETRY_INTERVAL <= retry <= MAX_INTERVAL:
                errors["base"] = "retry_out_of_range"
            else:
                return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL): vol.Coerce(int),
                vol.Required(CONF_RETRY_INTERVAL): vol.Coerce(int),
            }
        )
        # Show back what was just typed on a rejected value, the stored values
        # otherwise.
        current = {
            CONF_SCAN_INTERVAL: self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_RETRY_INTERVAL: self.config_entry.options.get(
                CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or current
            ),
            errors=errors,
        )
