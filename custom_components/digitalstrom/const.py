"""Define constants for the digitalSTROM component."""
from custom_components.digitalstrom.pydigitalstrom.constants import SCENE_PRESET0
from typing import List

from .pydigitalstrom import constants as dsconst

DOMAIN: str = "digitalstrom"

HOST_FORMAT: str = "https://{host}:{port}"
SLUG_FORMAT: str = "{host}_{port}"
TITLE_FORMAT: str = "{alias} ({host}:{port})"

CONF_DELAY: str = "delay"

DIGITALSTROM_MANUFACTURERS: List[str] = ["digitalSTROM AG", "aizo ag"]
DEFAULT_HOST: str = "dss.local"
DEFAULT_PORT: int = 8080
DEFAULT_DELAY: int = 500
DEFAULT_USERNAME: str = "dssadmin"
DEFAULT_ALIAS: str = "Apartment"

OPTION_GENERIC_SCENES: str = "generic_scenes"
OPTION_GENERIC_SCENES_DEFAULT: List[str] = [
    dsconst.SCENE_PRESET0,
    dsconst.SCENE_PRESET1,
    dsconst.SCENE_PRESET2,
    dsconst.SCENE_PRESET3,
    dsconst.SCENE_PRESET4,
    dsconst.SCENE_SLEEPING,
    dsconst.SCENE_WAKEUP,
    dsconst.SCENE_PRESENT,
    dsconst.SCENE_ABSENT,
    dsconst.SCENE_ROOM_WAKEUP,
]
