import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    CONF_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_RETRY_INTERVAL,
    PLATFORMS,
)
from .airbalticcard_api import AirBalticCardAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up AirBalticCard integration (no YAML)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up AirBalticCard from a config entry."""
    username = entry.data["username"]
    password = entry.data["password"]

    # Use Home Assistant's shared aiohttp session
    session = async_get_clientsession(hass)
    api = AirBalticCardAPI(username, password, session=session)

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    retry_interval = entry.options.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)

    async def async_update_data():
        """Fetch data periodically and handle errors gracefully."""
        try:
            await api.login()
            return await api.get_sim_cards()
        except Exception as err:
            _LOGGER.warning(
                "Failed to fetch AirBalticCard data: %s (retry in %ss)",
                err,
                retry_interval,
            )
            raise UpdateFailed(f"Error communicating with AirBalticCard: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "session": session,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "AirBalticCard integration started for %s (scan=%ss, retry=%ss)",
        username,
        scan_interval,
        retry_interval,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry and clean up resources."""
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if data:
        api = data.get("api")
        if hasattr(api, "close"):
            try:
                await api.close()
            except Exception as e:
                _LOGGER.debug("Error closing AirBalticCard API session: %s", e)

    if unload_ok:
        _LOGGER.info("AirBalticCard integration unloaded successfully")

    return unload_ok
