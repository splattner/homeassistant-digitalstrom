"""The digitalSTROM integration."""
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_ALIAS,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.start import async_at_start

from .pydigitalstrom.client import DSClient
from .pydigitalstrom.exceptions import DSAuthenticationException, DSException
from .pydigitalstrom.websocket import DSWebsocketEventListener

from .const import CONF_DELAY, DEFAULT_DELAY
from .events import async_create_scene_event_callback
from .util import get_session, slugify_entry

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.LIGHT, Platform.SWITCH, Platform.COVER, Platform.SCENE, Platform.SENSOR]


@dataclass
class DigitalstromData:
    """runtime data of a config entry"""

    client: DSClient
    listener: DSWebsocketEventListener


type DigitalstromConfigEntry = ConfigEntry[DigitalstromData]


def get_delay(entry: ConfigEntry) -> int:
    """delay between commands, the options win over the initial setup"""
    return entry.options.get(CONF_DELAY, entry.data.get(CONF_DELAY, DEFAULT_DELAY))


async def async_setup_entry(hass: HomeAssistant, entry: DigitalstromConfigEntry) -> bool:
    """
    set up digitalSTROM component from config entry
    """
    _LOGGER.debug("digitalstrom setup started")

    # old installations don't have an app token in their config entry
    if not entry.data.get(CONF_TOKEN, None):
        raise ConfigEntryAuthFailed(
            "No app token in config entry, please authenticate again"
        )

    # entries from before unique ids were used
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=slugify_entry(
                host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]
            ),
        )

    # setup client and listener
    client = DSClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        apptoken=entry.data[CONF_TOKEN],
        apartment_name=entry.data[CONF_ALIAS],
        stack_delay=get_delay(entry),
        session=get_session(hass),
    )
    listener = DSWebsocketEventListener(client=client, event_name="callScene")

    # load all scenes from digitalSTROM server
    # this fails often on the first connection, but works on the second
    try:
        await client.initialize()
    except DSAuthenticationException as err:
        raise ConfigEntryAuthFailed(f"App token rejected by {client.host}") from err
    except (DSException, RuntimeError, ConnectionResetError):
        try:
            await client.initialize()
        except DSAuthenticationException as err:
            raise ConfigEntryAuthFailed(f"App token rejected by {client.host}") from err
        except (DSException, RuntimeError, ConnectionResetError) as err:
            raise ConfigEntryNotReady(
                f"Failed to initialize digitalSTROM server at {client.host}"
            ) from err

    # we're connected
    _LOGGER.debug(f"Successfully retrieved session token from digitalSTROM server at {client.host}")

    entry.runtime_data = DigitalstromData(client=client, listener=listener)

    # let automations react to scenes called anywhere (wall buttons, apps, ...)
    entry.async_on_unload(
        listener.register(
            callback=async_create_scene_event_callback(hass, entry.entry_id, client)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # start websocket listener and action delayer loops on hass startup,
    # or right away if hass is already running (e.g. entry was just added)
    async def digitalstrom_start_loops(hass: HomeAssistant) -> None:
        _LOGGER.info(f"loops started for digitalSTROM server at {client.host}")
        entry.async_create_background_task(
            hass, listener.start(), "digitalstrom-websocket"
        )
        await client.stack.start()

    entry.async_on_unload(async_at_start(hass, digitalstrom_start_loops))

    # apply changed options
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DigitalstromConfigEntry) -> bool:
    """
    unload a config entry, stops the loops and removes the entities
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = entry.runtime_data
        await data.listener.stop()
        await data.client.stack.stop()
        _LOGGER.info(f"loops stopped for digitalSTROM server at {data.client.host}")
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: DigitalstromConfigEntry) -> None:
    """reload the entry when the options changed"""
    await hass.config_entries.async_reload(entry.entry_id)
