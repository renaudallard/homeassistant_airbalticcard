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

    for sim in coordinator.data.get("sims", []):
        sensors.append(AirBalticCardSimSensor(coordinator, sim["number"]))

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
        self._attr_name = "AirBalticCard Account Credit"

    @property
    def native_value(self):
        """Return account-level available credit."""
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
        self._attr_name = "AirBalticCard Total SIM Credit"

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
# Individual SIM sensors
# ================================================================
class AirBalticCardSimSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single SIM card balance sensor."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:sim"
    _attr_translation_key = "sim_balance"

    def __init__(self, coordinator, sim_number: str):
        super().__init__(coordinator)
        self._sim_number = sim_number
        self._attr_unique_id = f"{DOMAIN}_{sim_number}"

    @staticmethod
    def _parse_credit(text: str) -> float | None:
        """Convert text like '€10.17' to float."""
        try:
            return float(text.replace("€", "").replace(",", ".").strip())
        except Exception:
            return None

    @property
    def _sim_data(self):
        """Find current SIM entry."""
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
                return sim
        return None

    @property
    def native_value(self):
        """Return latest SIM credit dynamically."""
        sim = self._sim_data
        if not sim:
            return None
        return self._parse_credit(sim.get("credit", ""))

    @property
    def name(self):
        """Show SIM label in UI."""
        sim = self._sim_data
        if not sim:
            return f"SIM {self._sim_number} Balance"
        return f"{sim.get('name', self._sim_number)} Balance"

    @property
    def extra_state_attributes(self):
        """Expose SIM metadata."""
        sim = self._sim_data or {}
        return {
            "sim_number": sim.get("number", self._sim_number),
            "sim_name": sim.get("name"),
        }

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
