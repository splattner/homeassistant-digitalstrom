"""Lights and switches start with the state the server reports."""
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import mock_restore_cache

from .conftest import wait_for

PRESETS = [0, 5, 17, 18, 19]


async def test_light_is_on_with_the_effect_that_was_called_last(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS
    dss.last_called = {(0, 1): 18}  # preset 3

    await setup_entry()

    state = hass.states.get("light.apartment")
    assert state.state == "on"
    assert state.attributes["effect"] == "PRESET3"


async def test_light_is_off_after_the_off_scene(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS
    dss.last_called = {(0, 1): 0}

    await setup_entry()

    assert hass.states.get("light.apartment").state == "off"


@pytest.mark.parametrize(
    "restored, last_scene, expected",
    [
        pytest.param("off", 5, "on", id="server on beats restored off"),
        pytest.param("on", 0, "off", id="server off beats restored on"),
    ],
)
async def test_server_state_wins_over_restored_state(
    hass, dss, setup_entry, restored, last_scene, expected
):
    dss.reachable_scenes = PRESETS
    dss.last_called = {(0, 1): last_scene}
    mock_restore_cache(hass, [State("light.apartment", restored)])

    await setup_entry()

    assert hass.states.get("light.apartment").state == expected


async def test_unrelated_last_scene_keeps_the_restored_state(hass, dss, setup_entry):
    """area 1 light, but area 2 was called last: nothing is known about area 1"""
    dss.reachable_scenes = [1, 6]
    dss.last_called = {(0, 1): 7}  # area 2 on
    mock_restore_cache(hass, [State("light.area1_off", "on")])

    await setup_entry()

    assert hass.states.get("light.area1_off").state == "on"


async def test_unknown_state_without_any_information(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS

    await setup_entry()

    assert hass.states.get("light.apartment").state == "unknown"


async def test_failing_request_does_not_break_setup(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS
    dss.fail_last_called = True
    mock_restore_cache(hass, [State("light.apartment", "on")])

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.apartment").state == "on"


async def test_one_request_per_zone_and_light_group(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS

    await setup_entry()

    assert sorted(dss.last_called_requests, key=str) == [(0, 1), (0, None)]


@pytest.mark.parametrize(
    "last_scene, restored, sleeping, present",
    [
        pytest.param(69, "off", "on", "on", id="sleeping called last"),
        pytest.param(70, "on", "off", "on", id="wake up called last"),
        pytest.param(72, None, "off", "off", id="absent called last"),
        pytest.param(71, None, "off", "on", id="present called last"),
        pytest.param(73, None, "off", "on", id="door bell says nothing, defaults stay"),
        pytest.param(None, None, "off", "on", id="no information, defaults stay"),
    ],
)
async def test_switches_use_the_last_called_scene_if_it_is_theirs(
    hass, dss, setup_entry, last_scene, restored, sleeping, present
):
    if last_scene is not None:
        dss.last_called = {(0, None): last_scene}
    if restored is not None:
        mock_restore_cache(hass, [State("switch.sleeping", restored)])

    await setup_entry()

    assert hass.states.get("switch.sleeping").state == sleeping
    assert hass.states.get("switch.present").state == present


async def test_live_events_still_update_the_state(hass, dss, setup_entry):
    dss.reachable_scenes = PRESETS
    dss.last_called = {(0, 1): 0}
    await setup_entry()
    assert hass.states.get("light.apartment").state == "off"
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=0, group_id=1, scene_id=19)

    await wait_for(lambda: hass.states.get("light.apartment").state == "on")
