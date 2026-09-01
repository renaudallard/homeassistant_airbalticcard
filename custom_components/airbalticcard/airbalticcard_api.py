"""HTTP client for the AirBalticCard customer portal."""

from __future__ import annotations

import logging
import re
from http import HTTPStatus
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

ACCOUNT_URL = "https://airbalticcard.com/my-account/"
_TIMEOUT = aiohttp.ClientTimeout(total=15)
_NONCE_FIELD = "woocommerce-login-nonce"

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
    def _extract_nonce(soup: BeautifulSoup) -> str | None:
        """Return the WooCommerce login nonce carried by a parsed page."""
        field = soup.find("input", {"name": _NONCE_FIELD})
        if not field:
            return None
        return _attr(field, "value") or None

    async def login(self, soup: BeautifulSoup | None = None) -> BeautifulSoup:
        """Perform login and return the parsed response page.

        If *soup* is provided, the nonce is extracted from it directly
        instead of making an extra GET request.
        """
        nonce = self._extract_nonce(soup) if soup else None

        if not nonce:
            nonce = self._extract_nonce(await self._fetch_account_page())
            if not nonce:
                raise ConnectionError("Could not retrieve login nonce from page")

        payload = {
            "username": self._username,
            "password": self._password,
            _NONCE_FIELD: nonce,
            "login": "Log in",
        }

        async with self._session.post(
            ACCOUNT_URL,
            data=payload,
            allow_redirects=True,
            timeout=_TIMEOUT,
        ) as resp:
            text = await resp.text()

        page = BeautifulSoup(text, "html.parser")
        if not self._is_logged_in(page):
            raise ValueError("Invalid username or password")

        _LOGGER.debug("Logged in to AirBalticCard")
        return page

    @staticmethod
    def _is_logged_in(soup: BeautifulSoup) -> bool:
        """Tell whether *soup* is an authenticated account page.

        The negative signals are checked first: an error banner or a login form
        means we are logged out whatever else the page happens to contain, and
        a site menu can carry a logout link on both sides of the login.
        """
        if soup.find(class_="woocommerce-error"):
            return False
        if soup.find("input", {"name": _NONCE_FIELD}):
            return False

        for link in soup.find_all("a"):
            if "logout" in link.get_text(strip=True).lower():
                return True
            if "logout" in _attr(link, "href").lower():
                return True

        # Some layouts hide the logout link inside a menu. Seeing the account
        # tables proves the session just as well.
        return bool(
            soup.find("div", class_="js-label-container")
            or soup.find("div", class_="sideTable_side")
        )

    async def _fetch_dashboard(self) -> BeautifulSoup:
        """Return the account page, logging in again if the session expired."""
        page = await self._fetch_account_page()
        if self._is_logged_in(page):
            return page

        _LOGGER.debug("Session expired, logging in again")
        # login() checks the page it returns and raises if the credentials no
        # longer work, so there is nothing left to verify here.
        return await self.login(soup=page)

    async def _fetch_account_page(self) -> BeautifulSoup:
        """GET the account page and return it parsed."""
        async with self._session.get(ACCOUNT_URL, timeout=_TIMEOUT) as resp:
            if resp.status != HTTPStatus.OK:
                raise ConnectionError(f"Account page unavailable (HTTP {resp.status})")
            text = await resp.text()

        return BeautifulSoup(text, "html.parser")

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
