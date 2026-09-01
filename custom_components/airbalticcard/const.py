"""Constants for the AirBalticCard integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "airbalticcard"

# Configuration options
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_RETRY_INTERVAL: Final = "retry_interval"

# Default intervals, in seconds
DEFAULT_SCAN_INTERVAL: Final = 3600
DEFAULT_RETRY_INTERVAL: Final = 3600

# Accepted range for both intervals, in seconds
MIN_SCAN_INTERVAL: Final = 10
MIN_RETRY_INTERVAL: Final = 5
MAX_INTERVAL: Final = 86400

# Device registry labels
MANUFACTURER: Final = "AirBaltic"
ACCOUNT_MODEL: Final = "Prepaid SIM Platform"
SIM_MODEL: Final = "Prepaid SIM"

# Balance thresholds driving the SIM icon and the balance_state attribute
BALANCE_CRITICAL: Final = 2.0
BALANCE_WARNING: Final = 4.0

PLATFORMS: Final = (Platform.SENSOR, Platform.BUTTON)
