"""The digitalSTROM integration."""
import asyncio
import logging
import socket
import urllib3

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ALIAS,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.exceptions import ConfigEntryNotReady, InvalidStateError
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant

from .pydigitalstrom.client import DSClient
from .pydigitalstrom.exceptions import DSException
from .pydigitalstrom.websocket import DSWebsocketEventListener

from .const import (
    DOMAIN,
    HOST_FORMAT,
    SLUG_FORMAT,
    CONF_DELAY,
    DEFAULT_DELAY,
)
from .util import slugify_entry

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.LIGHT, Platform.MEDIA_PLAYER, Platform.SWITCH, Platform.COVER, Platform.SCENE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    load configuration for digitalSTROM component
    """
    # not configured
    if DOMAIN not in config:
        return True

    # already imported
    if hass.config_entries.async_entries(DOMAIN):
        return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    set up digitalSTROM component from config entry
    """
    _LOGGER.debug("digitalstrom setup started")

    # initialize component data
    hass.data.setdefault(DOMAIN, dict())

    # old installations don't have an app token in their config entry
    if not entry.data.get(CONF_TOKEN, None):
        raise InvalidStateError(
            "No app token in config entry, please re-setup the integration"
        )

    # setup client and listener
    client = DSClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        apptoken=entry.data[CONF_TOKEN],
        apartment_name=entry.data[CONF_ALIAS],
        stack_delay=entry.data.get(CONF_DELAY, DEFAULT_DELAY),
        loop=hass.loop,
    )
    listener = DSWebsocketEventListener(client=client, event_name="callScene")

    # store client in hass data for future usage
    entry_slug = slugify_entry(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    hass.data[DOMAIN].setdefault(entry_slug, dict())
    hass.data[DOMAIN][entry_slug]["client"] = client
    hass.data[DOMAIN][entry_slug]["listener"] = listener

    # load all scenes from digitalSTROM server
    # this fails often on the first connection, but works on the second
    try:
        await client.initialize()
    except (DSException, RuntimeError, ConnectionResetError):
        try:
            await client.initialize()
        except (DSException, RuntimeError, ConnectionResetError):
            raise ConfigEntryNotReady(f"Failed to initialize digitalSTROM server at {client.host}")

    # we're connected
    _LOGGER.debug(f"Successfully retrieved session token from digitalSTROM server at {client.host}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


    # start websocket listener and action delayer loops on hass startup
    async def digitalstrom_start_loops(event):
        _LOGGER.info(f"loops started for digitalSTROM server at {client.host}")
        hass.async_create_background_task(listener.start)
        hass.async_create_background_task(client.stack.start)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, digitalstrom_start_loops)

    # start websocket listener and action delayer loops on hass shutdown
    async def digitalstrom_stop_loops(event):
        _LOGGER.info(f"loops stopped for digitalSTROM server at {client.host}")
        hass.async_create_background_task(client.stack.stop)
        hass.async_create_background_task(listener.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, digitalstrom_stop_loops)

    return True
