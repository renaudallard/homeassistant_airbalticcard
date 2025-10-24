"""Constants for the AirBalticCard integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "airbalticcard"

CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

# Configuration options
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_RETRY_INTERVAL: Final = "retry_interval"

# ⏱️ Default intervals: 3600 seconds = 1 hour
DEFAULT_SCAN_INTERVAL: Final = 3600
DEFAULT_RETRY_INTERVAL: Final = 3600

PLATFORMS: Final = (Platform.SENSOR, Platform.BUTTON)
