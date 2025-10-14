import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirBalticCard manual refresh button."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities([AirBalticCardRefreshButton(coordinator)], update_before_add=False)

    _LOGGER.debug("AirBalticCard Refresh button registered.")


class AirBalticCardRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button entity to manually refresh AirBalticCard data."""

    _attr_name = "AirBalticCard Refresh"
    _attr_unique_id = f"{DOMAIN}_refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh"

    def __init__(self, coordinator):
        super().__init__(coordinator)

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manual refresh triggered for AirBalticCard data.")
        try:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Manual AirBalticCard refresh completed successfully.")
        except Exception as err:
            _LOGGER.warning("Manual refresh failed: %s", err)
