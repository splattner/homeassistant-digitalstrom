"""Tests for the config, reauth and options flows."""
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType

from custom_components.digitalstrom.const import DOMAIN

from .conftest import make_entry


def user_input(dss, **overrides) -> dict:
    data = {
        "host": dss.host,
        "port": dss.port,
        "username": "dssadmin",
        "password": "secret",
        "alias": "Home",
        "delay": 200,
    }
    data.update(overrides)
    return data


async def start_user_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return result


async def test_user_flow_creates_entry_with_token(hass, dss):
    dss.ws_mode = "hold"
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Home ({dss.host}:{dss.port})"
    assert result["data"] == {
        "token": "apptoken",
        "host": dss.host,
        "port": dss.port,
        "alias": "Home",
        "delay": 200,
    }
    # the password is not stored
    assert "secret" not in str(result["data"])
    assert result["result"].unique_id == f"127_0_0_1_{dss.port}"
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_user_flow_with_special_characters_in_password(hass, dss):
    dss.ws_mode = "hold"
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss, password="p&ss#w+rd%20=x")
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dss.login_params["password"] == "p&ss#w+rd%20=x"
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_user_flow_invalid_auth(hass, dss):
    dss.reject_login = True
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass, dss):
    dss.http_status = 500
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unexpected_server_answer(hass, dss):
    dss.invalid_api_response = True
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_recovers_after_error(hass, dss):
    dss.ws_mode = "hold"
    dss.reject_login = True
    result = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )
    assert result["errors"] == {"base": "invalid_auth"}

    dss.reject_login = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_user_flow_aborts_if_server_is_configured(hass, dss):
    entry = make_entry(dss)
    entry.add_to_hass(hass)
    # entries are identified by host and port
    hass.config_entries.async_update_entry(entry, unique_id=f"127_0_0_1_{dss.port}")
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(dss)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_replaces_token(hass, dss, setup_entry):
    dss.reject_app_token = True
    entry = await setup_entry()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    # the server hands out a fresh token and accepts it
    dss.app_token = "newtoken"
    dss.reject_app_token = False
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"username": "dssadmin", "password": "secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == "newtoken"
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_flow_wrong_password(hass, dss, setup_entry):
    entry = await setup_entry(token=None)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    dss.reject_login = True
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"username": "dssadmin", "password": "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert "token" not in entry.data


async def test_options_flow_changes_delay_and_reloads(hass, dss, setup_entry):
    entry = await setup_entry(delay=300)
    assert entry.runtime_data.client.stack._delay == 300

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({})["delay"] == 300  # current value is the default

    assert result["data_schema"]({})["scan_interval"] == 30
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"delay": 50, "scan_interval": 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"delay": 50, "scan_interval": 60}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.client.stack._delay == 50
