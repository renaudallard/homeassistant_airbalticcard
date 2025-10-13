import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirBalticCard sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    sensors = []

    # --- Account-level sensor ---
    if coordinator.data.get("account_credit") is not None:
        sensors.append(AirBalticCardAccountSensor(coordinator))

    # --- Total SIM credit sensor ---
    if coordinator.data.get("sims"):
        sensors.append(AirBalticCardTotalSimCreditSensor(coordinator))

    # --- Individual SIM sensors ---
    for sim in coordinator.data.get("sims", []):
        sensors.append(AirBalticCardSimSensor(coordinator, sim))

    async_add_entities(sensors, update_before_add=True)


# ================================================================
# Account-level sensor
# ================================================================
class AirBalticCardAccountSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing total account credit."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:wallet"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "AirBalticCard Account Credit"
        self._attr_unique_id = f"{DOMAIN}_account_credit"

    @property
    def native_value(self):
        """Return account-level available credit."""
        try:
            return float(self.coordinator.data.get("account_credit") or 0)
        except Exception:
            return None

    @property
    def available(self):
        return self.coordinator.last_update_success


# ================================================================
# Total SIM Credit sensor
# ================================================================
class AirBalticCardTotalSimCreditSensor(CoordinatorEntity, SensorEntity):
    """Sensor summing all SIM card balances."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "AirBalticCard Total SIM Credit"
        self._attr_unique_id = f"{DOMAIN}_total_sim_credit"

    @property
    def native_value(self):
        """Return total sum of all SIM credits."""
        total = 0.0
        for sim in self.coordinator.data.get("sims", []):
            try:
                credit = float(sim["credit"].replace("€", "").replace(",", ".").strip())
                total += credit
            except Exception:
                pass
        return round(total, 2)

    @property
    def available(self):
        return self.coordinator.last_update_success


# ================================================================
# Individual SIM sensors
# ================================================================
class AirBalticCardSimSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single SIM card balance sensor."""

    _attr_device_class = "monetary"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:sim"

    def __init__(self, coordinator, sim):
        super().__init__(coordinator)
        self._sim_number = sim["number"]
        self._sim_name = sim["name"]
        self._attr_unique_id = f"airbalticcard_{self._sim_number}"
        self._attr_name = f"{self._sim_name} Balance"
        self._attr_native_value = self._parse_credit(sim["credit"])

    @staticmethod
    def _parse_credit(text):
        """Convert text like '€10.17' to float."""
        try:
            val = text.replace("€", "").replace(",", ".").strip()
            return float(val)
        except Exception:
            return None

    @property
    def native_value(self):
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Show SIM metadata."""
        return {
            "sim_number": self._sim_number,
            "sim_name": self._sim_name,
        }

    def _handle_coordinator_update(self):
        """Update sensor values when coordinator refreshes."""
        for sim in self.coordinator.data.get("sims", []):
            if sim["number"] == self._sim_number:
                self._attr_native_value = self._parse_credit(sim["credit"])
                self._sim_name = sim["name"]
                self.async_write_ha_state()
                break
