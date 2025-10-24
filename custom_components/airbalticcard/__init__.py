"""Integration setup for the AirBalticCard custom component."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .airbalticcard_api import AirBalticCardAPI
from .const import (
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .models import AirBalticCardRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AirBalticCard integration (YAML not supported)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirBalticCard from a config entry."""
    username: str = entry.data["username"]
    password: str = entry.data["password"]

    # Use HA’s shared aiohttp session
    session = async_get_clientsession(hass)
    api = AirBalticCardAPI(username, password, session=session)

    scan_interval: int = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    retry_interval: int = entry.options.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)

    coordinator_ref: dict[str, DataUpdateCoordinator[dict[str, Any]] | None] = {
        "coordinator": None
    }
    success_interval = timedelta(seconds=scan_interval)
    retry_interval_delta = timedelta(seconds=retry_interval)

    async def async_update_data() -> dict[str, Any]:
        """Fetch data periodically and handle errors."""
        try:
            await api.login()
            data = await api.get_sim_cards()
        except Exception as err:
            _LOGGER.warning(
                "Failed to fetch AirBalticCard data: %s (retry in %ss)",
                err,
                retry_interval,
            )
            coordinator_obj = coordinator_ref["coordinator"]
            if coordinator_obj and coordinator_obj.update_interval != retry_interval_delta:
                coordinator_obj.update_interval = retry_interval_delta
            raise UpdateFailed(f"Error communicating with AirBalticCard: {err}") from err

        coordinator_obj = coordinator_ref["coordinator"]
        if coordinator_obj and coordinator_obj.update_interval != success_interval:
            coordinator_obj.update_interval = success_interval

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=success_interval,
    )

    coordinator_ref["coordinator"] = coordinator

    # ⛔ Blocking: wait for the first refresh before entity setup
    await coordinator.async_config_entry_first_refresh()

    runtime_data = AirBalticCardRuntimeData(
        coordinator=coordinator,
        api=api,
        session=session,
        account_id=entry.entry_id,
        username=username,
    )

    hass.data[DOMAIN][entry.entry_id] = runtime_data
    entry.runtime_data = runtime_data

    await _async_migrate_device_entries(hass, entry, runtime_data)
    await _async_migrate_entity_unique_ids(hass, entry, runtime_data.account_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "AirBalticCard integration started for %s (scan=%ss, retry=%ss)",
        username,
        scan_interval,
        retry_interval,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up resources."""
    data: AirBalticCardRuntimeData | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if data:
        try:
            await data.api.close()
        except Exception as err:  # pragma: no cover - defensive safety net
            _LOGGER.debug("Error closing AirBalticCard API session: %s", err)

    if unload_ok:
        _LOGGER.info("AirBalticCard integration unloaded successfully")

    return unload_ok


async def _async_migrate_entity_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, account_id: str
) -> None:
    """Migrate entity unique IDs from legacy format to account-scoped IDs."""

    registry = er.async_get(hass)
    migrated = 0

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        new_unique_id = _map_legacy_unique_id(entity_entry.unique_id, account_id)
        if not new_unique_id or new_unique_id == entity_entry.unique_id:
            continue

        try:
            registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )
        except ValueError:
            _LOGGER.debug(
                "Skipping unique ID migration for %s; target ID %s already in use",
                entity_entry.entity_id,
                new_unique_id,
            )
        else:
            migrated += 1

    if migrated:
        _LOGGER.info(
            "Migrated %d AirBalticCard entity unique IDs to account-scoped format",
            migrated,
        )


async def _async_migrate_device_entries(
    hass: HomeAssistant, entry: ConfigEntry, runtime_data: AirBalticCardRuntimeData
) -> None:
    """Migrate device registry identifiers to include the config entry scope."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    account_identifier_old = (DOMAIN, "airbalticcard_account")
    account_identifier_new = (DOMAIN, f"{runtime_data.account_id}_account")

    account_device = device_registry.async_get_device({account_identifier_new})
    legacy_account_device = device_registry.async_get_device({account_identifier_old})
    migrated = 0

    if account_device is None:
        if legacy_account_device and entry.entry_id in legacy_account_device.config_entries:
            device_registry.async_update_device(
                legacy_account_device.id,
                new_identifiers={account_identifier_new},
                name=f"AirBalticCard Account ({runtime_data.username})",
                manufacturer="AirBaltic",
                model="Prepaid SIM Platform",
            )
            migrated += 1
            account_device = legacy_account_device
            legacy_account_device = None
    else:
        device_registry.async_update_device(
            account_device.id,
            name=f"AirBalticCard Account ({runtime_data.username})",
            manufacturer="AirBaltic",
            model="Prepaid SIM Platform",
        )

        if (
            legacy_account_device
            and legacy_account_device.id != account_device.id
            and entry.entry_id in legacy_account_device.config_entries
        ):
            # The legacy device still exists alongside the migrated one. Remove it
            # once all entities have been pointed at the new identifiers.
            legacy_entities_present = any(
                entity_entry.device_id == legacy_account_device.id
                for entity_entry in er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                )
            )
            if not legacy_entities_present:
                device_registry.async_remove_device(legacy_account_device.id)
                migrated += 1
            else:
                _LOGGER.debug(
                    "Skipping removal of legacy AirBalticCard account device %s due to"
                    " remaining entity references",
                    legacy_account_device.id,
                )

    account_device_id = account_device.id if account_device else None

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if device_entry.id == account_device_id:
            continue

        identifiers = {
            identifier
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }
        if not identifiers:
            continue

        identifier = identifiers.pop()

        if identifier == account_identifier_new:
            continue
        if identifier == account_identifier_old:
            if account_device_id and device_entry.id != account_device_id:
                # Legacy account device that could not be removed earlier because it
                # still had identifiers pointing to the old format. Remove it if no
                # entities remain attached.
                legacy_entities_present = any(
                    entity_entry.device_id == device_entry.id
                    for entity_entry in er.async_entries_for_config_entry(
                        entity_registry, entry.entry_id
                    )
                )
                if not legacy_entities_present:
                    device_registry.async_remove_device(device_entry.id)
                    migrated += 1
            else:
                device_registry.async_update_device(
                    device_entry.id,
                    new_identifiers={account_identifier_new},
                    name=f"AirBalticCard Account ({runtime_data.username})",
                    manufacturer="AirBaltic",
                    model="Prepaid SIM Platform",
                )
                account_device_id = device_entry.id
                migrated += 1
            continue

        value = identifier[1]

        if value.startswith(f"{runtime_data.account_id}_"):
            # Already migrated; ensure hierarchy is correct.
            if account_device_id and device_entry.via_device_id != account_device_id:
                device_registry.async_update_device(
                    device_entry.id, via_device_id=account_device_id
                )
            continue

        new_identifier = (DOMAIN, f"{runtime_data.account_id}_{value}")
        update_kwargs: dict[str, Any] = {
            "new_identifiers": {new_identifier},
            "manufacturer": "AirBaltic",
            "model": "Prepaid SIM",
        }
        if account_device_id:
            update_kwargs["via_device_id"] = account_device_id

        existing_device = device_registry.async_get_device({new_identifier})

        if existing_device and existing_device.id != device_entry.id:
            # Entities referencing the legacy SIM device must be reassigned to the
            # already-migrated scoped device before we can remove the duplicate.
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            ):
                if entity_entry.device_id != device_entry.id:
                    continue
                entity_registry.async_update_entity(
                    entity_entry.entity_id, device_id=existing_device.id
                )

            existing_update_kwargs: dict[str, Any] = {
                "manufacturer": "AirBaltic",
                "model": "Prepaid SIM",
            }
            if account_device_id and existing_device.via_device_id != account_device_id:
                existing_update_kwargs["via_device_id"] = account_device_id

            device_registry.async_update_device(
                existing_device.id, **existing_update_kwargs
            )
            device_registry.async_remove_device(device_entry.id)
            migrated += 1
            continue

        device_registry.async_update_device(device_entry.id, **update_kwargs)
        migrated += 1

    if migrated:
        _LOGGER.info(
            "Migrated %d AirBalticCard device registry entries to account-scoped IDs",
            migrated,
        )


def _map_legacy_unique_id(unique_id: str, account_id: str) -> str | None:
    """Return the migrated unique ID for a legacy entity, if applicable."""

    prefix = f"{DOMAIN}_"
    scoped_prefix = f"{DOMAIN}_{account_id}_"

    if unique_id.startswith(scoped_prefix):
        return None
    if not unique_id.startswith(prefix):
        return None

    suffix = unique_id[len(prefix) :]

    if suffix in {"account_credit", "total_sim_credit", "refresh"}:
        return f"{scoped_prefix}{suffix}"

    if suffix.endswith("_balance") or suffix.endswith("_description"):
        sim_part, sensor_suffix = suffix.rsplit("_", 1)
        if sim_part:
            return f"{scoped_prefix}{sim_part}_{sensor_suffix}"

    return None
