"""Define constants for the digitalSTROM component."""

DOMAIN: str = "digitalstrom"

SLUG_FORMAT: str = "{host}_{port}"
TITLE_FORMAT: str = "{alias} ({host}:{port})"

CONF_DELAY: str = "delay"

# fired on the event bus whenever a scene is called on the digitalSTROM server
EVENT_SCENE_CALLED: str = "digitalstrom_scene_called"

DEFAULT_HOST: str = "dss.local"
DEFAULT_PORT: int = 8080
DEFAULT_DELAY: int = 500
DEFAULT_USERNAME: str = "dssadmin"
DEFAULT_ALIAS: str = "Apartment"

DEFAULT_SCAN_INTERVAL: int = 30  # seconds between reading the meters
MIN_SCAN_INTERVAL: int = 10
MAX_SCAN_INTERVAL: int = 3600

MIN_DELAY: int = 10
MAX_DELAY: int = 10000
