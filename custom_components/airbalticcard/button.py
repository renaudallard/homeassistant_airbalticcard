"""Button entity for the AirBalticCard integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirBalticCardCoordinator
from .entity import AirBalticCardAccountEntity

if TYPE_CHECKING:
    from . import AirBalticCardConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirBalticCardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirBalticCard manual refresh button."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            AirBalticCardRefreshButton(
                runtime.coordinator, runtime.account_id, runtime.username
            )
        ]
    )


class AirBalticCardRefreshButton(AirBalticCardAccountEntity, ButtonEntity):
    """Button that fetches the account data on demand."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"
    _attr_translation_key = "refresh"

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, username: str
    ) -> None:
        """Set the account-scoped unique ID."""
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_refresh"

    @property
    def available(self) -> bool:
        """Stay available: a failed update is exactly when this is needed."""
        return True

    async def async_press(self) -> None:
        """Refresh the account data."""
        await self.coordinator.async_request_refresh()
