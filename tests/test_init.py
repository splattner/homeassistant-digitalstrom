"""Tests for setting up, unloading and reloading the config entry."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState

from custom_components.digitalstrom.const import DOMAIN

from .conftest import wait_for


async def test_setup_creates_entities_and_starts_loops(hass, dss, setup_entry):
    dss.reachable_scenes = [0, 5]
    dss.meters = ["meter1"]

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids("light")) == 1
    assert len(hass.states.async_entity_ids("switch")) == 2  # sleeping, present
    assert hass.states.async_entity_ids("scene") == ["scene.movie_night"]
    assert len(hass.states.async_entity_ids("sensor")) == 2  # power, energy
    # hass is running, the loops must have been started right away
    await wait_for(lambda: len(dss._sockets) == 1)
    assert entry.runtime_data.client.stack._task is not None


async def test_loops_wait_for_the_start_event(hass, dss, setup_entry):
    hass.set_state(CoreState.not_running)

    entry = await setup_entry()

    assert dss.ws_connections == 0
    assert entry.runtime_data.client.stack._task is None

    hass.set_state(CoreState.starting)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await wait_for(lambda: len(dss._sockets) == 1)
    assert entry.runtime_data.client.stack._task is not None


async def test_unload_stops_everything(hass, dss, setup_entry):
    entry = await setup_entry()
    await wait_for(lambda: len(dss._sockets) == 1)
    data = entry.runtime_data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert data.client.stack._task is None
    assert data.listener._callbacks == []
    await wait_for(lambda: len(dss._sockets) == 0)
    for entity_id in hass.states.async_entity_ids("light"):
        assert hass.states.get(entity_id).state == "unavailable"


async def test_reload_reconnects(hass, dss, setup_entry):
    entry = await setup_entry()
    await wait_for(lambda: len(dss._sockets) == 1)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    await wait_for(lambda: dss.ws_connections == 2 and len(dss._sockets) == 1)


async def test_commands_are_sent_to_the_server(hass, dss, setup_entry):
    await setup_entry()

    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.movie_night"}, blocking=True
    )

    await wait_for(lambda: dss.scene_calls == ["40"])


async def test_missing_token_starts_reauth(hass, dss, setup_entry):
    entry = await setup_entry(token=None)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == "reauth"


async def test_rejected_token_starts_reauth(hass, dss, setup_entry):
    dss.reject_app_token = True

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == "reauth"


async def test_unreachable_server_is_retried(hass, dss, setup_entry):
    dss.http_status = 500

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_unique_id_is_added_to_old_entries(hass, dss, setup_entry):
    entry = await setup_entry()

    assert entry.unique_id == f"127_0_0_1_{dss.port}"
