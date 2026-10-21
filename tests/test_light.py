"""Tests for the light platform, run with stubbed Home Assistant base classes."""
from unittest.mock import MagicMock

import pytest

from custom_components.digitalstrom import light
from custom_components.digitalstrom.pydigitalstrom.devices.scene import DSColorScene


class RecordingScene(DSColorScene):
    """scene that records calls instead of talking to a server"""

    calls = []

    async def turn_on(self):
        self.calls.append(self.scene_id)


@pytest.fixture(autouse=True)
def reset_calls():
    RecordingScene.calls = []


def make_scenes(scene_ids, zone_id=1, color=1):
    return {
        f"{zone_id}_{color}_{scene_id}": RecordingScene(
            client=None,
            zone_id=zone_id,
            zone_name="Living",
            scene_id=scene_id,
            scene_name=f"SCENE_{scene_id}",
            color=color,
        )
        for scene_id in scene_ids
    }


async def setup_lights(monkeypatch, scene_ids):
    monkeypatch.setattr(light, "slugify_entry", lambda host, port: "slug")
    client = MagicMock()
    client.get_scenes.return_value = make_scenes(scene_ids)
    hass = MagicMock()
    hass.data = {"digitalstrom": {"slug": {"client": client, "listener": MagicMock()}}}
    entry = MagicMock()
    entry.data = {"host": "dss.local", "port": 8080}

    added = []
    await light.async_setup_entry(hass, entry, lambda entities: added.extend(entities))
    return added


@pytest.mark.parametrize(
    "scene_ids, expected_effects",
    [
        pytest.param([0, 5, 17, 18, 19], ["PRESET1", "PRESET2", "PRESET3", "PRESET4"], id="all presets"),
        pytest.param([0, 5, 18], ["PRESET1", "PRESET3"], id="only preset 3"),
        pytest.param([0, 5], ["PRESET1"], id="no extra presets"),
        pytest.param([1, 6], ["PRESET1"], id="area light"),
    ],
)
async def test_setup_only_exposes_existing_effects(monkeypatch, scene_ids, expected_effects):
    lights = await setup_lights(monkeypatch, scene_ids)

    assert len(lights) == 1
    assert lights[0].effect_list == expected_effects


async def test_setup_skips_light_without_turn_on_scene(monkeypatch):
    assert await setup_lights(monkeypatch, [0]) == []


async def test_turn_on_and_off_call_scenes_and_write_state(monkeypatch):
    [entity] = await setup_lights(monkeypatch, [0, 5, 17, 18, 19])

    await entity.async_turn_on(effect="PRESET3")
    assert RecordingScene.calls == [18]
    assert entity.is_on and entity.effect == "PRESET3"

    await entity.async_turn_on()
    assert RecordingScene.calls == [18, 5]
    assert entity.effect == "PRESET1"

    await entity.async_turn_off()
    assert RecordingScene.calls == [18, 5, 0]
    assert entity.is_on is False and entity.effect is None
    assert entity.state_writes == 3


async def test_unknown_effect_falls_back_to_preset1(monkeypatch):
    [entity] = await setup_lights(monkeypatch, [0, 5])

    await entity.async_turn_on(effect="BOGUS")

    assert RecordingScene.calls == [5]
    assert entity.effect == "PRESET1"


async def test_websocket_events_update_state(monkeypatch):
    [entity] = await setup_lights(monkeypatch, [0, 5, 17, 18, 19])
    callback = entity._listener.register.call_args.kwargs["callback"]

    def event(scene_id, zone_id=1):
        return {
            "name": "callScene",
            "properties": {"zoneID": zone_id, "groupID": 1, "sceneID": scene_id},
        }

    await callback(event=event(19))
    assert entity.is_on and entity.effect == "PRESET4"
    assert entity.state_writes == 1

    await callback(event=event(0))
    assert entity.is_on is False and entity.effect is None
    assert entity.state_writes == 2

    # other zone is ignored
    await callback(event=event(5, zone_id=2))
    assert entity.is_on is False
    assert entity.state_writes == 2
