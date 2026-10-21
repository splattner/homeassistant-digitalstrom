"""Tests for the events fired when scenes are called on the server."""
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.digitalstrom.const import EVENT_SCENE_CALLED

from .conftest import wait_for


async def test_scene_call_fires_event_with_names(hass, dss, setup_entry):
    entry = await setup_entry()
    events = async_capture_events(hass, EVENT_SCENE_CALLED)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_event(
        {
            "name": "callScene",
            "properties": {
                "zoneID": "0",
                "groupID": "1",
                "sceneID": "5",
                "originDSUID": "abc",
            },
        }
    )
    await wait_for(lambda: len(events) == 1)

    assert events[0].data == {
        "entry_id": entry.entry_id,
        "zone_id": 0,
        "zone_name": "Apartment",
        "group_id": 1,
        "scene_id": 5,
        "scene_name": "Preset1",
        "properties": {
            "zoneID": "0",
            "groupID": "1",
            "sceneID": "5",
            "originDSUID": "abc",
        },
    }


async def test_standard_scenes_without_entity_have_a_name(hass, dss, setup_entry):
    """the door bell is not exposed as scene entity, but is a great trigger"""
    await setup_entry()
    events = async_capture_events(hass, EVENT_SCENE_CALLED)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=0, group_id=0, scene_id=73)
    await dss.push_scene(zone_id=0, group_id=0, scene_id=200)  # unknown
    await wait_for(lambda: len(events) == 2)

    assert [e.data["scene_name"] for e in events] == ["Door Bell", None]


async def test_custom_named_scene_uses_the_server_name(hass, dss, setup_entry):
    await setup_entry()
    events = async_capture_events(hass, EVENT_SCENE_CALLED)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=0, group_id=1, scene_id=40)
    await wait_for(lambda: len(events) == 1)

    assert events[0].data["scene_name"] == "Movie Night"


async def test_unknown_zone_has_no_name(hass, dss, setup_entry):
    await setup_entry()
    events = async_capture_events(hass, EVENT_SCENE_CALLED)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=77, group_id=1, scene_id=5)
    await wait_for(lambda: len(events) == 1)

    assert events[0].data["zone_name"] is None


async def test_incomplete_events_are_ignored(hass, dss, setup_entry):
    await setup_entry()
    events = async_capture_events(hass, EVENT_SCENE_CALLED)
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_event({"name": "callScene"})
    await dss.push_event({"name": "callScene", "properties": {"zoneID": "0"}})
    await dss.push_event({"name": "callScene", "properties": {"zoneID": "x", "groupID": "1", "sceneID": "5"}})
    # a valid one afterwards proves the listener is still alive
    await dss.push_scene(zone_id=0, group_id=1, scene_id=5)
    await wait_for(lambda: len(events) == 1)

    assert events[0].data["scene_id"] == 5


async def test_no_events_after_unload(hass, dss, setup_entry):
    entry = await setup_entry()
    listener = entry.runtime_data.listener
    events = async_capture_events(hass, EVENT_SCENE_CALLED)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await listener._handle_event({"name": "callScene", "properties": {"zoneID": "0", "groupID": "1", "sceneID": "5"}})

    assert events == []
