"""Tests for the switch platform against the fake dSS."""
from .conftest import wait_for


async def test_switch_follows_websocket_events(hass, dss, setup_entry):
    await setup_entry()
    sleeping = "switch.sleeping"
    present = "switch.present"
    assert hass.states.get(sleeping).state == "off"  # default
    assert hass.states.get(present).state == "on"  # default
    await wait_for(lambda: len(dss._sockets) == 1)

    await dss.push_scene(zone_id=0, group_id=0, scene_id=69)  # sleeping
    await wait_for(lambda: hass.states.get(sleeping).state == "on")

    await dss.push_scene(zone_id=0, group_id=0, scene_id=70)  # wakeup
    await wait_for(lambda: hass.states.get(sleeping).state == "off")


async def test_switch_commands_call_scenes(hass, dss, setup_entry):
    await setup_entry()

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.sleeping"}, blocking=True)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.sleeping"}, blocking=True)

    await wait_for(lambda: len(dss.scene_calls) == 2)
    assert dss.scene_calls == ["69", "70"]
    assert hass.states.get("switch.sleeping").state == "off"
