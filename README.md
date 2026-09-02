<p align="center">
  <img src="images/logo.png" alt="AirBalticCard logo" width="200">
</p>

<h1 align="center">AirBalticCard</h1>
<p align="center">Home Assistant Custom Integration</p>

<p align="center">
  Monitor <strong>AirBalticCard</strong> prepaid SIM account and balances directly in Home Assistant.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.3.2-blue" alt="Version">
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
| **Total SIM credit** | Sum of all SIM balances, unknown if any cannot be read |
| **Per-SIM balance** | Individual credit with status icons |
| **Per-SIM description** | SIM name / label |
| **Manual refresh** | Diagnostic button for on-demand updates |
| **Multi-account** | Each account polls with its own session and its own devices |
| **Reauthentication** | Prompts for a new password instead of retrying forever |
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

Saving options reloads the integration, so a new interval applies straight away.

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| Scan interval | `3600` s | 10 - 86400 | How often to poll for updates |
| Retry interval | `3600` s | 5 - 86400 | Wait time after a failed fetch |

---

## Entities

> Entity IDs are built from the device name, so the account ones carry your login.

### Sensors

| Entity | Type | Device |
|--------|------|--------|
| `sensor.airbalticcard_account_<login>_account_credit` | Monetary (EUR) | Account |
| `sensor.airbalticcard_account_<login>_total_sim_credit` | Monetary (EUR) | Account |
| `sensor.sim_<number>_balance` | Monetary (EUR) | SIM |
| `sensor.sim_<number>_description` | Text | SIM |

`<login>` is your username slugified, because the account device is named
after it. Check the real IDs under **Settings > Devices & Services >
Entities** rather than typing them from here.

Per-SIM balance sensors include extra attributes: `sim_number`, `sim_name`, `balance_state`.

Each SIM is registered as its own device linked to the parent account device.

### Button

| Entity | Category | Description |
|--------|----------|-------------|
| `button.airbalticcard_account_<login>_manual_refresh` | Diagnostic | Triggers an immediate data fetch |

---

## Example: Lovelace

```yaml
type: entities
title: AirBalticCard
entities:
  # Replace these with the IDs your install actually registered.
  - sensor.airbalticcard_account_john_example_com_account_credit
  - sensor.airbalticcard_account_john_example_com_total_sim_credit
  - button.airbalticcard_account_john_example_com_manual_refresh
  - sensor.sim_3712xxxxxxx_balance
  - sensor.sim_3712xxxxxxx_description
```

---

## Troubleshooting

| Problem | Cause / Fix |
|---------|-------------|
| **Invalid auth** | Home Assistant asks for the password again. Two-factor or captchas on the site can block login. |
| **Cannot connect** | Temporary site protection or downtime. The integration retries automatically. |
| **Slow first update** | The first fetch is awaited before entities are created. Subsequent updates run in the background. |
| **Unknown balance** | A balance that cannot be read stays unknown rather than showing 0. Enable debug logs and open an issue. |
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

- Your password is stored in Home Assistant's config entries, which are plain
  JSON under `.storage/`. Anyone who can read your config directory or an
  unencrypted backup can read it, so treat those accordingly.
- Data is only exchanged with **airbalticcard.com**.
- Each account uses its own `aiohttp` session, so logins never mix between accounts.

---

## Changelog

### 1.3.2
- The SIM sensors no longer read unavailable after a restart. Since 1.3.1 they
  were only created when the entity registry did not already know them, which
  is true exactly once, so every later start restored the registry entries
  with no entity behind them.
- The account credit is read again on pages that print a currency marker on
  both sides of the amount, as in "€70.00 EUR", which is what the portal
  sends.

### 1.3.1
- Deleting a device no longer errors when the integration is not loaded; the
  action was offered but crashed on the missing runtime data.
- Entries upgraded from 1.2.x get their unique ID normalised, so the account
  they already hold is recognised and cannot be added a second time.
- The account credit is held to the same amount-only check as the SIM
  balances; text alongside the amount published a garbage figure before.
- Account pages are parsed in the thread pool instead of on the event loop,
  which a 12-SIM page was blocking for over 400 ms per poll.
- A SIM whose stale device was deleted gets its sensors back if it returns.
- The RuntimeError aiohttp raises on a detached session is contained.
- The registry migration no longer uses a device lookup Home Assistant is
  removing in 2027.8, and scopes its search to the config entry.
- `already_in_progress` is translated.
- A release is published only after the checks pass, and never with a version
  older than the one already out.
- Tests now drive a real Home Assistant across the migration, the SIM
  lifecycle and the device-removal hook; two parsing tests that passed for the
  wrong reason were rewritten.
- README: corrected the entity IDs, the Lovelace example and the claim that
  credentials are stored encrypted.
- CI runs on actions that target Node 24, and the Home Assistant test harness
  is pinned so it cannot resolve to a prerelease its own fixtures reject.

### 1.3.0
- Fixed the options dialog crashing on Home Assistant 2025.12 and later.
- Each account now polls with its own HTTP session; two accounts no longer
  overwrote each other's login and reported the wrong balances.
- Balances are read whether the currency sits before or after the amount, and
  in either decimal convention. An unreadable balance stays unknown instead of
  being reported as 0.00 and raising a false low-balance alert.
- The login check no longer mistakes a menu link or a script for a session.
- A rejected password now asks for a new one instead of retrying forever.
- The manual refresh button stays available after a failed update.
- Saving options reloads the entry, so a new interval applies straight away.
- SIM cards added to the account appear without restarting Home Assistant.
- Dropped a redundant fetch performed on every setup.
- Entity names come from the translation files again, so the French names show.
- Registry migration runs once through `async_migrate_entry` instead of on
  every startup.
- A request timeout is handled as a connection failure, so the retry interval
  applies to it and the config flow says so rather than reporting an
  unexpected error.
- Only a cell holding nothing but an amount counts as a balance, so a tariff
  or a plan name on the same row is not read as one.
- A reauthentication prompt appears only when the portal actually refused the
  password, not for a maintenance page.
- The SIM total stays unknown while any balance on the account is unreadable,
  instead of quietly leaving a SIM out.
- A SIM that has left the account can be deleted from the device page.
- The options form keeps what was typed when a value is out of range.
- `hacs.json` no longer hides the repository from HACS country filters.
- Adds the MIT license file, sorts the manifest keys, and runs hassfest, the
  HACS check, ruff and the tests in CI.

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

## Development

```sh
python -m venv venv && venv/bin/pip install -r tests/requirements.txt ruff
venv/bin/python -m pytest tests                        # parsing
venv/bin/python -m pytest tests/test_integration.py -c tests/pytest.ini
venv/bin/ruff check custom_components tests
venv/bin/ruff format --check custom_components tests
```

`tests/test_api_parsing.py` covers the page parsing and needs no Home
Assistant; `tests/test_integration.py` drives a real one and skips itself when
`pytest-homeassistant-custom-component` is not installed. Keep the venv out of
the repo root or add it to `.gitignore`.

---

## Support & Contributions

- **Repository:** [github.com/renaudallard/homeassistant_airbalticcard](https://github.com/renaudallard/homeassistant_airbalticcard)
- **Issues:** Please include debug logs and your HA version.

Contributions welcome: bug reports, PRs, translations.

---

## License

MIT. See [LICENSE](LICENSE).
