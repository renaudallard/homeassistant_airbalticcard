"""HTTP client for the AirBalticCard customer portal."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
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

    Accepts the currency on either side and in either decimal convention, so
    "EUR 1 234,56" and "€1,250.00" both come out right. The separator that
    appears last is the decimal one.
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


async def _run_inline(func: Any, *args: Any) -> Any:
    """Run a blocking callable directly, for callers with no thread pool."""
    return func(*args)


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

    Parsing an account page costs hundreds of milliseconds, so *run* is the
    hook a caller uses to push that work off its own thread. It defaults to
    running inline, which suits tests and scripts.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        run: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        """Store the credentials, the session and the blocking-work hook."""
        self._username = username
        self._password = password
        self._session = session
        self._run = run or _run_inline

    async def login(self, soup: BeautifulSoup | None = None) -> BeautifulSoup:
        """Log in and return the parsed response page.

        When *soup* already carries a login form its nonce is reused, which
        saves a round trip on re-authentication.
        """
        nonce = self._extract_nonce(soup) if soup is not None else None

        if not nonce:
            page, _ = await self._read(await self._get_account_text())
            nonce = self._extract_nonce(page)
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
        except RuntimeError as err:
            raise self._closed_session_error(err) from err

        page, logged_in = await self._read(text)
        if logged_in:
            _LOGGER.debug("Logged in to AirBalticCard")
            return page

        # WooCommerce re-renders the login form when it refuses the
        # credentials. A page without it failed for some other reason, such as
        # maintenance or a stray notice, and is worth retrying rather than
        # asking the user for a password that is probably fine.
        if page.find("input", {"name": _NONCE_FIELD}):
            raise AirBalticCardAuthError("Invalid username or password")

        raise AirBalticCardConnectionError("Login did not establish a session")

    async def get_sim_cards(self) -> dict[str, Any]:
        """Return the account credit and every SIM card on the account."""
        page = await self._fetch_dashboard()
        return await self._run(self._extract, page)

    async def _fetch_dashboard(self) -> BeautifulSoup:
        """Return the account page, logging in again if the session expired."""
        page, logged_in = await self._read(await self._get_account_text())
        if logged_in:
            return page

        _LOGGER.debug("Session expired, logging in again")
        return await self.login(soup=page)

    def _closed_session_error(self, err: RuntimeError) -> BaseException:
        """Turn "Session is closed" into our own error, and nothing else.

        aiohttp raises a bare RuntimeError once the session has been detached,
        which Home Assistant does as the entry unloads. A request already in
        flight would otherwise escape this module's error hierarchy.
        """
        if not self._session.closed:
            return err
        return AirBalticCardConnectionError("The session was closed mid-request")

    async def _read(self, text: str) -> tuple[BeautifulSoup, bool]:
        """Parse a page and say whether it shows a session, off this thread."""
        return await self._run(self._parse_and_check, text)

    @staticmethod
    def _parse_and_check(text: str) -> tuple[BeautifulSoup, bool]:
        """Parse *text* and check it for a session. Blocking; runs via _run."""
        page = BeautifulSoup(text, "html.parser")
        return page, AirBalticCardAPI._is_logged_in(page)

    @staticmethod
    def _extract(page: BeautifulSoup) -> dict[str, Any]:
        """Pull the account data out of a page. Blocking; runs via _run."""
        sims = AirBalticCardAPI._parse_sims(page)
        credit = AirBalticCardAPI._parse_account_credit(page)
        _LOGGER.debug("Parsed account credit %s and %d SIM card(s)", credit, len(sims))
        return {"account_credit": credit, "sims": sims}

    async def _get_account_text(self) -> str:
        """GET the account page and return its body."""
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
        except RuntimeError as err:
            raise self._closed_session_error(err) from err

        return text

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
            # Same gate as the SIM balances: anything but an amount and a
            # currency marker would otherwise yield the first digit run on the
            # line, which reads as a real figure.
            credit = parse_amount(text) if _CREDIT_RE.match(text) else None
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
