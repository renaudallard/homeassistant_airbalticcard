import aiohttp
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any

_LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://airbalticcard.com/my-account/"
DASHBOARD_URL = "https://airbalticcard.com/my-account/"


class AirBalticCardAPI:
    """Async API client for AirBalticCard."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession | None = None):
        self._username = username
        self._password = password
        self._session = session
        self._own_session = False
        self._logged_in = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._own_session = True
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "HomeAssistant-AirBalticCard/1.7"}
            )
        return self._session

    async def close(self):
        if self._own_session and self._session:
            await self._session.close()

    async def _get_nonce(self) -> str:
        session = await self._get_session()
        async with session.get(LOGIN_URL, timeout=15) as resp:
            if resp.status != 200:
                raise ConnectionError(f"Login page unavailable (HTTP {resp.status})")
            text = await resp.text()
        soup = BeautifulSoup(text, "html.parser")
        nonce_input = soup.find("input", {"name": "woocommerce-login-nonce"})
        if not nonce_input:
            raise ConnectionError("Could not retrieve login nonce from page")
        nonce = nonce_input.get("value")
        if not nonce:
            raise ConnectionError("Login nonce field is empty")
        return nonce

    async def login(self):
        """Perform login."""
        session = await self._get_session()
        nonce = await self._get_nonce()

        payload = {
            "username": self._username,
            "password": self._password,
            "woocommerce-login-nonce": nonce,
            "login": "Log in",
        }

        async with session.post(LOGIN_URL, data=payload, allow_redirects=True, timeout=15) as resp:
            text = await resp.text()

        if not self._is_logged_in(text):
            raise ValueError("Invalid username or password")

        self._logged_in = True
        _LOGGER.info("Login successful for %s", self._username)

    def _is_logged_in(self, html: str) -> bool:
        """Check if user is logged in based on page content.

        Uses multiple indicators for robust authentication verification:
        - Presence of logout link
        - Absence of login form
        - Presence of WooCommerce error messages indicating failed login
        """
        soup = BeautifulSoup(html, "html.parser")

        # Check for WooCommerce error messages (indicates login failure)
        error_indicators = [
            soup.find("ul", class_="woocommerce-error"),
            soup.find("div", class_="woocommerce-error"),
            soup.find(string=lambda text: text and "incorrect" in text.lower()),
            soup.find(string=lambda text: text and "invalid" in text.lower() and "username" in text.lower()),
        ]
        if any(error_indicators):
            return False

        # Check for logout link (primary indicator of logged-in state)
        logout_link = soup.find("a", string=lambda text: text and "logout" in text.lower())
        if logout_link:
            return True

        # Alternative check: look for logout in href attributes
        logout_href = soup.find("a", href=lambda href: href and "logout" in href.lower())
        if logout_href:
            return True

        # Check if login form is still present (indicates NOT logged in)
        login_form = soup.find("input", {"name": "woocommerce-login-nonce"})
        if login_form:
            return False

        # Fallback: check for "logout" text anywhere in the page
        # This is less reliable but kept for backward compatibility
        return "logout" in html.lower()

    async def _fetch_dashboard(self) -> BeautifulSoup:
        session = await self._get_session()
        async with session.get(DASHBOARD_URL, timeout=15) as resp:
            text = await resp.text()

        if not self._is_logged_in(text):
            _LOGGER.info("Session expired — reauthenticating...")
            await self.login()
            async with session.get(DASHBOARD_URL, timeout=15) as resp:
                text = await resp.text()
                if not self._is_logged_in(text):
                    raise ValueError("Could not reestablish session after re-login")

        return BeautifulSoup(text, "html.parser")

    async def get_sim_cards(self) -> Dict[str, Any]:
        """Fetch SIM cards and account-level credit."""
        soup = await self._fetch_dashboard()

        result: Dict[str, Any] = {
            "account_credit": None,
            "sims": []
        }

        # --- Account-level credit ---
        account_block = soup.find("div", class_="sideTable_side")
        if account_block:
            title = account_block.find("div", class_="sideTable_title")
            if title and "available credit for account" in title.text.lower():
                credit_el = account_block.find("div", class_="sideTable_text")
                if credit_el:
                    text = credit_el.get_text(strip=True)
                    credit_val = (
                        text.replace("€", "")
                        .replace("EUR", "")
                        .strip()
                        .replace(",", ".")
                    )
                    result["account_credit"] = credit_val
                    _LOGGER.debug("Account credit found: %s EUR", credit_val)

        # --- SIM cards ---
        rows = soup.find_all("tr")
        for row in rows:
            sim_container = row.find("div", class_="js-label-container")
            if not sim_container:
                continue

            sim_number = sim_container.get("data-number", "").strip()
            label_el = sim_container.find("span", class_="js-sim-label-value")
            sim_name = label_el.get_text(strip=True) if label_el else "Unnamed"

            sim_credit = None
            for td in row.find_all("td"):
                text = td.get_text(strip=True)
                if text.startswith("€"):
                    sim_credit = text.replace("€", "").replace(",", ".").strip()
                    break

            result["sims"].append({
                "number": sim_number,
                "name": sim_name,
                "credit": sim_credit or "0.00",
            })

        _LOGGER.debug(
            "Parsed account credit: %s, %d SIM cards",
            result["account_credit"],
            len(result["sims"]),
        )
        return result
