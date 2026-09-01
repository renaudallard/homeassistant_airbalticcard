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
