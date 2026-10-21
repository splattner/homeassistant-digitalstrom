"""Fire home assistant events for scenes called on the digitalSTROM server."""
import logging

from homeassistant.core import HomeAssistant

from .const import EVENT_SCENE_CALLED
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.client import DSClient

_LOGGER = logging.getLogger(__name__)


def scene_name(client: DSClient, zone_id: int, group_id: int, scene_id: int):
    """
    name of a scene: a name chosen on the server, otherwise the readable name
    of the standard scene (e.g. "Door Bell"), None for unknown scenes
    """
    scenes = client.get_scenes()
    scene = scenes.get(f"{zone_id}_{group_id}_{scene_id}") or scenes.get(
        f"{zone_id}_{scene_id}"
    )

    constant = dsconst.ALL_SCENES_BYID.get(scene_id)
    standard_name = constant.replace("SCENE_", "").title() if constant else None

    # scenes are named after the standard scene unless the user renamed them
    if scene and scene.scene_name != standard_name:
        return scene.scene_name
    return standard_name.replace("_", " ") if standard_name else None


def async_create_scene_event_callback(hass: HomeAssistant, entry_id: str, client: DSClient):
    """
    create a websocket callback that fires EVENT_SCENE_CALLED

    The event also fires for scenes called by Home Assistant itself, as the
    server reports every call. origin_device_id is the dSID of the device (for
    example the button) that caused the call, if the server tells. All
    properties of the original event are kept in "properties".
    """

    async def event_callback(event: dict) -> None:
        properties = event.get("properties")
        try:
            zone_id = int(properties["zoneID"])
            group_id = int(properties["groupID"])
            scene_id = int(properties["sceneID"])
        except (KeyError, TypeError, ValueError):
            _LOGGER.debug("ignoring callScene event without zone, group and scene: %s", event)
            return

        hass.bus.async_fire(
            EVENT_SCENE_CALLED,
            {
                "entry_id": entry_id,
                "zone_id": zone_id,
                "zone_name": client.get_zone_name(zone_id),
                "group_id": group_id,
                "scene_id": scene_id,
                "scene_name": scene_name(client, zone_id, group_id, scene_id),
                "origin_device_id": properties.get("originDeviceID"),
                "properties": properties,
            },
        )

    return event_callback
