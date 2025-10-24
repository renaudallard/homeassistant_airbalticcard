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
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
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
            AirBalticCardAccountSensor(coordinator, runtime_data.account_id, runtime_data.username)
        )

    # --- Total SIM credit sensor ---
    if data.get("sims"):
        sensors.append(
            AirBalticCardTotalSimCreditSensor(coordinator, runtime_data.account_id, runtime_data.username)
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
class AirBalticCardAccountSensor(CoordinatorEntity[Mapping[str, Any]], SensorEntity):
    """Sensor showing total account credit."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:wallet"
    _attr_translation_key = "account_credit"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = account_id
        self._username = username
        self._attr_unique_id = f"{DOMAIN}_{account_id}_account_credit"
        self._attr_name = "Account Credit"

    @property
    def native_value(self):
        val = (self.coordinator.data or {}).get("account_credit")
        try:
            return float(val) if val is not None else None
        except Exception:
            return None

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._account_id}_account")},
            "name": f"AirBalticCard Account ({self._username})",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }


# ================================================================
# Total SIM Credit sensor
# ================================================================
class AirBalticCardTotalSimCreditSensor(CoordinatorEntity[Mapping[str, Any]], SensorEntity):
    """Sensor summing all SIM card balances."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:cash-multiple"
    _attr_translation_key = "total_sim_credit"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        account_id: str,
        username: str,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = account_id
        self._username = username
        self._attr_unique_id = f"{DOMAIN}_{account_id}_total_sim_credit"
        self._attr_name = "Total SIM Credit"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        sims = data.get("sims", [])
        total = 0.0
        for sim in sims:
            try:
                val = (sim.get("credit", "") or "").replace("€", "").replace(",", ".").strip()
                total += float(val)
            except Exception:
                continue
        return round(total, 2) if sims else None

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._account_id}_account")},
            "name": f"AirBalticCard Account ({self._username})",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }


# ================================================================
# Individual SIM BALANCE sensors (with dynamic icons + severity)
# ================================================================
class AirBalticCardSimBalanceSensor(CoordinatorEntity[Mapping[str, Any]], SensorEntity):
    """Sensor showing SIM card balance with dynamic icons."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_translation_key = "sim_balance"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        account_id: str,
        sim_number: str,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = account_id
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_balance"
        self._attr_name = "Balance"

    @staticmethod
    def _parse_credit(text: str) -> float | None:
        try:
            return float(text.replace("€", "").replace(",", ".").strip())
        except Exception:
            return None

    @property
    def _sim_data(self):
        data = self.coordinator.data or {}
        for sim in data.get("sims", []):
            if sim.get("number") == self._sim_number:
                return sim
        return None

    @property
    def native_value(self):
        sim = self._sim_data
        if not sim:
            return None
        return self._parse_credit(sim.get("credit", ""))

    @property
    def icon(self):
        val = self.native_value
        if val is None:
            return "mdi:sim"
        if val < 2:
            return "mdi:sim-alert"
        elif val < 4:
            return "mdi:sim-off"
        return "mdi:sim"

    @property
    def extra_state_attributes(self):
        sim = self._sim_data or {}
        val = self.native_value or 0
        severity = (
            "critical" if val < 2 else
            "warning" if val < 4 else
            "normal"
        )
        return {
            "sim_number": sim.get("number"),
            "sim_name": sim.get("name"),
            "balance_state": severity,
        }

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._account_id}_{self._sim_number}")},
            "name": f"SIM {self._sim_number}",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM",
            "via_device": (DOMAIN, f"{self._account_id}_account"),
        }


# ================================================================
# Individual SIM DESCRIPTION sensors
# ================================================================
class AirBalticCardSimDescriptionSensor(CoordinatorEntity[Mapping[str, Any]], SensorEntity):
    """Sensor showing SIM card description/label."""

    _attr_icon = "mdi:label"
    _attr_translation_key = "sim_description"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        account_id: str,
        sim_number: str,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = account_id
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_description"
        self._attr_name = "Description"

    @property
    def _sim_data(self):
        data = self.coordinator.data or {}
        for sim in data.get("sims", []):
            if sim.get("number") == self._sim_number:
                return sim
        return None

    @property
    def native_value(self):
        sim = self._sim_data
        if not sim:
            return None
        return sim.get("name")

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._account_id}_{self._sim_number}")},
            "name": f"SIM {self._sim_number}",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM",
            "via_device": (DOMAIN, f"{self._account_id}_account"),
        }
