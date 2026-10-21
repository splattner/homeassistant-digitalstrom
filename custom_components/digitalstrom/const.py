"""Define constants for the digitalSTROM component."""

DOMAIN: str = "digitalstrom"

SLUG_FORMAT: str = "{host}_{port}"
TITLE_FORMAT: str = "{alias} ({host}:{port})"

CONF_DELAY: str = "delay"

DEFAULT_HOST: str = "dss.local"
DEFAULT_PORT: int = 8080
DEFAULT_DELAY: int = 500
DEFAULT_USERNAME: str = "dssadmin"
DEFAULT_ALIAS: str = "Apartment"

MIN_DELAY: int = 10
MAX_DELAY: int = 10000
