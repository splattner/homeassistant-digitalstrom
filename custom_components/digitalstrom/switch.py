# -*- coding: UTF-8 -*-
import logging
from typing import Union

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import HomeAssistant
from .pydigitalstrom.client import DSClient
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.devices.scene import DSScene, DSColorScene
from .pydigitalstrom.websocket import DSWebsocketEventListener

from . import DigitalstromConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: DigitalstromConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    client: DSClient = entry.runtime_data.client
    listener: DSWebsocketEventListener = entry.runtime_data.listener
    devices: list = []
    scenes: dict = client.get_scenes()

    scene: Union[DSScene, DSColorScene]
    for scene in scenes.values():
        # only handle scenes
        if not isinstance(scene, DSScene):
            continue
        # only sleeping and present
        if scene.scene_id not in [dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_SLEEPING"], dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_PRESENT"] ]:
            continue

        # get turn on counterpart
        scene_off: DSScene = scenes.get(
            f"{scene.zone_id}_{scene.scene_id + 1}", None,
        )

        # no turn off scene found, skip
        if not scene_off:
            continue

        # add sensors
        devices.append(
            DigitalstromSwitch(
                hass=hass,
                scene_on=scene,
                scene_off=scene_off,
                listener=listener,
                last_scene_id=client.get_last_called_scene_at_setup(scene.zone_id),
            )
        )

    async_add_entities(devices)


class DigitalstromSwitch(RestoreEntity, SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        scene_on: DSScene,
        scene_off: DSScene,
        listener: DSWebsocketEventListener,
        last_scene_id: int = None,
        *args,
        **kwargs,
    ):
        self._hass: HomeAssistant = hass
        self._scene_on: DSScene = scene_on
        self._scene_off: DSScene = scene_off
        self._listener: DSWebsocketEventListener = listener
        self._state: bool = None
        self._last_scene_id: int = last_scene_id

        # sleeping default is false
        if self._scene_on.scene_id == dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_SLEEPING"]:
            self._state = False
        # present default is true
        elif self._scene_on.scene_id == dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_PRESENT"]:
            self._state = True
        super().__init__(*args, **kwargs)

    def _apply_scene(self, zone_id: int, scene_id: int) -> bool:
        """
        set state if a scene called on the server concerns this switch

        :return: True if the scene concerns this switch
        """
        # turn on scene called
        if self._scene_on.zone_id == zone_id and self._scene_on.scene_id == scene_id:
            self._state = True
            return True

        # turn off scene called
        if self._scene_off.zone_id == zone_id and self._scene_off.scene_id == scene_id:
            self._state = False
            return True

        return False

    def _register_callback(self):
        async def event_callback(event: dict):
            # sanity checks
            if "name" not in event:
                return
            if event["name"] != "callScene":
                return
            if "properties" not in event:
                return
            if "sceneID" not in event["properties"]:
                return
            if "zoneID" not in event["properties"]:
                return

            # cast event data
            zone_id: int = int(event["properties"]["zoneID"])
            scene_id: int = int(event["properties"]["sceneID"])

            if self._apply_scene(zone_id, scene_id):
                self.async_write_ha_state()

        return self._listener.register(callback=event_callback)

    @property
    def name(self) -> str:
        return self._scene_on.scene_name

    @property
    def unique_id(self) -> str:
        return f"dsswitch_{self._scene_on.unique_id}"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        await self._scene_on.turn_on()
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._scene_off.turn_on()
        self._state = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._register_callback())

        state = await self.async_get_last_state()
        if state:
            _LOGGER.debug(
                f"trying to restore state of entity {self.entity_id} to {state.state}"
            )
            self._state = state.state == STATE_ON

        # sleeping and present share the last called scene of the zone, so it
        # only tells something if it is one of ours. Otherwise the state we
        # restored (or the default) is the best guess.
        if self._last_scene_id is not None:
            self._apply_scene(self._scene_on.zone_id, self._last_scene_id)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self) -> dict:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self._scene_off.zone_id)},
            "name": self._scene_off.zone_name,
            "model": "Digitalstrom Zone",
            "manufacturer": "digitalSTROM AG",
        }
