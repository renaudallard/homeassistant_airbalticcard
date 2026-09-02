"""One-off migration of pre-1.2 registry entries to account-scoped IDs.

Older releases keyed devices and entities on the domain alone, so two accounts
collided. Everything is now prefixed with the config entry id. This runs from
async_migrate_entry, once per entry.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import ACCOUNT_MODEL, DOMAIN, MANUFACTURER, SIM_MODEL

_LOGGER = logging.getLogger(__name__)


def _device_with(
    device_registry: dr.DeviceRegistry, entry: ConfigEntry, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """Return this entry's device carrying *identifier*, if it has one.

    async_get_device searches every config entry, which is both ambiguous when
    two accounts share a legacy identifier and deprecated for that reason
    (removal in Home Assistant 2027.8). Scoping the search to the entry is
    what this migration wanted all along.
    """
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if identifier in device.identifiers:
            return device
    return None


def async_migrate_registries(
    hass: HomeAssistant, entry: ConfigEntry, username: str
) -> None:
    """Rewrite the device and entity registries for *entry*."""
    _migrate_devices(hass, entry, username)
    _migrate_entity_unique_ids(hass, entry)


def _migrate_entity_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity unique IDs from the legacy format to account-scoped IDs."""
    registry = er.async_get(hass)
    migrated = 0

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        new_unique_id = map_legacy_unique_id(entity_entry.unique_id, entry.entry_id)
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


def _migrate_devices(hass: HomeAssistant, entry: ConfigEntry, username: str) -> None:
    """Migrate device registry identifiers to include the config entry scope."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    account_id = entry.entry_id

    account_identifier_old = (DOMAIN, "airbalticcard_account")
    account_identifier_new = (DOMAIN, f"{account_id}_account")

    account_device = _device_with(device_registry, entry, account_identifier_new)
    legacy_account_device = _device_with(device_registry, entry, account_identifier_old)
    migrated = 0

    if account_device is None:
        if legacy_account_device:
            device_registry.async_update_device(
                legacy_account_device.id,
                new_identifiers={account_identifier_new},
                name=f"AirBalticCard Account ({username})",
                manufacturer=MANUFACTURER,
                model=ACCOUNT_MODEL,
            )
            migrated += 1
            account_device = legacy_account_device
            legacy_account_device = None
    else:
        device_registry.async_update_device(
            account_device.id,
            name=f"AirBalticCard Account ({username})",
            manufacturer=MANUFACTURER,
            model=ACCOUNT_MODEL,
        )

        if legacy_account_device and legacy_account_device.id != account_device.id:
            # The legacy device still exists alongside the migrated one. Remove
            # it once all entities have been pointed at the new identifiers.
            if not _has_entities(entity_registry, entry, legacy_account_device.id):
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
                # A second legacy account device that could not be removed
                # earlier. Drop it once no entity points at it any more.
                if not _has_entities(entity_registry, entry, device_entry.id):
                    device_registry.async_remove_device(device_entry.id)
                    migrated += 1
            else:
                device_registry.async_update_device(
                    device_entry.id,
                    new_identifiers={account_identifier_new},
                    name=f"AirBalticCard Account ({username})",
                    manufacturer=MANUFACTURER,
                    model=ACCOUNT_MODEL,
                )
                account_device_id = device_entry.id
                migrated += 1
            continue

        value = identifier[1]

        if value.startswith(f"{account_id}_"):
            # Already migrated; make sure the hierarchy is right.
            if account_device_id and device_entry.via_device_id != account_device_id:
                device_registry.async_update_device(
                    device_entry.id, via_device_id=account_device_id
                )
            continue

        new_identifier = (DOMAIN, f"{account_id}_{value}")

        update_kwargs: dict[str, Any] = {
            "manufacturer": MANUFACTURER,
            "model": SIM_MODEL,
        }

        should_update_identifiers = new_identifier not in device_entry.identifiers
        if should_update_identifiers:
            update_kwargs["new_identifiers"] = {new_identifier}

        if account_device_id and device_entry.via_device_id != account_device_id:
            update_kwargs["via_device_id"] = account_device_id

        existing_device = _device_with(device_registry, entry, new_identifier)

        if existing_device and existing_device.id != device_entry.id:
            # Entities referencing the legacy SIM device must be reassigned to
            # the already-migrated scoped device before the duplicate can go.
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            ):
                if entity_entry.device_id != device_entry.id:
                    continue
                entity_registry.async_update_entity(
                    entity_entry.entity_id, device_id=existing_device.id
                )

            existing_update_kwargs: dict[str, Any] = {
                "manufacturer": MANUFACTURER,
                "model": SIM_MODEL,
            }
            if account_device_id and existing_device.via_device_id != account_device_id:
                existing_update_kwargs["via_device_id"] = account_device_id

            device_registry.async_update_device(
                existing_device.id, **existing_update_kwargs
            )
            device_registry.async_remove_device(device_entry.id)
            migrated += 1
            continue

        if should_update_identifiers or len(update_kwargs) > 2:
            device_registry.async_update_device(device_entry.id, **update_kwargs)
            migrated += 1

    if migrated:
        _LOGGER.info(
            "Migrated %d AirBalticCard device registry entries to account-scoped IDs",
            migrated,
        )


def _has_entities(
    entity_registry: er.EntityRegistry, entry: ConfigEntry, device_id: str
) -> bool:
    """Tell whether any entity of *entry* still points at *device_id*."""
    return any(
        entity_entry.device_id == device_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    )


def map_legacy_unique_id(unique_id: str, account_id: str) -> str | None:
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

    if suffix.endswith(("_balance", "_description")):
        sim_part, sensor_suffix = suffix.rsplit("_", 1)
        if sim_part:
            return f"{scoped_prefix}{sim_part}_{sensor_suffix}"

    return None
