import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

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


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})


class AirBalticCardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for AirBalticCard."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                await self._async_validate_login(username, password)
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

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
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )

    async def _async_validate_login(self, username, password):
        """Validate user credentials."""
        api = AirBalticCardAPI(username, password)
        try:
            await api.login()
            return True
        except ValueError:
            raise InvalidAuth
        except ConnectionError:
            raise CannotConnect

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AirBalticCardOptionsFlow(config_entry)


class AirBalticCardOptionsFlow(config_entries.OptionsFlow):
    """Handle AirBalticCard integration options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            scan = user_input.get(CONF_SCAN_INTERVAL)
            retry = user_input.get(CONF_RETRY_INTERVAL)

            if scan < 10:
                errors["base"] = "scan_too_short"
            elif retry < 5:
                errors["base"] = "retry_too_short"
            else:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or {}
        schema = vol.Schema({
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=86400)),
            vol.Required(
                CONF_RETRY_INTERVAL,
                default=current.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=86400)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication."""
