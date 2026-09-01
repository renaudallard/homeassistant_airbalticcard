"""Data update coordinator for the AirBalticCard integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .airbalticcard_api import (
    AirBalticCardAPI,
    AirBalticCardAuthError,
    AirBalticCardError,
)
from .const import (
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _interval(entry: ConfigEntry, option: str, default: int) -> timedelta:
    """Return one of the interval options as a timedelta."""
    return timedelta(seconds=entry.options.get(option, default))


class AirBalticCardCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the account page, backing off to the retry interval on failure."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: AirBalticCardAPI
    ) -> None:
        """Start on the scan interval configured for the entry."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=_interval(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the account data for this poll."""
        try:
            data = await self.api.get_sim_cards()
        except AirBalticCardAuthError as err:
            # Ask the user for a new password instead of retrying forever.
            raise ConfigEntryAuthFailed(str(err)) from err
        except AirBalticCardError as err:
            retry = _interval(
                self.config_entry, CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL
            )
            # The next poll is scheduled once this call returns, so assigning
            # the interval here is enough to take effect.
            self.update_interval = retry
            _LOGGER.debug("Retrying in %s seconds", retry.total_seconds())
            raise UpdateFailed(
                f"Error communicating with AirBalticCard: {err}"
            ) from err

        self.update_interval = _interval(
            self.config_entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return data
