"""Data models for the AirBalticCard integration."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import AirBalticCardCoordinator


@dataclass(slots=True)
class AirBalticCardRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: AirBalticCardCoordinator
    account_id: str
    username: str
