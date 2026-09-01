"""Button entity definitions for the AirBalticCard integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirBalticCardCoordinator
from .entity import AirBalticCardAccountEntity
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


class AirBalticCardRefreshButton(AirBalticCardAccountEntity, ButtonEntity):
    """Button entity to manually refresh AirBalticCard data."""

    _attr_name = "Manual Refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: AirBalticCardCoordinator,
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_refresh"

    @property
    def available(self) -> bool:
        """Stay available: a failed update is exactly when this is needed."""
        return True

    async def async_press(self) -> None:
        """Refresh the account data."""
        await self.coordinator.async_request_refresh()
