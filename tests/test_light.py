"""Tests for the light platform against the fake dSS."""
import pytest

from .conftest import wait_for


async def light_entity_id(hass) -> str:
    [entity_id] = hass.states.async_entity_ids("light")
    return entity_id


@pytest.mark.parametrize(
    "reachable_scenes, expected_effects",
    [
        pytest.param([0, 5, 17, 18, 19], ["PRESET1", "PRESET2", "PRESET3", "PRESET4"], id="all presets"),
        pytest.param([0, 5, 18], ["PRESET1", "PRESET3"], id="only preset 3"),
        pytest.param([0, 5], ["PRESET1"], id="no extra presets"),
        pytest.param([1, 6], ["PRESET1"], id="area light"),
    ],
)
async def test_setup_only_exposes_existing_effects(
    hass, dss, setup_entry, reachable_scenes, expected_effects
):
    dss.reachable_scenes = reachable_scenes

    await setup_entry()

    state = hass.states.get(await light_entity_id(hass))
    assert state.attributes["effect_list"] == expected_effects


async def test_no_light_without_turn_on_scene(hass, dss, setup_entry):
    dss.reachable_scenes = [0]

    await setup_entry()

    assert hass.states.async_entity_ids("light") == []


async def test_turn_on_and_off_call_scenes(hass, dss, setup_entry):
    dss.reachable_scenes = [0, 5, 17, 18, 19]
    await setup_entry()
    entity_id = await light_entity_id(hass)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id, "effect": "PRESET3"}, blocking=True
    )
    state = hass.states.get(entity_id)
    assert state.state == "on" and state.attributes["effect"] == "PRESET3"

    await hass.services.async_call("light", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert hass.states.get(entity_id).attributes["effect"] == "PRESET1"

    await hass.services.async_call("light", "turn_off", {"entity_id": entity_id}, blocking=True)
    state = hass.states.get(entity_id)
    assert state.state == "off" and state.attributes["effect"] is None

    await wait_for(lambda: len(dss.scene_calls) == 3)
    assert dss.scene_calls == ["18", "5", "0"]


async def test_websocket_events_update_state(hass, dss, setup_entry):
    dss.reachable_scenes = [0, 5, 17, 18, 19]
    await setup_entry()
    entity_id = await light_entity_id(hass)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=0, group_id=1, scene_id=19)
    await wait_for(lambda: hass.states.get(entity_id).state == "on")
    assert hass.states.get(entity_id).attributes["effect"] == "PRESET4"

    # other zone is ignored
    await dss.push_scene(zone_id=2, group_id=1, scene_id=0)
    await dss.push_scene(zone_id=0, group_id=1, scene_id=0)
    await wait_for(lambda: hass.states.get(entity_id).state == "off")
    assert hass.states.get(entity_id).attributes["effect"] is None
