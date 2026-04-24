<p align="center">
  <img src="images/logo.png" alt="AirBalticCard logo" width="200">
</p>

<h1 align="center">AirBalticCard</h1>
<p align="center">Home Assistant Custom Integration</p>

<p align="center">
  Monitor <strong>AirBalticCard</strong> prepaid SIM account and balances directly in Home Assistant.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.2.1-blue" alt="Version">
  <img src="https://img.shields.io/badge/HA-2025.10%2B-41BDF5" alt="Home Assistant">
  <img src="https://img.shields.io/badge/Python-3.13%2B-3776AB" alt="Python">
  <img src="https://img.shields.io/badge/IoT%20class-cloud__polling-yellow" alt="IoT class">
  <img src="https://img.shields.io/badge/HACS-custom-orange" alt="HACS">
</p>

---

## Features

| | |
|---|---|
| **Account credit** | Total account balance in EUR |
| **Total SIM credit** | Sum of all SIM card balances |
| **Per-SIM balance** | Individual credit with status icons |
| **Per-SIM description** | SIM name / label |
| **Manual refresh** | Diagnostic button for on-demand updates |
| **Multi-account** | Safe per-account scoping with automatic migration |
| **Translations** | English, French |

### Balance status icons

| Balance | Icon | State |
|---------|------|-------|
| `< 2 EUR` | `mdi:sim-alert` | `critical` |
| `2 - 4 EUR` | `mdi:sim-off` | `warning` |
| `>= 4 EUR` | `mdi:sim` | `normal` |

---

## Installation

### HACS (preferred)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=renaudallard&repository=homeassistant_airbalticcard&category=integration)

1. Click the button above, or in **HACS > Integrations**, search for **AirBalticCard SIM Balance**.
   If it doesn't appear, add the repo as a **Custom repository**:
   `https://github.com/renaudallard/homeassistant_airbalticcard` (Integration)
2. Install, then **restart Home Assistant**.

### Manual

1. Copy `custom_components/airbalticcard/` into your HA config directory.
2. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**.
2. Search **AirBalticCard**.
3. Enter your **Username (or Email)** and **Password**.

### Options

Options take effect immediately, no reload needed.

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| Scan interval | `3600` s | 10 - 86400 | How often to poll for updates |
| Retry interval | `3600` s | 5 - 86400 | Wait time after a failed fetch |

---

## Entities

> Entity IDs depend on your system's naming. Examples below show typical patterns.

### Sensors

| Entity | Type | Device |
|--------|------|--------|
| `sensor.airbalticcard_account_credit` | Monetary (EUR) | Account |
| `sensor.airbalticcard_total_sim_credit` | Monetary (EUR) | Account |
| `sensor.sim_<number>_balance` | Monetary (EUR) | SIM |
| `sensor.sim_<number>_description` | Text | SIM |

Per-SIM balance sensors include extra attributes: `sim_number`, `sim_name`, `balance_state`.

Each SIM is registered as its own device linked to the parent account device.

### Button

| Entity | Category | Description |
|--------|----------|-------------|
| `button.airbalticcard_refresh` | Diagnostic | Triggers an immediate data fetch |

---

## Example: Lovelace

```yaml
type: entities
title: AirBalticCard
entities:
  - sensor.airbalticcard_account_credit
  - sensor.airbalticcard_total_sim_credit
  - button.airbalticcard_refresh
  - sensor.sim_3712xxxxxxx_balance
  - sensor.sim_3712xxxxxxx_description
```

---

## Troubleshooting

| Problem | Cause / Fix |
|---------|-------------|
| **Invalid auth** | Re-check username/password. Two-factor or captchas on the site can block login. |
| **Cannot connect** | Temporary site protection or downtime. The integration retries automatically. |
| **Slow first update** | The first fetch is awaited before entities are created. Subsequent updates run in the background. |
| **Empty/None data** | The site structure may have changed. Enable debug logs and open an issue. |

### Debug logging

```yaml
logger:
  default: warning
  logs:
    custom_components.airbalticcard: debug
```

Logs appear in **Settings > System > Logs** or in `home-assistant.log`.

---

## Privacy & Security

- Credentials are stored in Home Assistant's encrypted config entries.
- Data is only exchanged with **airbalticcard.com**.
- Uses HA's shared `aiohttp` session for connection pooling.

---

## Changelog

### 1.2.1
- Reduced redundant BeautifulSoup parsing (normal path from 2 parses to 1, re-auth from 5 to 3).
- Module-level HTTP timeout constant instead of per-request allocation.
- Reduced repeated SIM data lookups in balance sensor properties.

### 1.2.0
- Fixed session leak in config flow login validation.
- Eliminated redundant login on every poll cycle (3 HTTP requests reduced to 1).
- Cut first-load HTTP requests from 4 to 2 by reusing fetched HTML.
- Fixed false login failures from overly broad text matching.
- Fixed account credit parsing to search all sidebar blocks.
- Options changes now take effect immediately without reload.
- Config flow checks for duplicate accounts before network calls.
- Fixed AbortFlow being swallowed by generic exception handler.
- Added upper bound validation (86400s) for intervals.
- Removed unused `requests` dependency.
- Full type correctness (mypy clean).

### 1.1.4
- Modern HA patterns (type hints, dataclasses, entity naming).
- Account-scoped unique IDs and device registry entries.
- SIM devices linked through parent account device.

### 1.1.3
- README and i18n polish.

### 1.1.2
- HACS compatibility, coordinator improvements.

### 1.1.1 and earlier
- Initial release: async client, sensors, button, translations.

---

## Support & Contributions

- **Repository:** [github.com/renaudallard/homeassistant_airbalticcard](https://github.com/renaudallard/homeassistant_airbalticcard)
- **Issues:** Please include debug logs and your HA version.

Contributions welcome: bug reports, PRs, translations.

---

## License

MIT (see repository).
