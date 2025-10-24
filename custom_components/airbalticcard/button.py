"""Button entity definitions for the AirBalticCard integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .models import AirBalticCardRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirBalticCard manual refresh button."""
    runtime_data: AirBalticCardRuntimeData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            AirBalticCardRefreshButton(
                runtime_data.coordinator, runtime_data.account_id, runtime_data.username
            )
        ],
        update_before_add=False,
    )

    _LOGGER.debug("AirBalticCard Refresh button registered.")


class AirBalticCardRefreshButton(CoordinatorEntity[Mapping[str, Any]], ButtonEntity):
    """Button entity to manually refresh AirBalticCard data."""

    _attr_has_entity_name = True
    _attr_name = "Manual Refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = account_id
        self._username = username
        self._attr_unique_id = f"{DOMAIN}_{account_id}_refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manual refresh triggered for AirBalticCard data.")
        try:
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Manual AirBalticCard refresh completed successfully.")
        except Exception as err:
            _LOGGER.warning("Manual refresh failed: %s", err)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self._account_id}_account")},
            "name": f"AirBalticCard Account ({self._username})",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }
