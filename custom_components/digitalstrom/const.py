"""Define constants for the digitalSTROM component."""
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
    dsconst.SCENES["PRESET"]["SCENE_PRESET0"],
    dsconst.SCENES["PRESET"]["SCENE_PRESET1"],
    dsconst.SCENES["PRESET"]["SCENE_PRESET2"],
    dsconst.SCENES["PRESET"]["SCENE_PRESET3"],
    dsconst.SCENES["PRESET"]["SCENE_PRESET4"],
    dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_SLEEPING"],
    dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_WAKEUP"],
    dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_PRESENT"],
    dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ABSENT"],
    dsconst.SCENES["GROUP_INDIPENDENT"]["SCENE_ZONE_ACTIVE"],
]
