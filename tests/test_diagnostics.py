"""Tests for the diagnostics download."""
import json

from custom_components.digitalstrom.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import wait_for


async def test_diagnostics_describe_the_state_without_secrets(hass, dss, setup_entry):
    dss.reachable_scenes = [0, 5]
    dss.meters = ["m1", "m2"]
    dss.meters_without_metering = {"m2"}
    dss.last_called = {(0, 1): 5}
    entry = await setup_entry()
    await wait_for(lambda: len(dss._sockets) == 1)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["command_stack"] == {"running": True, "delay_ms": 10, "pending": 0}
    assert result["websocket"]["running"] and result["websocket"]["connected"]
    assert result["websocket"]["callbacks"] == 4  # event, light, two switches
    assert result["zones"] == {0: "Apartment"}
    assert result["scenes"]["DSColorScene"] > 0 and result["scenes"]["DSScene"] > 0
    assert result["last_called_scenes_at_setup"]["zone 0 group 1"] == 5
    assert result["entry"]["data"]["alias"] == "Apartment"
    assert result["entry"]["data"]["delay"] == 10
    assert result["meters"]["last_update_success"] is True
    assert result["meters"]["update_interval_s"] == 30
    # the meter without readings is listed, too, that is what a report needs
    assert result["meters"]["readings"] == {
        "meter 1": {"consumption": 42.0, "energy": 1500.0},
        "meter 2": {"consumption": None, "energy": None},
    }
    assert [m["name"] for m in result["meters"]["known"]] == ["Meter m1", "Meter m2"]


async def test_diagnostics_contain_no_secrets_or_identifiers(hass, dss, setup_entry):
    dss.meters = ["m1"]
    entry = await setup_entry()

    result = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(result)  # must be serializable, too

    assert "apptoken" not in text  # token
    assert dss.host not in text  # host, title and unique id
    assert "m1" not in text.replace("Meter m1", "")  # dSUID and dSID of the meter
    assert "dsid-m1" not in text
    assert result["entry"]["data"]["token"] == "**REDACTED**"
    assert result["entry"]["data"]["host"] == "**REDACTED**"
    assert result["entry"]["unique_id"] == "**REDACTED**"
    assert result["entry"]["title"] == "**REDACTED**"


async def test_diagnostics_without_meters(hass, dss, setup_entry):
    entry = await setup_entry()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["meters"]["known"] == []
    assert result["meters"]["last_update_success"] is None
    assert result["meters"]["readings"] is None


async def test_diagnostics_show_a_stopped_server(hass, dss, setup_entry):
    """the interesting case: nothing connected"""
    entry = await setup_entry()
    await wait_for(lambda: len(dss._sockets) == 1)
    await dss.close_sockets()
    dss.http_status = 500  # no way to reconnect

    await wait_for(lambda: not entry.runtime_data.listener.connected)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["websocket"]["running"] is True
    assert result["websocket"]["connected"] is False
