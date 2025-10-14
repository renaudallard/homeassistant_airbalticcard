import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirBalticCard sensors (blocking, data ready at startup)."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    sensors = []

    # --- Account-level sensor ---
    if coordinator.data.get("account_credit") is not None:
        sensors.append(AirBalticCardAccountSensor(coordinator))

    # --- Total SIM credit sensor ---
    if coordinator.data.get("sims"):
        sensors.append(AirBalticCardTotalSimCreditSensor(coordinator))

    # --- Individual SIM sensors (balance + description) ---
    for sim in coordinator.data.get("sims", []):
        sim_number = sim["number"]
        sensors.append(AirBalticCardSimBalanceSensor(coordinator, sim_number))
        sensors.append(AirBalticCardSimDescriptionSensor(coordinator, sim_number))

    async_add_entities(sensors, update_before_add=True)

    _LOGGER.debug(
        "AirBalticCard sensors set up with %d SIM(s).", len(coordinator.data.get("sims", []))
    )


# ================================================================
# Account-level sensor
# ================================================================
class AirBalticCardAccountSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing total account credit."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:wallet"
    _attr_translation_key = "account_credit"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_account_credit"
        self._attr_name = "Account Credit"

    @property
    def native_value(self):
        val = self.coordinator.data.get("account_credit")
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
            "identifiers": {(DOMAIN, "airbalticcard_account")},
            "name": "AirBalticCard Account",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }


# ================================================================
# Total SIM Credit sensor
# ================================================================
class AirBalticCardTotalSimCreditSensor(CoordinatorEntity, SensorEntity):
    """Sensor summing all SIM card balances."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:cash-multiple"
    _attr_translation_key = "total_sim_credit"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_total_sim_credit"
        self._attr_name = "Total SIM Credit"

    @property
    def native_value(self):
        total = 0.0
        for sim in self.coordinator.data.get("sims", []):
            try:
                val = sim.get("credit", "").replace("€", "").replace(",", ".").strip()
                total += float(val)
            except Exception:
                continue
        return round(total, 2)

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "airbalticcard_account")},
            "name": "AirBalticCard Account",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }


# ================================================================
# Individual SIM BALANCE sensors (with dynamic icons + severity)
# ================================================================
class AirBalticCardSimBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing SIM card balance with dynamic icons."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO

    def __init__(self, coordinator, sim_number: str):
        super().__init__(coordinator)
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{sim_number}_balance"
        self._attr_name = f"{sim_number} Balance"

    @staticmethod
    def _parse_credit(text: str) -> float | None:
        try:
            return float(text.replace("€", "").replace(",", ".").strip())
        except Exception:
            return None

    @property
    def _sim_data(self):
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
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
            "identifiers": {(DOMAIN, self._sim_number)},
            "name": f"SIM {self._sim_number}",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM",
        }


# ================================================================
# Individual SIM DESCRIPTION sensors
# ================================================================
class AirBalticCardSimDescriptionSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing SIM card description/label."""

    _attr_icon = "mdi:label"
    _attr_translation_key = "sim_description"

    def __init__(self, coordinator, sim_number: str):
        super().__init__(coordinator)
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{sim_number}_description"
        self._attr_name = f"{sim_number} Description"

    @property
    def _sim_data(self):
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
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
            "identifiers": {(DOMAIN, self._sim_number)},
            "name": f"SIM {self._sim_number}",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM",
        }
