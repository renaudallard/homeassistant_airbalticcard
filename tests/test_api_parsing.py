"""Tests for the page parsing done by the AirBalticCard client."""

import pytest
from airbalticcard_api import AirBalticCardAPI, parse_amount
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
    """A WooCommerce error banner means the login was rejected."""
    page = soup('<ul class="woocommerce-error"><li>Wrong password</li></ul>')
    assert AirBalticCardAPI._is_logged_in(page) is False


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


def test_account_credit_is_none_when_absent():
    """No matching block means no account credit."""
    page = soup('<div class="sideTable_side"></div>')
    assert AirBalticCardAPI._parse_account_credit(page) is None
