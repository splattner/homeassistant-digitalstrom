"""Tests for the power meter sensors."""
from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.digitalstrom.const import DOMAIN

from .conftest import wait_for


async def next_poll(hass, seconds: int = 31) -> None:
    """let the coordinator read the meters once more"""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


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
    # values are there without waiting for the first poll
    assert float(power.state) == 42.0
    assert float(energy.state) == 1500.0


async def test_every_meter_gets_its_own_sensors_and_values(hass, dss, setup_entry):
    dss.meters = ["m1", "m2"]
    dss.meter_values = {"m2": {"consumption": 7.5, "energy": 99.0}}

    await setup_entry()

    assert sorted(hass.states.async_entity_ids("sensor")) == [
        "sensor.meter_m1_consumption",
        "sensor.meter_m1_energy",
        "sensor.meter_m2_consumption",
        "sensor.meter_m2_energy",
    ]
    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0
    assert float(hass.states.get("sensor.meter_m2_consumption").state) == 7.5
    assert float(hass.states.get("sensor.meter_m2_energy").state) == 99.0


async def test_all_meters_are_read_with_two_requests(hass, dss, setup_entry):
    dss.meters = ["m1", "m2", "m3"]
    await setup_entry()

    assert dss.metering_requests == [
        ("consumption", ["all"]),
        ("energy", ["all"]),
    ]

    dss.metering_requests.clear()
    await next_poll(hass)
    await wait_for(lambda: len(dss.metering_requests) == 2)
    assert [reading for reading, _ in dss.metering_requests] == ["consumption", "energy"]


async def test_dsid_case_does_not_matter(hass, dss, setup_entry):
    dss.meters = ["m1"]
    dss.metering_id_key = "dsid"
    dss.metering_uppercase_dsid = True

    await setup_entry()

    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0


async def test_meters_without_readings_do_not_break_the_others(hass, dss, setup_entry):
    """a dSS can know meters that deliver nothing; they are just unknown"""
    dss.meters = ["m1", "m2", "m3"]
    dss.meters_without_metering = {"m2", "m3"}

    await setup_entry()

    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0
    assert float(hass.states.get("sensor.meter_m1_energy").state) == 1500.0
    assert hass.states.get("sensor.meter_m2_consumption").state == "unknown"
    assert hass.states.get("sensor.meter_m3_energy").state == "unknown"


async def test_servers_that_answer_with_the_dsuid(hass, dss, setup_entry):
    """newer servers deprecate the dSID in favor of the dSUID"""
    dss.meters = ["m1", "m2"]
    dss.meter_values = {"m2": {"consumption": 7.5, "energy": 99.0}}
    dss.metering_id_key = "dSUID"

    await setup_entry()

    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0
    assert float(hass.states.get("sensor.meter_m2_consumption").state) == 7.5
    assert float(hass.states.get("sensor.meter_m2_energy").state) == 99.0


async def test_single_meter_answer_without_an_id(hass, dss, setup_entry):
    dss.meters = ["m1"]
    dss.metering_id_key = None

    await setup_entry()

    assert float(hass.states.get("sensor.meter_m1_consumption").state) == 42.0
    assert float(hass.states.get("sensor.meter_m1_energy").state) == 1500.0


async def test_unmatched_readings_are_logged_once(hass, dss, setup_entry, caplog):
    """several meters and no way to tell whose value is whose"""
    dss.meters = ["m1", "m2"]
    dss.metering_id_key = None

    await setup_entry()
    await next_poll(hass)
    await wait_for(lambda: len(dss.metering_requests) >= 4)

    assert hass.states.get("sensor.meter_m1_consumption").state == "unknown"
    warnings = [r for r in caplog.records if "don't belong to any known meter" in r.getMessage()]
    assert len(warnings) == 1
    assert "'value': 42.0" in warnings[0].getMessage()  # what the server sent


async def test_missing_readings_are_unknown(hass, dss, setup_entry):
    dss.meters = ["m1"]
    dss.metering_empty = True

    await setup_entry()

    assert hass.states.get("sensor.meter_m1_consumption").state == "unknown"
    assert hass.states.get("sensor.meter_m1_energy").state == "unknown"


async def test_sensors_are_unavailable_while_the_server_fails(hass, dss, setup_entry):
    dss.meters = ["m1"]
    await setup_entry()

    dss.fail_metering = True
    await next_poll(hass)
    await wait_for(
        lambda: hass.states.get("sensor.meter_m1_consumption").state == "unavailable"
    )

    dss.fail_metering = False
    dss.meter_values = {"m1": {"consumption": 100.0, "energy": 2000.0}}
    await next_poll(hass, seconds=62)
    await wait_for(
        lambda: hass.states.get("sensor.meter_m1_consumption").state == "100.0"
    )


async def test_failing_first_read_does_not_block_setup(hass, dss, setup_entry):
    dss.meters = ["m1"]
    dss.fail_metering = True

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.meter_m1_consumption").state == "unavailable"
    assert len(hass.states.async_entity_ids("light")) == 1  # other platforms are fine

    dss.fail_metering = False
    await next_poll(hass, seconds=31)
    await wait_for(
        lambda: hass.states.get("sensor.meter_m1_consumption").state == "42.0"
    )


async def test_rejected_token_while_polling_starts_reauth(hass, dss, setup_entry):
    dss.meters = ["m1"]
    entry = await setup_entry()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    dss.reject_app_token = True
    entry.runtime_data.client._last_request = None  # make it log in again
    await next_poll(hass)
    await wait_for(lambda: hass.config_entries.flow.async_progress_by_handler(DOMAIN))

    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == "reauth"


async def test_scan_interval_option_sets_the_poll_interval(hass, dss, setup_entry):
    dss.meters = ["m1"]
    await setup_entry(scan_interval=120)
    coordinator = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.meter_m1_consumption"
    ).coordinator

    assert coordinator.update_interval == timedelta(seconds=120)


async def test_no_meters_no_sensors(hass, dss, setup_entry):
    await setup_entry()

    assert hass.states.async_entity_ids("sensor") == []
