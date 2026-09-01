"""Data models for the AirBalticCard integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass(slots=True)
class AirBalticCardRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: DataUpdateCoordinator[dict[str, Any]]
    account_id: str
    username: str
