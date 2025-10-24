# AirBalticCard — Home Assistant Custom Integration

Monitor **AirBalticCard** account and SIM balances directly in Home Assistant.

- **Integration domain:** `airbalticcard`
- **Version:** 1.1.6
- **HA Compatibility:** Home Assistant **2025.10** (and later)
- **Python:** 3.13+
- **IoT class:** `cloud_polling`
- **Config Flow:** ✅ (UI-based)
- **Translations:** English, French
- **Platforms:** `sensor`, `button`

---

## What it does

- Logs in to **airbalticcard.com** using your credentials.
- Fetches **account credit** and **per-SIM balances**.
- Exposes:
  - **Account credit** sensor (EUR)
  - **Total SIM credit** sensor (EUR)
  - **Per-SIM credit** sensors (EUR)
  - **Per-SIM description/name** sensors
- Provides a **Manual Refresh** button entity (diagnostics category) tied to the account device.
- Automatically migrates legacy entity and device identifiers to account-scoped formats for safe multi-account setups.
- Balance icon coloring:
  - **Red** when `< €2`
  - **Orange** when `< €4`
  - **Default** when `≥ €4`
- Adds a `balance_state` attribute: `critical | warning | normal`.

---

## Installation

### Option A — HACS (preferred)

1. In **HACS → Integrations**, search for **AirBalticCard SIM Balance**.
   - If it doesn’t appear, add the repo as a **Custom repository**:
     `https://github.com/renaudallard/homeassistant_airbalticcard` (Integration)
2. Install, then **Restart Home Assistant**.

### Option B — Manual

1. Copy the folder `custom_components/airbalticcard/` into your HA `config` directory.
2. Ensure these files are present:

```
custom_components/airbalticcard/
├── __init__.py
├── airbalticcard_api.py
├── button.py
├── config_flow.py
├── const.py
├── manifest.json
├── models.py
├── sensor.py
├── strings.json
└── translations/
    ├── en.json
    └── fr.json
```

3. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search **AirBalticCard**.
3. Enter your **Username (or Email)** and **Password**.
4. Finish the flow.

### Options (can be changed later)

- **Scan interval** (seconds, default `3600`) — periodic update frequency.
- **Retry interval** (seconds, default `3600`) — wait time after a failed attempt.

---

## Entities

> Exact entity IDs depend on your system’s naming. Examples below illustrate typical patterns.

### Sensors

- **Account credit**
  `sensor.airbalticcard_account_credit` (EUR)

- **Total SIM credit**
  `sensor.airbalticcard_total_sim_credit` (EUR)

- **Per-SIM credit**
  `sensor.sim_<number>_balance` (EUR)
  Attributes:
  - `sim_number`
  - `sim_name`
  - `balance_state` → `critical | warning | normal`

- **Per-SIM description/name**
  `sensor.sim_<number>_description` (text)

> Each SIM is registered as its own device linked via the parent AirBalticCard account device for better grouping in the Devices & Entities view.

> Icon coloring on SIM credit sensors follows the thresholds listed above.

### Button

- **Manual Refresh**
  `button.airbalticcard_refresh`
  Diagnostic button that triggers an immediate data fetch for the configured account.

---

## Example: Lovelace (Entities card)

```yaml
type: entities
title: AirBalticCard
entities:
  - sensor.airbalticcard_account_credit
  - sensor.airbalticcard_total_sim_credit
  - button.airbalticcard_refresh
  # Example SIMs (your entity IDs will differ)
  - sensor.sim_3712xxxxxxx_balance
  - sensor.sim_3712xxxxxxx_description
```

---

## Troubleshooting

- **Invalid auth**: Re-check username/password. Two-factor or captchas on the website can block programmatic login.
- **Cannot connect**: Temporary site protection or downtime. The integration will retry per the **Retry interval**.
- **Slow first update**: Initial fetch is synchronous to ensure data availability; subsequent updates are coordinated.
- **Empty/None data**: If the site structure changes, enable **Debug logs** and open an issue (see below).

### Enable debug logging

```yaml
logger:
  default: warning
  logs:
    custom_components.airbalticcard: debug
```

Logs appear in **Settings → System → Logs** (or in `home-assistant.log`).

---

## Privacy & Security

- Credentials are stored in Home Assistant’s config entries.
- No data is sent anywhere except to **airbalticcard.com** for fetching your balances.
- Uses HA’s shared `aiohttp` session for connection pooling.

---

## Changelog

### 1.1.4
- Refactored the integration to modern Home Assistant patterns (type hints, dataclasses, entity naming).
- Scoped entity unique IDs and device registry entries per account, ensuring safe multi-account use and smooth migration.
- Updated device metadata hierarchy so SIM devices link through the parent AirBalticCard account.

### 1.1.3
- README refresh with clear HA 2025.10 compatibility statement.
- Clarified entities and attributes; improved troubleshooting section.
- Minor i18n wording polish.

### 1.1.2
- HACS compatibility, badges and metadata updates.
- Improved coordinator behavior and logging.

### 1.1.1 and earlier
- Initial async client, sensors, manual refresh button, color thresholds, and translations.

---

## Support & Contributions

- **Repository:** `https://github.com/renaudallard/homeassistant_airbalticcard`
- **Issues:** Please include debug logs and your HA version.

Contributions welcome: bug reports, PRs, translations.

---

## License

MIT (see repository).
