import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirBalticCard manual refresh button."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities([AirBalticCardRefreshButton(coordinator)], update_before_add=False)


class AirBalticCardRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button entity to manually refresh AirBalticCard data."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "AirBalticCard Refresh"
        self._attr_unique_id = f"{DOMAIN}_refresh"
        self._attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manual refresh triggered for AirBalticCard data")
        await self.coordinator.async_request_refresh()
