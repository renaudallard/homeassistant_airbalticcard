# 💳 AirBalticCard SIM Balance for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![version](https://img.shields.io/badge/version-1.1.2-blue.svg)](https://github.com/renaudallard/homeassistant_airbalticcard)
[![license](https://img.shields.io/github/license/renaudallard/homeassistant_airbalticcard.svg)](LICENSE)

Monitor your **AirBalticCard prepaid SIM cards** and **account balance** directly in [Home Assistant](https://www.home-assistant.io/).  
This integration automatically fetches SIM balances and account credit, updates them on a schedule, and allows manual refresh from the dashboard.

---

## ✨ Features

- 🔐 Secure login to your AirBalticCard account  
- 📱 Displays **each SIM card balance** and **its label/description**  
- 💰 Shows **total account credit** and **total SIM balance**  
- 🎨 Dynamic icon colors for SIM balances:
  - 🟥 **Red** — Critical (< €2)
  - 🟧 **Orange** — Warning (< €4)
  - 🟩 **Normal** — Healthy balance  
- 🔄 Manual refresh button  
- 🌐 Fully translated — **English** 🇬🇧 and **French** 🇫🇷  
- ⚙️ Configurable scan and retry intervals  
- 🧠 Uses Home Assistant’s `DataUpdateCoordinator` for efficient async updates

---

## 🛠️ Installation

### 📦 Option 1 — via [HACS (Custom Repository)](https://hacs.xyz/)

1. Go to **HACS → Integrations → 3-dot menu → Custom repositories**.  
2. Add the repository URL:  
Category: **Integration**
3. Search for **AirBalticCard SIM Balance** in HACS and install it.
4. Restart Home Assistant.

---

### 📂 Option 2 — Manual installation

1. Download the latest release ZIP from [GitHub Releases](https://github.com/renaudallard/homeassistant_airbalticcard/releases).  
2. Extract the folder `airbalticcard` into your Home Assistant config folder:
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to  
**Settings → Devices & Services → + Add Integration → AirBalticCard SIM Balance**
2. Enter your **AirBalticCard username and password**
3. Adjust optional settings:
- **Scan interval** — how often to update data (default 3600 s)
- **Retry interval** — how often to retry on connection failure (default 3600 s)

No YAML configuration is required.

---

## 🧾 Entities Created

| Entity | Example Name | Description |
|--------|---------------|--------------|
| `sensor.account_credit` | `Account Credit` | Account-level credit (€) |
| `sensor.total_sim_credit` | `Total SIM Credit` | Sum of all SIM credits (€) |
| `sensor.<number>_balance` | `+37120012345 Balance` | Individual SIM balance, dynamic color icon |
| `sensor.<number>_description` | `+37120012345 Description` | SIM name/label |
| `button.airbalticcard_refresh` | `AirBalticCard Refresh` | Manually refresh data |

---

## 🎨 Icon Colors (Balance Thresholds)

| Balance (€) | Icon | Severity | Typical HA Color |
|--------------|------|-----------|------------------|
| ≥ 4 € | `mdi:sim` | Normal | Gray / Green |
| 2 – 3.99 € | `mdi:sim-off` | Warning | Orange |
| < 2 € | `mdi:sim-alert` | Critical | Red |

Each SIM balance entity also exposes an attribute `balance_state` with values:
`normal`, `warning`, or `critical`.

---

## 🧠 Technical Details

- Uses **async/await** throughout — fully non-blocking.  
- Data is fetched via **aiohttp** and parsed with **BeautifulSoup4**.  
- Coordinated via Home Assistant’s `DataUpdateCoordinator`.  
- Automatically retries and re-authenticates when the session expires.  
- Compatible with **Python ≥ 3.13** and **Home Assistant 2025.10+**.

---

## 🌐 Translations

| Language | File |
|-----------|------|
| English | `translations/en.json` |
| French | `translations/fr.json` |

More translations are welcome via pull requests.

---

## 📸 Screenshots

*(Add your own screenshots here once installed)*  
You can show the entities in a card or custom dashboard:

```yaml
type: entities
title: AirBalticCard
entities:
- sensor.account_credit
- sensor.total_sim_credit
- sensor.+37120012345_balance
- sensor.+37120012345_description
- button.airbalticcard_refresh
