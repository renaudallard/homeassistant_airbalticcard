"""Sensor entities for the AirBalticCard integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BALANCE_CRITICAL, BALANCE_WARNING, DOMAIN
from .coordinator import AirBalticCardCoordinator
from .entity import AirBalticCardAccountEntity, AirBalticCardSimEntity

if TYPE_CHECKING:
    from . import AirBalticCardConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirBalticCardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the account sensors and follow the SIM cards as they appear."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    known: set[str] = set()

    @callback
    def _add_new_sims() -> None:
        """Add sensors for SIM cards that have no entities yet."""
        entities: list[SensorEntity] = []
        for sim in coordinator.data.get("sims", []):
            number = sim.get("number")
            if not number or number in known:
                continue
            known.add(number)
            entities.append(
                AirBalticCardSimBalanceSensor(coordinator, runtime.account_id, number)
            )
            entities.append(
                AirBalticCardSimDescriptionSensor(
                    coordinator, runtime.account_id, number
                )
            )
        if entities:
            async_add_entities(entities)

    async_add_entities(
        [
            AirBalticCardAccountSensor(
                coordinator, runtime.account_id, runtime.username
            ),
            AirBalticCardTotalSimCreditSensor(
                coordinator, runtime.account_id, runtime.username
            ),
        ]
    )
    _add_new_sims()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_sims))


class AirBalticCardAccountSensor(AirBalticCardAccountEntity, SensorEntity):
    """Sensor showing total account credit."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:wallet"
    _attr_translation_key = "account_credit"

    def __init__(
        self,
        coordinator: AirBalticCardCoordinator,
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_account_credit"

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("account_credit")


# ================================================================
# Total SIM Credit sensor
# ================================================================
class AirBalticCardTotalSimCreditSensor(AirBalticCardAccountEntity, SensorEntity):
    """Sensor summing all SIM card balances."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:cash-multiple"
    _attr_translation_key = "total_sim_credit"

    def __init__(
        self,
        coordinator: AirBalticCardCoordinator,
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_total_sim_credit"

    @property
    def native_value(self) -> float | None:
        balances = [
            sim["credit"]
            for sim in (self.coordinator.data or {}).get("sims", [])
            if sim.get("credit") is not None
        ]
        if not balances:
            return None
        return round(sum(balances), 2)


# ================================================================
# Individual SIM BALANCE sensors (with dynamic icons + severity)
# ================================================================
class AirBalticCardSimBalanceSensor(AirBalticCardSimEntity, SensorEntity):
    """Sensor showing SIM card balance with dynamic icons."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_translation_key = "sim_balance"

    def __init__(
        self,
        coordinator: AirBalticCardCoordinator,
        account_id: str,
        sim_number: str,
    ) -> None:
        super().__init__(coordinator, account_id, sim_number)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_balance"

    @property
    def native_value(self) -> float | None:
        sim = self.sim
        return sim.get("credit") if sim else None

    @property
    def icon(self) -> str:
        value = self.native_value
        if value is None:
            return "mdi:sim"
        if value < BALANCE_CRITICAL:
            return "mdi:sim-alert"
        if value < BALANCE_WARNING:
            return "mdi:sim-off"
        return "mdi:sim"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sim = self.sim or {}
        value = sim.get("credit")

        if value is None:
            severity = None
        elif value < BALANCE_CRITICAL:
            severity = "critical"
        elif value < BALANCE_WARNING:
            severity = "warning"
        else:
            severity = "normal"

        return {
            "sim_number": self._sim_number,
            "sim_name": sim.get("name"),
            "balance_state": severity,
        }


# ================================================================
# Individual SIM DESCRIPTION sensors
# ================================================================
class AirBalticCardSimDescriptionSensor(AirBalticCardSimEntity, SensorEntity):
    """Sensor showing SIM card description/label."""

    _attr_icon = "mdi:label"
    _attr_translation_key = "sim_description"

    def __init__(
        self,
        coordinator: AirBalticCardCoordinator,
        account_id: str,
        sim_number: str,
    ) -> None:
        super().__init__(coordinator, account_id, sim_number)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_description"

    @property
    def native_value(self):
        sim = self.sim
        if not sim:
            return None
        return sim.get("name")
