"""Shared entity bases for the AirBalticCard integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACCOUNT_MODEL, DOMAIN, MANUFACTURER, SIM_MODEL
from .coordinator import AirBalticCardCoordinator


class AirBalticCardAccountEntity(CoordinatorEntity[AirBalticCardCoordinator]):
    """Entity belonging to the account device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, username: str
    ) -> None:
        """Attach the entity to the account device."""
        super().__init__(coordinator)
        self._account_id = account_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{account_id}_account")},
            name=f"AirBalticCard Account ({username})",
            manufacturer=MANUFACTURER,
            model=ACCOUNT_MODEL,
        )


class AirBalticCardSimEntity(CoordinatorEntity[AirBalticCardCoordinator]):
    """Entity belonging to a single SIM device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, sim_number: str
    ) -> None:
        """Attach the entity to a SIM device below the account device."""
        super().__init__(coordinator)
        self._account_id = account_id
        self._sim_number = sim_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{account_id}_{sim_number}")},
            name=f"SIM {sim_number}",
            manufacturer=MANUFACTURER,
            model=SIM_MODEL,
            via_device=(DOMAIN, f"{account_id}_account"),
        )

    @property
    def sim(self) -> dict[str, Any] | None:
        """Return this SIM in the latest coordinator data, if still listed."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("number") == self._sim_number:
                return sim
        return None
