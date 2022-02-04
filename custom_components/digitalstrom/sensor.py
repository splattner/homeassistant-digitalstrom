# -*- coding: UTF-8 -*-
import logging
from typing import Callable, Union

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import POWER_WATT, ENERGY_WATT_HOUR, CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from .pydigitalstrom.client import DSClient
from .pydigitalstrom.devices.meter import DSMeter
from homeassistant.util import dt


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
    hass: HomeAssistantType, 
    entry: ConfigEntry, 
    async_add_entities: Callable
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
            DigitalstromConsumptionMeter(
                hass=hass, dsmeter=meter
            )
        )
        devices.append(
            DigitalstromEnergyMeter(
                hass=hass, dsmeter=meter
            )
        )

    device: Union[DigitalstromConsumptionMeter,DigitalstromEnergyMeter]
    async_add_entities(device for device in devices)


class DigitalstromConsumptionMeter(SensorEntity):
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
        return f"{self._dsmeter.name} Consumption"

    @property
    def unique_id(self) -> str:
        return f"dsmeter_{self._dsmeter.unique_id}_cosumption"

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self) -> int:
        return self._state

    @property
    def state_class(self):
        return "measurement"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return POWER_WATT

    @property
    def device_class(self):
        return "power"

    @property
    def device_info(self) -> dict:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self._dsmeter.unique_id)},
            "name": self._dsmeter.name,
            "model": "DSMeter",
            "manufacturer": "digitalSTROM AG",
        }

    async def async_update(self, **kwargs) -> None:
        self._state = await self._dsmeter.get_latest()

class DigitalstromEnergyMeter(SensorEntity):
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
        return f"{self._dsmeter.name} Energy"

    @property
    def unique_id(self) -> str:
        return f"dsenergymeter_{self._dsmeter.unique_id}_energy"

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self) -> int:
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return ENERGY_WATT_HOUR
        
    @property
    def state_class(self):
        return "total_increasing"

    @property
    def device_class(self):
        return "energy"

    @property
    def device_info(self) -> dict:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self._dsmeter.unique_id)},
            "name": self._dsmeter.name,
            "model": "DSMeter",
            "manufacturer": "digitalSTROM AG",
        }

    async def async_update(self, **kwargs) -> None:
        self._state = await self._dsmeter.get_latest_energy()
