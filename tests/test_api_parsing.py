"""Tests for the page parsing done by the AirBalticCard client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from airbalticcard_api import (
    AirBalticCardAPI,
    AirBalticCardAuthError,
    AirBalticCardConnectionError,
    parse_amount,
)
from bs4 import BeautifulSoup


def soup(html: str) -> BeautifulSoup:
    """Parse a fragment the way the client does."""
    return BeautifulSoup(html, "html.parser")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("€12,34", 12.34),
        ("12,34 €", 12.34),
        ("€ 12,34", 12.34),
        ("12.34 EUR", 12.34),
        ("EUR 12.34", 12.34),
        ("1 234,56 €", 1234.56),
        ("€1,250.00", 1250.0),
        ("1 250,00", 1250.0),
        ("0", 0.0),
        ("-3,50 €", -3.5),
        ("€", None),
        ("", None),
        ("no digits here", None),
    ],
)
def test_parse_amount(text, expected):
    """Amounts are read in either currency position and decimal convention."""
    assert parse_amount(text) == expected


def test_logged_out_page_with_a_logout_link_in_the_menu():
    """A login form outweighs a logout link left in the site menu."""
    page = soup(
        '<nav><a href="/my-account/?customer-logout=true">Log out</a></nav>'
        '<form><input name="woocommerce-login-nonce" value="abc"></form>'
    )
    assert AirBalticCardAPI._is_logged_in(page) is False


def test_error_banner_means_logged_out():
    """An error banner outweighs the account content on the same page."""
    page = soup(
        '<ul class="woocommerce-error"><li>Wrong password</li></ul>'
        '<a href="/my-account/?customer-logout=true">Log out</a>'
        '<div class="sideTable_side"></div>'
    )
    assert AirBalticCardAPI._is_logged_in(page) is False


def test_logout_link_text_alone_proves_the_session():
    """The anchor text is checked, not just the href."""
    page = soup('<a href="/account/exit">Logout</a>')
    assert AirBalticCardAPI._is_logged_in(page) is True


def test_logout_mention_in_a_script_is_not_a_session():
    """Text in a script tag is not evidence of a session."""
    page = soup("<script>var url = '/wp/logout';</script><p>Session ended.</p>")
    assert AirBalticCardAPI._is_logged_in(page) is False


def test_logout_link_means_logged_in():
    """A real logout link is accepted."""
    page = soup('<a href="/my-account/?customer-logout=true">Log out</a>')
    assert AirBalticCardAPI._is_logged_in(page) is True


def test_account_tables_mean_logged_in():
    """Account content is accepted when the logout link sits behind a menu."""
    page = soup('<div class="sideTable_side"></div>')
    assert AirBalticCardAPI._is_logged_in(page) is True


def test_nonce_extraction():
    """The login nonce is read out of the form."""
    page = soup('<input name="woocommerce-login-nonce" value="9f8e7d">')
    assert AirBalticCardAPI._extract_nonce(page) == "9f8e7d"
    assert AirBalticCardAPI._extract_nonce(soup("<p>nothing</p>")) is None


SIM_ROW = (
    "<table><tr>"
    '<td><div class="js-label-container" data-number="37120000000">'
    '<span class="js-sim-label-value">Travel</span></div></td>'
    "<td>{credit}</td>"
    "</tr></table>"
)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("€12,34", 12.34),
        ("12,34 €", 12.34),
        ("12.34 EUR", 12.34),
        ("1 234,56 €", 1234.56),
    ],
)
def test_sim_credit_is_read_in_any_currency_position(cell, expected):
    """A balance is read wherever the currency marker sits."""
    sims = AirBalticCardAPI._parse_sims(soup(SIM_ROW.format(credit=cell)))
    assert sims == [{"number": "37120000000", "name": "Travel", "credit": expected}]


def test_unreadable_sim_credit_is_none_not_zero():
    """An unreadable balance stays unknown instead of becoming a fake zero."""
    sims = AirBalticCardAPI._parse_sims(soup(SIM_ROW.format(credit="n/a")))
    assert sims[0]["credit"] is None


def test_sim_without_a_number_is_skipped():
    """Rows with no SIM number carry nothing worth reporting."""
    page = soup(
        "<table><tr>"
        '<td><div class="js-label-container" data-number=""></div></td>'
        "<td>€1,00</td></tr></table>"
    )
    assert AirBalticCardAPI._parse_sims(page) == []


def test_account_credit_is_found_in_the_matching_block():
    """The sidebar is searched for the account credit block."""
    page = soup(
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Something else</div>'
        '<div class="sideTable_text">€ 1,00</div></div>'
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Available credit for account</div>'
        '<div class="sideTable_text">€ 125,00</div></div>'
    )
    assert AirBalticCardAPI._parse_account_credit(page) == 125.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\u20ac70.00 EUR", 70.0),
        ("\u20ac 1 234,56 EUR", 1234.56),
        ("EUR 70.00 \u20ac", 70.0),
    ],
)
def test_account_credit_with_a_currency_on_both_sides(text, expected):
    """The portal prints the account credit as "\u20ac70.00 EUR"."""
    page = soup(
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Available credit for account</div>'
        f'<div class="sideTable_text">{text}</div></div>'
    )
    assert AirBalticCardAPI._parse_account_credit(page) == expected


@pytest.mark.parametrize(
    "text",
    [
        "as of 31.12.2026, \u20ac 125,00",
        "12 months left, \u20ac 125,00",
        "SIM-12345 credit 5,00 \u20ac",
        "no credit on file",
    ],
)
def test_account_credit_with_extra_text_is_unknown(text):
    """A block holding more than an amount must not yield a number."""
    page = soup(
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Available credit for account</div>'
        f'<div class="sideTable_text">{text}</div></div>'
    )
    assert AirBalticCardAPI._parse_account_credit(page) is None


def test_account_credit_is_none_when_absent():
    """No matching block means no account credit."""
    page = soup('<div class="sideTable_side"></div>')
    assert AirBalticCardAPI._parse_account_credit(page) is None


@pytest.mark.parametrize(
    "cell",
    [
        "Europe 5 countries",
        "€0.09/min",
        "0.09 EUR per minute",
        "Travel",
        "37120000000",
        "",
    ],
)
def test_cells_that_are_not_a_balance_are_skipped(cell):
    """Only a cell holding nothing but an amount counts as the balance."""
    sims = AirBalticCardAPI._parse_sims(soup(SIM_ROW.format(credit=cell)))
    assert sims[0]["credit"] is None


def test_the_balance_wins_over_an_earlier_tariff_cell():
    """A tariff column ahead of the balance is not picked up."""
    page = soup(
        "<table><tr>"
        '<td><div class="js-label-container" data-number="37120000000">'
        '<span class="js-sim-label-value">Travel</span></div></td>'
        "<td>Europe 5 countries</td><td>€0.09/min</td><td>12,34 €</td>"
        "</tr></table>"
    )
    assert AirBalticCardAPI._parse_sims(page)[0]["credit"] == 12.34


def api_returning(get_html, post_html=None, run=None):
    """Build a client answering GET with *get_html* and POST with *post_html*."""

    def responder(html):
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value=html)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=response)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return MagicMock(return_value=ctx)

    session = MagicMock()
    session.get = responder(get_html)
    session.post = responder(get_html if post_html is None else post_html)
    return AirBalticCardAPI("user", "secret", session, run)


LOGIN_FORM = '<input name="woocommerce-login-nonce" value="nonce">'


def test_refused_credentials_raise_an_auth_error():
    """The login form coming back means the password was refused."""
    client = api_returning(
        LOGIN_FORM + '<ul class="woocommerce-error"><li>no</li></ul>'
    )
    with pytest.raises(AirBalticCardAuthError):
        asyncio.run(client.login())


def test_a_login_that_fails_for_another_reason_is_a_connection_error():
    """A POST answer with no login form failed for some other reason.

    The GET must carry the form, or login() stops at the missing-nonce guard
    and never reaches the branch this guards.
    """
    client = api_returning(LOGIN_FORM, "<p>Down for maintenance</p>")
    with pytest.raises(AirBalticCardConnectionError):
        asyncio.run(client.login())


def test_a_refused_login_is_told_apart_from_an_unusable_page():
    """The two post-POST outcomes must not collapse into one."""
    refused = api_returning(LOGIN_FORM, LOGIN_FORM + "<p>Wrong password</p>")
    with pytest.raises(AirBalticCardAuthError):
        asyncio.run(refused.login())

    unusable = api_returning(LOGIN_FORM, "<p>502 Bad Gateway</p>")
    with pytest.raises(AirBalticCardConnectionError):
        asyncio.run(unusable.login())


def test_a_successful_login_returns_the_session_page():
    """A response carrying the account tables ends the login."""
    client = api_returning(
        LOGIN_FORM,
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Available credit for account</div>'
        '<div class="sideTable_text">125,00 EUR</div></div>',
    )
    page = asyncio.run(client.login())
    assert AirBalticCardAPI._parse_account_credit(page) == 125.0


def test_parsing_goes_through_the_supplied_runner():
    """The blocking parse is handed to the caller's hook, not run inline."""
    calls = []

    async def run(func, *fargs):
        calls.append(func.__name__)
        return func(*fargs)

    client = api_returning(
        '<a href="/my-account/?customer-logout=true">Log out</a>'
        '<div class="sideTable_side">'
        '<div class="sideTable_title">Available credit for account</div>'
        '<div class="sideTable_text">125,00 EUR</div></div>',
        run=run,
    )
    data = asyncio.run(client.get_sim_cards())

    assert data["account_credit"] == 125.0
    assert calls == ["_parse_and_check", "_extract"]


def test_a_closed_session_is_reported_as_a_connection_failure():
    """Home Assistant detaches the session on unload; a request in flight
    then hits a bare RuntimeError that must not escape this module."""

    async def attempt():
        session = aiohttp.ClientSession()
        session.detach()
        client = AirBalticCardAPI("user", "secret", session)
        with pytest.raises(AirBalticCardConnectionError):
            await client.get_sim_cards()

    asyncio.run(attempt())


def test_an_unrelated_runtime_error_is_not_swallowed():
    """Only a closed session is translated; other bugs still surface."""
    session = MagicMock()
    session.closed = False
    session.get = MagicMock(side_effect=RuntimeError("something else"))
    client = AirBalticCardAPI("user", "secret", session)
    with pytest.raises(RuntimeError, match="something else"):
        asyncio.run(client.get_sim_cards())
