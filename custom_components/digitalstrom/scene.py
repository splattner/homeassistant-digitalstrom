# -*- coding: UTF-8 -*-
import logging
from typing import Callable, Union

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from .pydigitalstrom import constants
from .pydigitalstrom.client import DSClient
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.devices.scene import DSScene, DSColorScene

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
    scenes: list = []

    scene: Union[DSScene, DSColorScene]
    for scene in client.get_scenes().values():
        # only color scenes have a special check
        if isinstance(scene, DSColorScene):
            # area and broadcast scenes (yellow/1 and grey/2 up to id 9)
            # shouldn't be added since they'll be processed as
            # lights and covers
            if scene.color in (constants.GROUP_LIGHTS, constants.GROUP_BLINDS) and scene.scene_id <= 9:
                continue

            # Preset X2-X4 are handled with Effects
            if scene.color == constants.GROUP_LIGHTS and scene.scene_id in [
                dsconst.SCENES["PRESET"]["SCENE_PRESET2"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET3"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET4"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET12"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET13"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET14"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET22"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET23"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET24"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET32"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET33"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET34"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET42"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET43"],
                dsconst.SCENES["PRESET"]["SCENE_PRESET44"],
                ]:
                continue

            # Ignore never used scenes
            if scene.scene_id in [
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_DEEP_OFF"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_STANDBY"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ZONE_ACTIVE"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_AUTO_STANDBY"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ABSENT"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_PRESENT"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_SLEEPING"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_WAKEUP"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_DOOR_BELL"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_PANIC"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ALARM_1"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ALARM_2"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ALARM_3"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ALARM_4"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_WIND"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_NO_WIND"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_RAIN"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_NO_RAIN"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_HAIL"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_NO_HAIL"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_POLLUTION"],
                dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_BURGLARY"]
            ]:
                continue

        _LOGGER.info(f"adding scene {scene.scene_id}: {scene.name}")
        scenes.append(DigitalstromScene(scene=scene, config_entry=entry))

    scene: DigitalstromScene
    async_add_entities(scene for scene in scenes)


class DigitalstromScene(Scene):
    """Representation of a digitalSTROM scene."""

    def __init__(
        self,
        scene: Union[DSScene, DSColorScene],
        config_entry: ConfigEntry,
        *args,
        **kwargs,
    ):
        self._scene: Union[DSScene, DSColorScene] = scene
        self._config_entry: ConfigEntry = config_entry
        super().__init__(*args, **kwargs)

    @property
    def name(self) -> str:
        return self._scene.name

    @property
    def unique_id(self) -> str:
        return f"dsscene_{self._scene.unique_id}"

    async def async_activate(self) -> None:
        _LOGGER.info(f"calling scene {self._scene.scene_id}")
        await self._scene.turn_on()

    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self) -> dict:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self._scene.unique_id)},
            "name": self._scene.name,
            "model": "DSScene",
            "manufacturer": "digitalSTROM AG",
        }