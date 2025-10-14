import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirBalticCard sensors from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    sensors = [
        AirBalticCardAccountSensor(coordinator),
        AirBalticCardTotalSimCreditSensor(coordinator),
    ]

    # Create per-SIM sensors: balance + description
    for sim in coordinator.data.get("sims", []):
        sim_number = sim["number"]
        sensors.append(AirBalticCardSimBalanceSensor(coordinator, sim_number))
        sensors.append(AirBalticCardSimDescriptionSensor(coordinator, sim_number))

    async_add_entities(sensors, update_before_add=True)


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
        """Return total sum of all SIM credits."""
        sims = self.coordinator.data.get("sims", [])
        total = 0.0
        for sim in sims:
            try:
                val = sim.get("credit", "").replace("€", "").replace(",", ".").strip()
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
            "identifiers": {(DOMAIN, "airbalticcard_account")},
            "name": "AirBalticCard Account",
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM Platform",
        }


# ================================================================
# Individual SIM BALANCE sensors (with dynamic icons + severity attribute)
# ================================================================
class AirBalticCardSimBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the balance of a SIM card with color-coded icons."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO

    def __init__(self, coordinator, sim_number: str):
        super().__init__(coordinator)
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{sim_number}_balance"
        self._attr_name = f"{sim_number} Balance"

    @staticmethod
    def _parse_credit(text: str) -> float | None:
        """Convert text like '€10.17' to float."""
        try:
            return float(text.replace("€", "").replace(",", ".").strip())
        except Exception:
            return None

    @property
    def _sim_data(self):
        """Find SIM info by number."""
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
                return sim
        return None

    @property
    def native_value(self):
        """Return balance as a float."""
        sim = self._sim_data
        if not sim:
            return None
        return self._parse_credit(sim.get("credit", ""))

    @property
    def icon(self):
        """Dynamic icon based on balance severity."""
        val = self.native_value
        if val is None:
            return "mdi:sim"
        if val < 2:
            # Critical level — red in most HA themes
            return "mdi:sim-alert"
        elif val < 4:
            # Warning level — orange/yellow
            return "mdi:sim-off"
        return "mdi:sim"

    @property
    def extra_state_attributes(self):
        """Add SIM metadata and severity for automations or dashboards."""
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
            "balance_state": severity
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
    """Sensor showing the SIM card's description/label."""

    _attr_icon = "mdi:label"
    _attr_translation_key = "sim_description"

    def __init__(self, coordinator, sim_number: str):
        super().__init__(coordinator)
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{sim_number}_description"
        self._attr_name = f"{sim_number} Description"

    @property
    def _sim_data(self):
        """Find SIM info by number."""
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
                return sim
        return None

    @property
    def native_value(self):
        """Return SIM label (the name from dashboard)."""
        sim = self._sim_data
        if not sim:
            return
