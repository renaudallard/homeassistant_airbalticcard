"""HTTP client for the AirBalticCard customer portal."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

ACCOUNT_URL = "https://airbalticcard.com/my-account/"
_TIMEOUT = aiohttp.ClientTimeout(total=15)

# A leading digit followed by digits, group separators and a decimal separator.
_AMOUNT_RE = re.compile(r"-?\d[\d\s\u00a0\u202f.,]*")
_SPACE_RE = re.compile(r"[\s\u00a0\u202f]")


def parse_amount(text: str) -> float | None:
    """Return the amount contained in *text*, or None when there is none.

    Accepts the symbol on either side and in either decimal convention, so
    "EUR 1 234,56" and "$1,234.56"-style groupings both come out right. The
    separator that appears last is the decimal one.
    """
    match = _AMOUNT_RE.search(text)
    if not match:
        return None

    raw = _SPACE_RE.sub("", match.group())
    if raw.rfind(",") > raw.rfind("."):
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "")

    try:
        return float(raw)
    except ValueError:
        return None


def _attr(tag: Any, name: str) -> str:
    """Return a tag attribute as a plain stripped string."""
    value = tag.get(name, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


class AirBalticCardAPI:
    """Async API client for AirBalticCard.

    The caller owns *session*: its cookie jar holds the portal login, so each
    account needs a session of its own.
    """

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        self._username = username
        self._password = password
        self._session = session

    @staticmethod
    def _extract_nonce_from_soup(soup: BeautifulSoup) -> str | None:
        """Extract the WooCommerce login nonce from a parsed page."""
        field = soup.find("input", {"name": "woocommerce-login-nonce"})
        if not field:
            return None
        return _attr(field, "value") or None

    async def login(self, soup: BeautifulSoup | None = None) -> BeautifulSoup:
        """Perform login and return the parsed response page.

        If *soup* is provided, the nonce is extracted from it directly
        instead of making an extra GET request.
        """
        nonce = self._extract_nonce_from_soup(soup) if soup else None

        if not nonce:
            async with self._session.get(ACCOUNT_URL, timeout=_TIMEOUT) as resp:
                if resp.status != 200:
                    raise ConnectionError(
                        f"Login page unavailable (HTTP {resp.status})"
                    )
                text = await resp.text()
            soup = BeautifulSoup(text, "html.parser")
            nonce = self._extract_nonce_from_soup(soup)
            if not nonce:
                raise ConnectionError("Could not retrieve login nonce from page")

        payload = {
            "username": self._username,
            "password": self._password,
            "woocommerce-login-nonce": nonce,
            "login": "Log in",
        }

        async with self._session.post(
            ACCOUNT_URL,
            data=payload,
            allow_redirects=True,
            timeout=_TIMEOUT,
        ) as resp:
            text = await resp.text()

        result_soup = BeautifulSoup(text, "html.parser")
        if not self._is_logged_in(result_soup, text):
            raise ValueError("Invalid username or password")

        _LOGGER.info("Login successful for %s", self._username)
        return result_soup

    @staticmethod
    def _is_logged_in(soup: BeautifulSoup, html: str) -> bool:
        """Check if user is logged in based on page content.

        Uses multiple indicators for robust authentication verification:
        - Presence of logout link
        - Absence of login form
        - Presence of WooCommerce error messages indicating failed login
        """
        # Check for WooCommerce error containers (indicates login failure)
        wc_error = soup.find("ul", class_="woocommerce-error") or soup.find(
            "div", class_="woocommerce-error"
        )
        if wc_error:
            return False

        # Check for logout link (primary indicator of logged-in state)
        for link in soup.find_all("a"):
            link_text = link.get_text(strip=True)
            if link_text and "logout" in link_text.lower():
                return True
            href = link.get("href", "")
            if isinstance(href, list):
                href = href[0] if href else ""
            if href and "logout" in href.lower():
                return True

        # Check if login form is still present (indicates NOT logged in)
        login_form = soup.find("input", {"name": "woocommerce-login-nonce"})
        if login_form:
            return False

        # Fallback: check for "logout" text anywhere in the page
        return "logout" in html.lower()

    async def _fetch_dashboard(self) -> BeautifulSoup:
        async with self._session.get(ACCOUNT_URL, timeout=_TIMEOUT) as resp:
            text = await resp.text()

        soup = BeautifulSoup(text, "html.parser")

        if not self._is_logged_in(soup, text):
            _LOGGER.info("Session expired — reauthenticating...")
            # Pass the soup we already parsed so login() can extract
            # the nonce without an extra GET or parse.  login() returns
            # the parsed response page directly.
            soup = await self.login(soup=soup)
            if not self._is_logged_in(soup, str(soup)):
                raise ValueError("Could not reestablish session after re-login")

        return soup

    async def get_sim_cards(self) -> dict[str, Any]:
        """Fetch SIM cards and account-level credit."""
        soup = await self._fetch_dashboard()
        sims = self._parse_sims(soup)
        credit = self._parse_account_credit(soup)

        _LOGGER.debug("Parsed account credit %s and %d SIM card(s)", credit, len(sims))
        return {"account_credit": credit, "sims": sims}

    @staticmethod
    def _parse_account_credit(soup: BeautifulSoup) -> float | None:
        """Return the account-level credit shown in the sidebar."""
        for block in soup.find_all("div", class_="sideTable_side"):
            title = block.find("div", class_="sideTable_title")
            if not title:
                continue
            if "available credit for account" not in title.get_text().lower():
                continue

            value = block.find("div", class_="sideTable_text")
            if not value:
                return None

            text = value.get_text(strip=True)
            credit = parse_amount(text)
            if credit is None:
                _LOGGER.warning("Could not read the account credit from %r", text)
            return credit

        return None

    @staticmethod
    def _parse_sims(soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Return one entry per SIM card listed on the account page."""
        sims: list[dict[str, Any]] = []

        for row in soup.find_all("tr"):
            container = row.find("div", class_="js-label-container")
            if not container:
                continue

            number = _attr(container, "data-number")
            if not number:
                continue

            label = container.find("span", class_="js-sim-label-value")

            credit = None
            for cell in row.find_all("td"):
                text = cell.get_text(strip=True)
                if "€" not in text and "eur" not in text.lower():
                    continue
                credit = parse_amount(text)
                if credit is not None:
                    break

            if credit is None:
                _LOGGER.warning("No readable balance for SIM %s", number)

            sims.append(
                {
                    "number": number,
                    "name": label.get_text(strip=True) if label else None,
                    "credit": credit,
                }
            )

        return sims
