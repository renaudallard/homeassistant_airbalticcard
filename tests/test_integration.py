"""End-to-end tests against a real Home Assistant.

These need pytest-homeassistant-custom-component; tests/test_api_parsing.py
deliberately does not, so the parsing can be checked without it.
"""

import pytest

# Everything below needs a real Home Assistant. Skip the whole module when the
# harness is not installed, so tests/test_api_parsing.py still runs on its own.
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbalticcard import async_remove_config_entry_device

DOMAIN = "airbalticcard"
GET_SIM_CARDS = (
    "custom_components.airbalticcard.airbalticcard_api.AirBalticCardAPI.get_sim_cards"
)


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    """Let Home Assistant load this integration from custom_components."""
    return


def payload(*numbers):
    """Build coordinator data listing *numbers* as the account's SIMs."""
    return {
        "account_credit": 10.0,
        "sims": [{"number": n, "name": f"SIM {n}", "credit": 2.5} for n in numbers],
    }


async def add_entry(hass, monkeypatch, data, **kwargs):
    """Set up a config entry whose polling returns *data*."""

    async def fake(self):
        return data["v"]

    monkeypatch.setattr(GET_SIM_CARDS, fake)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": kwargs.pop("username", "user@example.com"), "password": "p"},
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


async def test_entry_from_1_2_x_is_migrated(hass, monkeypatch):
    """Registry identifiers and the unique ID move to the account-scoped form."""
    entry = await add_entry(
        hass,
        monkeypatch,
        {"v": payload("111")},
        version=1,
        unique_id="  User@Example.COM ",
        username="  User@Example.COM ",
    )

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    account = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "airbalticcard_account")},
        name="AirBalticCard Account",
    )
    sim = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "111")},
        name="SIM 111",
    )
    for domain, unique_id, device in (
        ("sensor", "airbalticcard_account_credit", account),
        ("sensor", "airbalticcard_111_balance", sim),
        ("button", "airbalticcard_refresh", account),
    ):
        entity_registry.async_get_or_create(
            domain, DOMAIN, unique_id, config_entry=entry, device_id=device.id
        )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entry_id = entry.entry_id
    assert entry.version == 2
    assert entry.unique_id == "user@example.com"

    identifiers = {
        identifier
        for device in dr.async_entries_for_config_entry(device_registry, entry_id)
        for identifier in device.identifiers
    }
    assert (DOMAIN, f"{entry_id}_account") in identifiers
    assert (DOMAIN, f"{entry_id}_111") in identifiers
    assert (DOMAIN, "airbalticcard_account") not in identifiers
    assert (DOMAIN, "111") not in identifiers

    unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry_id)
    }
    assert f"{DOMAIN}_{entry_id}_account_credit" in unique_ids
    assert f"{DOMAIN}_{entry_id}_111_balance" in unique_ids
    assert f"{DOMAIN}_{entry_id}_refresh" in unique_ids

    assert (
        device_registry.async_get_device({(DOMAIN, f"{entry_id}_111")}).via_device_id
        == device_registry.async_get_device({(DOMAIN, f"{entry_id}_account")}).id
    )


async def test_sim_returns_after_its_device_was_deleted(hass, monkeypatch):
    """A deleted stale SIM device must not blacklist the number."""
    data = {"v": payload("111")}
    entry = await add_entry(hass, monkeypatch, data, version=2, unique_id="u")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    coordinator = entry.runtime_data.coordinator

    def sim_entities():
        return sorted(
            entity.entity_id
            for entity in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if "111" in entity.entity_id
        )

    before = sim_entities()
    assert before

    # the SIM leaves the account; the entry stays loaded throughout
    data["v"] = payload()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_111")})
    assert await async_remove_config_entry_device(hass, entry, device)
    device_registry.async_update_device(
        device.id, remove_config_entry_id=entry.entry_id
    )
    await hass.async_block_till_done()
    assert sim_entities() == []

    # and comes back
    data["v"] = payload("111")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert sim_entities() == before


async def test_the_sensors_come_back_after_a_reload(hass, monkeypatch):
    """A restart finds the entities in the registry; they must still be built.

    Skipping the SIMs already on record left Home Assistant restoring registry
    entries with no entity behind them, so every SIM sensor read unavailable
    from the second start onwards.
    """
    entry = await add_entry(
        hass, monkeypatch, {"v": payload("111", "222")}, version=2, unique_id="u"
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = [
        entry_.entity_id
        for entry_ in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    ]
    assert entities

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert [
        entity_id
        for entity_id in entities
        if hass.states.get(entity_id).state == "unavailable"
    ] == []


async def test_disabling_one_sensor_does_not_re_add_the_other(
    hass, monkeypatch, caplog
):
    """Disabling removes the entity but keeps its registry entry.

    The SIM must stay on record, or the next poll builds a second copy of the
    sensor left enabled and Home Assistant rejects it as a duplicate.
    """
    entry = await add_entry(
        hass, monkeypatch, {"v": payload("111")}, version=2, unique_id="u"
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        "sensor.sim_111_description", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "does not generate unique IDs" not in caplog.text
    assert hass.states.get("sensor.sim_111_balance").state == "2.5"


async def test_a_live_sim_device_cannot_be_deleted(hass, monkeypatch):
    """The account device and SIMs still on the account are protected."""
    entry = await add_entry(
        hass, monkeypatch, {"v": payload("111")}, version=2, unique_id="u"
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    for suffix in ("111", "account"):
        device = device_registry.async_get_device(
            {(DOMAIN, f"{entry.entry_id}_{suffix}")}
        )
        assert not await async_remove_config_entry_device(hass, entry, device)


async def test_device_removal_is_allowed_while_the_entry_is_unloaded(hass, monkeypatch):
    """Home Assistant offers Delete even then, and must not get an error."""
    entry = await add_entry(
        hass, monkeypatch, {"v": payload("111")}, version=2, unique_id="u"
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_111")})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hasattr(entry, "runtime_data")

    assert await async_remove_config_entry_device(hass, entry, device)
