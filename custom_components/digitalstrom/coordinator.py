"""Update the power meters of a digitalSTROM server."""
import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .pydigitalstrom.client import DSClient
from .pydigitalstrom.exceptions import DSAuthenticationException, DSException
from .util import get_option

_LOGGER = logging.getLogger(__name__)


@dataclass
class MeterValues:
    """latest readings of one meter, None if the server has no value yet"""

    consumption: float | None
    energy: float | None


class DigitalstromMeterCoordinator(DataUpdateCoordinator[dict[str, MeterValues]]):
    """reads all meters in one update, keyed by the dSUID of the meter"""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: DSClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} meters",
            update_interval=timedelta(
                seconds=get_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, MeterValues]:
        meters = list(self._client.get_meters().values())

        try:
            # two requests no matter how many meters there are, a dSS is easily
            # overwhelmed
            consumption = await self._client.get_latest_metering(meters, "consumption")
            energy = await self._client.get_latest_metering(meters, "energy")
        except DSAuthenticationException as err:
            raise ConfigEntryAuthFailed("App token rejected by server") from err
        except DSException as err:
            raise UpdateFailed(f"Error reading the meters: {err}") from err

        return {
            meter.dsuid: MeterValues(
                consumption=consumption.get(meter.dsuid),
                energy=energy.get(meter.dsuid),
            )
            for meter in meters
        }
