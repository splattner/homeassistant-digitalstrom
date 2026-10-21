# -*- coding: UTF-8 -*-
import logging
from typing import Callable, Union

from homeassistant.components.light import (
    LightEntity,
    LightEntityFeature,
    ColorMode,
    ATTR_EFFECT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, CONF_HOST, CONF_PORT
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant
from .pydigitalstrom.client import DSClient
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.devices.scene import DSScene, DSColorScene
from .pydigitalstrom.websocket import DSWebsocketEventListener

from .const import DOMAIN
from .util import slugify_entry

_LOGGER = logging.getLogger(__name__)

# turn off scene id -> scene ids of the Preset X2-X4 effects of that light
PRESET_EFFECT_SCENES = {
    dsconst.SCENES["PRESET"]["SCENE_PRESET0"]: (
        dsconst.SCENES["PRESET"]["SCENE_PRESET2"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET3"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET4"],
    ),
    dsconst.SCENES["PRESET"]["SCENE_PRESET10"]: (
        dsconst.SCENES["PRESET"]["SCENE_PRESET12"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET13"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET14"],
    ),
    dsconst.SCENES["PRESET"]["SCENE_PRESET20"]: (
        dsconst.SCENES["PRESET"]["SCENE_PRESET22"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET23"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET24"],
    ),
    dsconst.SCENES["PRESET"]["SCENE_PRESET30"]: (
        dsconst.SCENES["PRESET"]["SCENE_PRESET32"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET33"],
        dsconst.SCENES["PRESET"]["SCENE_PRESET34"],
    ),
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_devices: Callable,
    discovery_info: dict = None,
):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    entry_slug: str = slugify_entry(
        host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]
    )

    client: DSClient = hass.data[DOMAIN][entry_slug]["client"]
    listener: DSWebsocketEventListener = hass.data[DOMAIN][entry_slug]["listener"]
    devices: dict = []
    scenes: dict = client.get_scenes()

    scene: Union[DSScene, DSColorScene]
    for scene in scenes.values():
        # only handle light (color 1) scenes
        if not isinstance(scene, DSColorScene) or scene.color != dsconst.GROUP_LIGHTS:
            continue
        # not an area or broadcast turn off scene
        if scene.scene_id not in (
            dsconst.SCENES["PRESET"]["SCENE_PRESET0"],
            dsconst.SCENES["AREA"]["SCENE_AREA1_OFF"],
            dsconst.SCENES["AREA"]["SCENE_AREA2_OFF"],
            dsconst.SCENES["AREA"]["SCENE_AREA3_OFF"],
            dsconst.SCENES["AREA"]["SCENE_AREA4_OFF"],
        ):
            continue

        # get turn on counterpart
        scene_on: Union[DSScene, DSColorScene] = scenes.get(
            f"{scene.zone_id}_{scene.color}_{scene.scene_id + 5}", None,
        )

        # get Preset X2-X4, only those that exist on the server
        effects = dict()
        for effect_key, preset_id in zip(
            ("preset2", "preset3", "preset4"),
            PRESET_EFFECT_SCENES.get(scene.scene_id, ()),
        ):
            effect_scene = scenes.get(f"{scene.zone_id}_{scene.color}_{preset_id}")
            if effect_scene:
                effects[effect_key] = effect_scene

        # no turn on scene found, skip
        if not scene_on:
            continue

        # add light
        _LOGGER.info(
            f"adding light {scene.scene_id}: Off: {scene.name}, On: {scene_on.name}, "
            f"Effects: {[e.name for e in effects.values()]}"
        )
        devices.append(
            DigitalstromLight(
                hass=hass, scene_on=scene_on, scene_off=scene, listener=listener, effects=effects
            )
        )

    device: DigitalstromLight
    async_add_entities(device for device in devices)


class DigitalstromLight(RestoreEntity, LightEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        scene_on: Union[DSScene, DSColorScene],
        scene_off: Union[DSScene, DSColorScene],
        listener: DSWebsocketEventListener,
        effects,
        *args,
        **kwargs,
    ):
        self._hass: HomeAssistant = hass
        self._scene_on: Union[DSScene, DSColorScene] = scene_on
        self._scene_off: Union[DSScene, DSColorScene] = scene_off
        self._listener: DSWebsocketEventListener = listener
        self._state: bool = None
        self._effect = None

        # effect name -> scene to call, PRESET1 is the regular turn on scene
        self._effect_scenes: dict = {"PRESET1": scene_on}
        for key, effect_scene in effects.items():
            self._effect_scenes[key.upper()] = effect_scene

        super().__init__(*args, **kwargs)

        self.register_callback()

    @property
    def supported_features(self):
        """Flag supported features."""
        support = LightEntityFeature.EFFECT


        return support
    
    @property
    def color_mode(self):
        color_mode = ColorMode.ONOFF
        return color_mode

    
    @property
    def supported_color_modes(self):
        supported_color_modes = {ColorMode.ONOFF}
        return supported_color_modes

    @property
    def effect(self):
        """Return the name of the currently running effect."""

        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return list(self._effect_scenes)

    def register_callback(self):
        async def event_callback(event: dict) -> None:
            # sanity checks
            if "name" not in event:
                return
            if event["name"] != "callScene":
                return
            if "properties" not in event:
                return
            if "sceneID" not in event["properties"]:
                return
            if "groupID" not in event["properties"]:
                return
            if "zoneID" not in event["properties"]:
                return

            # cast event data
            zone_id: int = int(event["properties"]["zoneID"])
            group_id: int = int(event["properties"]["groupID"])
            scene_id: int = int(event["properties"]["sceneID"])

            # Map preset scene ids to effect names
            preset_map = {
                dsconst.SCENES["PRESET"]["SCENE_PRESET1"]: "PRESET1",
                dsconst.SCENES["PRESET"]["SCENE_PRESET2"]: "PRESET2",
                dsconst.SCENES["PRESET"]["SCENE_PRESET3"]: "PRESET3",
                dsconst.SCENES["PRESET"]["SCENE_PRESET4"]: "PRESET4",
            }

            # device turned on or broadcast turned on (handle PRESET1..PRESET4)
            if (
                self._scene_on.zone_id == zone_id
                and self._scene_on.color == group_id
                and (self._scene_on.scene_id == scene_id or scene_id in preset_map)
            ):
                self._state = True
                # set effect according to which preset was called (default to PRESET1)
                effect = preset_map.get(scene_id, "PRESET1")
                self._effect = effect if effect in self._effect_scenes else "PRESET1"
                self.async_write_ha_state()
            # device turned off or broadcast turned off
            elif (
                self._scene_off.zone_id == zone_id
                and self._scene_off.color == group_id
                and (self._scene_off.scene_id == scene_id or dsconst.SCENES["PRESET"]["SCENE_PRESET0"] == scene_id)
            ):
                self._state = False
                self._effect = None
                self.async_write_ha_state()

        _LOGGER.debug(f"Register callback for {self._scene_off.name}")
        self._listener.register(callback=event_callback)

    @property
    def name(self) -> str:
        if self._scene_off.scene_name.startswith("Preset"):
            return self._scene_off.zone_name

        return self._scene_off.scene_name

    @property
    def unique_id(self) -> str:
        return f"dslight_{self._scene_off.unique_id}"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        effect = kwargs.get(ATTR_EFFECT, "PRESET1")
        scene = self._effect_scenes.get(effect)
        if scene is None:
            _LOGGER.warning(f"unknown effect {effect} for {self.name}, using PRESET1")
            effect = "PRESET1"
            scene = self._scene_on

        _LOGGER.debug(f"call turn on with Effect {effect}")
        await scene.turn_on()
        self._effect = effect
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._scene_off.turn_on()
        self._effect = None
        self._state = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state: bool = await self.async_get_last_state()
        if not state:
            return

        _LOGGER.debug(
            f"trying to restore state of entity {self.entity_id} to {state.state}"
        )
        self._state = state.state == STATE_ON

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
