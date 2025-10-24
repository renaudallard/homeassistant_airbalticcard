"""Data models for the AirBalticCard integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aiohttp import ClientSession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from .airbalticcard_api import AirBalticCardAPI


@dataclass(slots=True)
class AirBalticCardRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: DataUpdateCoordinator[dict[str, Any]]
    api: "AirBalticCardAPI"
    session: ClientSession
    account_id: str
    username: str
