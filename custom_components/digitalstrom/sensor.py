# -*- coding: UTF-8 -*-
import logging
from typing import Callable, Union

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import POWER_WATT, CONF_HOST, CONF_PORT
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from .pydigitalstrom.client import DSClient
from .pydigitalstrom import constants as dsconst
from .pydigitalstrom.devices.scene import DSMeter
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
    
    devices: dict = []
    meters: dict = client.get_meters()

    meter: DSMeter
    for meter in meters.values():
        # add meter
        _LOGGER.info(f"adding meter {meter.name}")
        devices.append(
            DigitalstromMeter(
                hass=hass, dsmeter=meter
            )
        )

    device: DigitalstromMeter
    async_add_entities(device for device in devices)


class DigitalstromMeter(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistantType,
        dsmeter: DSMeter,
        *args,
        **kwargs,
    ):
        self._hass: HomeAssistantType = hass
        self._dsmeter: DSMeter = dsmeter
        self._state: int = None
        super().__init__(*args, **kwargs)


    @property
    def name(self) -> str:
        return self._dsmeter.name

    @property
    def unique_id(self) -> str:
        return f"dsmeter_{self._dsmeter.unique_id}"

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self) -> int:
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return POWER_WATT

    @property
    def device_class(self):
        return "power"

    async def async_update(self, **kwargs) -> None:
        self._state = await self._dsmeter.getLatest()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self) -> dict:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self._dsmeter.unique_id)},
            "name": self._dsmeter.name,
            "model": "DSMeter",
            "manufacturer": "digitalSTROM AG",
        }
