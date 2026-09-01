"""Sensor entities for the AirBalticCard integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BALANCE_CRITICAL, BALANCE_WARNING, DOMAIN
from .coordinator import AirBalticCardCoordinator
from .entity import AirBalticCardAccountEntity, AirBalticCardSimEntity

if TYPE_CHECKING:
    from . import AirBalticCardConfigEntry


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
    """Credit available on the account itself."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:wallet"
    _attr_translation_key = "account_credit"

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, username: str
    ) -> None:
        """Set the account-scoped unique ID."""
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_account_credit"

    @property
    def native_value(self) -> float | None:
        """Return the account credit."""
        return self.coordinator.data.get("account_credit")


class AirBalticCardTotalSimCreditSensor(AirBalticCardAccountEntity, SensorEntity):
    """Sum of the balances of every SIM on the account."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-multiple"
    _attr_translation_key = "total_sim_credit"

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, username: str
    ) -> None:
        """Set the account-scoped unique ID."""
        super().__init__(coordinator, account_id, username)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_total_sim_credit"

    @property
    def native_value(self) -> float | None:
        """Return the sum of the SIM balances.

        A total that quietly leaves out a SIM reads as the real figure, so it
        stays unknown until every balance on the account could be read.
        """
        sims = self.coordinator.data.get("sims", [])
        if not sims or any(sim.get("credit") is None for sim in sims):
            return None
        return round(sum(sim["credit"] for sim in sims), 2)


class AirBalticCardSimBalanceSensor(AirBalticCardSimEntity, SensorEntity):
    """Balance of a single SIM card."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2
    _attr_translation_key = "sim_balance"

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, sim_number: str
    ) -> None:
        """Set the account-scoped unique ID."""
        super().__init__(coordinator, account_id, sim_number)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_balance"

    @property
    def native_value(self) -> float | None:
        """Return the SIM balance."""
        sim = self.sim
        return sim.get("credit") if sim else None

    @property
    def icon(self) -> str:
        """Return an icon reflecting how low the balance is."""
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
        """Return the SIM identity and how urgent its balance is."""
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


class AirBalticCardSimDescriptionSensor(AirBalticCardSimEntity, SensorEntity):
    """Label given to a SIM card on the portal."""

    _attr_icon = "mdi:label"
    _attr_translation_key = "sim_description"

    def __init__(
        self, coordinator: AirBalticCardCoordinator, account_id: str, sim_number: str
    ) -> None:
        """Set the account-scoped unique ID."""
        super().__init__(coordinator, account_id, sim_number)
        self._attr_unique_id = f"{DOMAIN}_{account_id}_{sim_number}_description"

    @property
    def native_value(self) -> str | None:
        """Return the SIM label."""
        sim = self.sim
        return sim.get("name") if sim else None
