# -*- coding: UTF-8 -*-
import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DigitalstromConfigEntry
from .const import DOMAIN
from .coordinator import DigitalstromMeterCoordinator, MeterValues
from .pydigitalstrom.devices.meter import DSMeter

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DigitalstromMeterSensorDescription(SensorEntityDescription):
    """a reading of a meter"""

    name_suffix: str
    # unique ids are kept as they were before the sensors used a coordinator
    unique_id_format: str
    value_fn: Callable[[MeterValues], float | None]


METER_SENSORS = (
    DigitalstromMeterSensorDescription(
        key="consumption",
        name_suffix="Consumption",
        unique_id_format="dsmeter_{dsid}_cosumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda values: values.consumption,
    ),
    DigitalstromMeterSensorDescription(
        key="energy",
        name_suffix="Energy",
        unique_id_format="dsenergymeter_{dsid}_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda values: values.energy,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DigitalstromConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    meters = entry.runtime_data.client.get_meters()
    if not meters:
        return

    coordinator = DigitalstromMeterCoordinator(hass, entry, entry.runtime_data.client)
    # a failing first read must not block the other platforms, the sensors are
    # unavailable until a read works
    await coordinator.async_refresh()

    entities = []
    for dsuid, meter in meters.items():
        _LOGGER.info(f"adding meter {meter.name}")
        for description in METER_SENSORS:
            entities.append(
                DigitalstromMeterSensor(coordinator, dsuid, meter, description)
            )
    async_add_entities(entities)


class DigitalstromMeterSensor(
    CoordinatorEntity[DigitalstromMeterCoordinator], SensorEntity
):
    entity_description: DigitalstromMeterSensorDescription

    def __init__(
        self,
        coordinator: DigitalstromMeterCoordinator,
        dsuid: str,
        meter: DSMeter,
        description: DigitalstromMeterSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._dsuid = dsuid
        self._attr_name = f"{meter.name} {description.name_suffix}"
        self._attr_unique_id = description.unique_id_format.format(dsid=meter.unique_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.unique_id)},
            name=meter.name,
            model="DSMeter",
            manufacturer="digitalSTROM AG",
        )

    @property
    def native_value(self) -> float | None:
        values = self.coordinator.data.get(self._dsuid)
        if values is None:
            return None
        return self.entity_description.value_fn(values)
