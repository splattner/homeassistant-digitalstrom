# -*- coding: UTF-8 -*-
import logging
from typing import Callable, Union

from homeassistant.components.light import (
    LightEntity,
    SUPPORT_EFFECT,
    ATTR_EFFECT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, CONF_HOST, CONF_PORT
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from .pydigitalstrom.client import DSClient
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.devices.scene import DSScene, DSColorScene
from .pydigitalstrom.websocket import DSWebsocketEventListener

from .const import DOMAIN
from .util import slugify_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_devices: Callable,
    discovery_info: dict = None,
):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: Callable
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

        effects = dict()

        # get Preset X2-x4
        if scene.scene_id == dsconst.SCENES["PRESET"]["SCENE_PRESET0"]:
            effects["preset2"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET2']}", None,)
            effects["preset3"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET3']}", None,)
            effects["preset4"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET4']}", None,)
        
        if scene.scene_id == dsconst.SCENES["PRESET"]["SCENE_PRESET10"]:
            effects["preset2"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET12']}", None,)
            effects["preset3"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET13']}", None,)
            effects["preset4"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET14']}", None,)
        
        if scene.scene_id == dsconst.SCENES["PRESET"]["SCENE_PRESET20"]:
            effects["preset2"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET22']}", None,)
            effects["preset3"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET23']}", None,)
            effects["preset4"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET24']}", None,)

        if scene.scene_id == dsconst.SCENES["PRESET"]["SCENE_PRESET30"]:
            effects["preset2"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET32']}", None,)
            effects["preset3"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET33']}", None,)
            effects["preset4"] = scenes.get(f"{scene.zone_id}_{scene.color}_{dsconst.SCENES['PRESET']['SCENE_PRESET34']}", None,)


        # no turn on scene found, skip
        if not scene_on:
            continue

        # add light
        _LOGGER.info(f"adding light {scene.scene_id}: Off: {scene.name}, On: {scene_on.name}, Preset2: {effects['preset2'].name}, Preset3: {effects['preset3'].name}, Preset4: {effects['preset4'].name}")
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
        hass: HomeAssistantType,
        scene_on: Union[DSScene, DSColorScene],
        scene_off: Union[DSScene, DSColorScene],
        listener: DSWebsocketEventListener,
        effects,
        *args,
        **kwargs,
    ):
        self._hass: HomeAssistantType = hass
        self._scene_on: Union[DSScene, DSColorScene] = scene_on
        self._scene_off: Union[DSScene, DSColorScene] = scene_off
        self._listener: DSWebsocketEventListener = listener
        self._state: bool = None
        self._scene_effects = effects
        self._effect = ""
        super().__init__(*args, **kwargs)

        self.register_callback()

    @property
    def supported_features(self):
        """Flag supported features."""
        support = SUPPORT_EFFECT


        return support

    @property
    def effect(self):
        """Return the name of the currently running effect."""

        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return ["PRESET1","PRESET2", "PRESET3", "PRESET4"]

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

            # device turned on or broadcast turned on
            if (
                self._scene_on.zone_id == zone_id
                and self._scene_on.color == group_id
                and (self._scene_on.scene_id == scene_id or dsconst.SCENES["PRESET"]["SCENE_PRESET1"] == scene_id)
            ):
                self._state = True
                await self.async_update_ha_state()
            # device turned off or broadcast turned off
            elif (
                self._scene_off.zone_id == zone_id
                and self._scene_off.color == group_id
                and (self._scene_off.scene_id == scene_id or dsconst.SCENES["PRESET"]["SCENE_PRESET0"] == scene_id)
            ):
                self._state = False
                await self.async_update_ha_state()

        _LOGGER.debug(f"Register callback for {self._scene_off.name}")
        self._listener.register(callback=event_callback)

    @property
    def name(self) -> str:
        if self._scene_off.scene_name == "Preset0":
            return "Light"

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

        if ATTR_EFFECT in kwargs:
            _LOGGER.debug(
                f"call turn on with Effect {kwargs[ATTR_EFFECT]}"
            )
            if kwargs[ATTR_EFFECT] == "PRESET1":
                await self._scene_on.turn_on()
                self._effect = "PRESET1"
            if kwargs[ATTR_EFFECT] == "PRESET2":
                await self._scene_effects["preset2"].turn_on()
                self._effect = "PRESET2"
            if kwargs[ATTR_EFFECT] == "PRESET3":
                await self._scene_effects["preset3"].turn_on()
                self._effect = "PRESET3"
            if kwargs[ATTR_EFFECT] == "PRESET4":
                await self._scene_effects["preset4"].turn_on()
                self._effect = "PRESET4"
                
        else:
            await self._scene_on.turn_on()
            self._effect = "PRESET1"
        self._state = True

    async def async_turn_off(self, **kwargs) -> None:
        await self._scene_off.turn_on()
        self._effect = ""
        self._state = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state: bool = await self.async_get_last_state()
        if not state:
            return

        _LOGGER.debug(
            f"trying to restore state of entity {self.entity_id} to {state.state}"
        )
        self._state = state.state == STATE_ON

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
