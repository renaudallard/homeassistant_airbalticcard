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
# A balance cell is an amount and a currency marker and nothing else, so a
# tariff such as "€0.09/min" or a label such as "Europe 5 countries" is
# not mistaken for one.
_CREDIT_RE = re.compile(
    r"^(?:€|EUR)\s*-?[\d\s\u00a0\u202f.,]+$"
    r"|^-?[\d\s\u00a0\u202f.,]+\s*(?:€|EUR)$",
    re.IGNORECASE,
)


class AirBalticCardError(Exception):
    """Base error raised by the client."""


class AirBalticCardConnectionError(AirBalticCardError):
    """The portal could not be reached or returned an unusable page."""


class AirBalticCardAuthError(AirBalticCardError):
    """The portal rejected the credentials."""


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


def _describe(err: BaseException) -> str:
    """Return a readable description, since a timeout carries no message."""
    return str(err) or type(err).__name__


def _attr(tag: Any, name: str) -> str:
    """Return a tag attribute as a plain stripped string."""
    value = tag.get(name, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


class AirBalticCardAPI:
    """Async client for the AirBalticCard customer portal.

    The caller owns *session*: its cookie jar holds the portal login, so each
    account needs a session of its own.
    """

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        """Store the credentials and the session used for every request."""
        self._username = username
        self._password = password
        self._session = session

    async def login(self, soup: BeautifulSoup | None = None) -> BeautifulSoup:
        """Log in and return the parsed response page.

        When *soup* already carries a login form its nonce is reused, which
        saves a round trip on re-authentication.
        """
        nonce = self._extract_nonce(soup) if soup is not None else None

        if not nonce:
            nonce = self._extract_nonce(await self._fetch_account_page())
            if not nonce:
                raise AirBalticCardConnectionError(
                    "Could not retrieve the login nonce from the account page"
                )

        payload = {
            "username": self._username,
            "password": self._password,
            _NONCE_FIELD: nonce,
            "login": "Log in",
        }

        try:
            async with self._session.post(
                ACCOUNT_URL, data=payload, allow_redirects=True, timeout=_TIMEOUT
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AirBalticCardConnectionError(
                f"Login request failed: {_describe(err)}"
            ) from err

        page = BeautifulSoup(text, "html.parser")
        if not self._is_logged_in(page):
            raise AirBalticCardAuthError("Invalid username or password")

        _LOGGER.debug("Logged in to AirBalticCard")
        return page

    async def get_sim_cards(self) -> dict[str, Any]:
        """Return the account credit and every SIM card on the account."""
        page = await self._fetch_dashboard()
        sims = self._parse_sims(page)
        credit = self._parse_account_credit(page)

        _LOGGER.debug("Parsed account credit %s and %d SIM card(s)", credit, len(sims))
        return {"account_credit": credit, "sims": sims}

    async def _fetch_dashboard(self) -> BeautifulSoup:
        """Return the account page, logging in again if the session expired."""
        page = await self._fetch_account_page()
        if self._is_logged_in(page):
            return page

        _LOGGER.debug("Session expired, logging in again")
        return await self.login(soup=page)

    async def _fetch_account_page(self) -> BeautifulSoup:
        """GET the account page and return it parsed."""
        try:
            async with self._session.get(ACCOUNT_URL, timeout=_TIMEOUT) as resp:
                if resp.status != HTTPStatus.OK:
                    raise AirBalticCardConnectionError(
                        f"Account page unavailable (HTTP {resp.status})"
                    )
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AirBalticCardConnectionError(
                f"Request failed: {_describe(err)}"
            ) from err

        return BeautifulSoup(text, "html.parser")

    @staticmethod
    def _extract_nonce(soup: BeautifulSoup) -> str | None:
        """Return the WooCommerce login nonce carried by a parsed page."""
        field = soup.find("input", {"name": _NONCE_FIELD})
        if not field:
            return None
        return _attr(field, "value") or None

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
                if not _CREDIT_RE.match(text):
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
