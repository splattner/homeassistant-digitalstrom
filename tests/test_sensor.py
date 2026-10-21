"""Tests for the power meter sensors."""


async def update(hass, entity_id: str) -> None:
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )


async def test_meters_become_power_and_energy_sensors(hass, dss, setup_entry):
    dss.meters = ["m1"]
    await setup_entry()

    power = hass.states.get("sensor.meter_m1_consumption")
    energy = hass.states.get("sensor.meter_m1_energy")
    assert power.attributes["device_class"] == "power"
    assert power.attributes["unit_of_measurement"] == "W"
    assert power.attributes["state_class"] == "measurement"
    assert energy.attributes["device_class"] == "energy"
    assert energy.attributes["unit_of_measurement"] == "Wh"
    assert energy.attributes["state_class"] == "total_increasing"

    await update(hass, "sensor.meter_m1_consumption")
    await update(hass, "sensor.meter_m1_energy")

    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0
    assert float(hass.states.get("sensor.meter_m1_energy").state) == 1500.0


async def test_every_meter_gets_its_own_sensors(hass, dss, setup_entry):
    dss.meters = ["m1", "m2"]

    await setup_entry()

    assert sorted(hass.states.async_entity_ids("sensor")) == [
        "sensor.meter_m1_consumption",
        "sensor.meter_m1_energy",
        "sensor.meter_m2_consumption",
        "sensor.meter_m2_energy",
    ]


async def test_no_meters_no_sensors(hass, dss, setup_entry):
    await setup_entry()

    assert hass.states.async_entity_ids("sensor") == []
