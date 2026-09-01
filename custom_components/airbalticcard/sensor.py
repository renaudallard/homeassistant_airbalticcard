"""Sensor entities for the AirBalticCard integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BALANCE_CRITICAL, BALANCE_WARNING, DOMAIN
from .coordinator import AirBalticCardCoordinator
from .entity import AirBalticCardAccountEntity, AirBalticCardSimEntity
from .models import AirBalticCardRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirBalticCard sensors when a config entry is added."""
    runtime_data: AirBalticCardRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime_data.coordinator

    sensors: list[SensorEntity] = []

    data: Mapping[str, Any] = coordinator.data or {}

    # --- Account-level sensor ---
    if data.get("account_credit") is not None:
        sensors.append(
            AirBalticCardAccountSensor(
                coordinator, runtime_data.account_id, runtime_data.username
            )
        )

    # --- Total SIM credit sensor ---
    if data.get("sims"):
        sensors.append(
            AirBalticCardTotalSimCreditSensor(
                coordinator, runtime_data.account_id, runtime_data.username
            )
        )

    # --- Individual SIM sensors (balance + description) ---
    for sim in data.get("sims", []):
        sim_number = sim.get("number")
        if not sim_number:
            continue
        sensors.append(
            AirBalticCardSimBalanceSensor(
                coordinator, runtime_data.account_id, sim_number
            )
        )
        sensors.append(
            AirBalticCardSimDescriptionSensor(
                coordinator, runtime_data.account_id, sim_number
            )
        )

    if sensors:
        async_add_entities(sensors, update_before_add=True)

    sim_count = len(data.get("sims", [])) if isinstance(data.get("sims"), list) else 0
    _LOGGER.debug("AirBalticCard sensors set up with %d SIM(s).", sim_count)


# ================================================================
# Account-level sensor
# ================================================================
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
        self._attr_name = "Account Credit"

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
        self._attr_name = "Total SIM Credit"

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
        self._attr_name = "Balance"

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
        self._attr_name = "Description"

    @property
    def native_value(self):
        sim = self.sim
        if not sim:
            return None
        return sim.get("name")
