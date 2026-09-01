"""Integration setup for the AirBalticCard custom component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .airbalticcard_api import AirBalticCardAPI
from .const import DOMAIN, PLATFORMS
from .coordinator import AirBalticCardCoordinator
from .migration import async_migrate_registries
from .models import AirBalticCardRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AirBalticCard integration (YAML not supported)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirBalticCard from a config entry."""
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    # The portal authenticates with a cookie, so each entry needs a session of
    # its own. The shared session would let two accounts overwrite each other.
    # It is detached automatically when the entry unloads.
    session = async_create_clientsession(hass)
    api = AirBalticCardAPI(username, password, session)

    coordinator = AirBalticCardCoordinator(hass, entry, api)

    # Blocking: wait for the first refresh before entity setup
    await coordinator.async_config_entry_first_refresh()

    runtime_data = AirBalticCardRuntimeData(
        coordinator=coordinator,
        account_id=entry.entry_id,
        username=username,
    )

    hass.data[DOMAIN][entry.entry_id] = runtime_data
    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("AirBalticCard integration started for %s", username)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up resources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an entry created by an older release."""
    if entry.version > 2:
        # Downgraded from a newer release; nothing sensible to do.
        return False

    if entry.version == 1:
        async_migrate_registries(hass, entry, entry.data[CONF_USERNAME])
        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.debug("Migrated AirBalticCard entry %s to version 2", entry.entry_id)

    return True
