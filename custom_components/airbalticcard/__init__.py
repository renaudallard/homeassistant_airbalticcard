"""Integration setup for the AirBalticCard custom component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .airbalticcard_api import AirBalticCardAPI
from .const import DOMAIN, PLATFORMS
from .coordinator import AirBalticCardCoordinator
from .migration import async_migrate_registries
from .models import AirBalticCardRuntimeData

_LOGGER = logging.getLogger(__name__)

type AirBalticCardConfigEntry = ConfigEntry[AirBalticCardRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirBalticCardConfigEntry
) -> bool:
    """Set up AirBalticCard from a config entry."""
    username: str = entry.data[CONF_USERNAME]

    # The portal authenticates with a cookie, so each entry needs a session of
    # its own. The shared session would let two accounts overwrite each other.
    # It is detached automatically when the entry unloads.
    session = async_create_clientsession(hass)
    api = AirBalticCardAPI(username, entry.data[CONF_PASSWORD], session)

    coordinator = AirBalticCardCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AirBalticCardRuntimeData(
        coordinator=coordinator,
        account_id=entry.entry_id,
        username=username,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("AirBalticCard integration started for %s", username)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AirBalticCardConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: AirBalticCardConfigEntry
) -> bool:
    """Migrate an entry created by an older release."""
    if entry.version == 1:
        async_migrate_registries(hass, entry, entry.data[CONF_USERNAME])
        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.debug("Migrated AirBalticCard entry %s to version 2", entry.entry_id)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: AirBalticCardConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow deleting a SIM device that is no longer on the account."""
    account_id = entry.entry_id
    live = {(DOMAIN, f"{account_id}_account")} | {
        (DOMAIN, f"{account_id}_{sim['number']}")
        for sim in entry.runtime_data.coordinator.data.get("sims", [])
        if sim.get("number")
    }
    return not device.identifiers & live
