import socket

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import SLUG_FORMAT


def slugify_entry(host, port):
    return slugify(SLUG_FORMAT.format(host=host, port=port))


def get_option(entry: ConfigEntry, key: str, default):
    """an option, falls back to the value from the initial setup"""
    return entry.options.get(key, entry.data.get(key, default))


def get_session(hass: HomeAssistant) -> ClientSession:
    """
    shared session for talking to a dSS, owned by home assistant

    Most servers use self-signed certificates, so verification is turned off.
    The server is only reachable via IPv4.
    """
    return async_get_clientsession(hass, verify_ssl=False, family=socket.AF_INET)
