"""Tests for the pydigitalstrom library against a fake dSS."""
import asyncio
import logging

import pytest

from custom_components.digitalstrom.pydigitalstrom import websocket
from custom_components.digitalstrom.pydigitalstrom.apptokenhandler import (
    DSAppTokenHandler,
)
from custom_components.digitalstrom.pydigitalstrom.client import DSClient
from custom_components.digitalstrom.pydigitalstrom.websocket import (
    DSWebsocketEventListener,
)

# characters that break an unencoded query string
TRICKY_PASSWORD = "p&ss#w+rd%20=x"


@pytest.fixture
def client(dss) -> DSClient:
    return DSClient(
        host=dss.host,
        port=dss.port,
        apptoken="apptoken",
        apartment_name="Home",
        stack_delay=10,
    )


async def test_apptoken_credentials_are_url_encoded(dss):
    handler = DSAppTokenHandler(dss.host, dss.port, "dssadmin", TRICKY_PASSWORD)

    assert await handler.request_apptoken() == "apptoken"
    assert dss.login_params == {"user": "dssadmin", "password": TRICKY_PASSWORD}


async def test_request_logging_never_contains_secrets(dss, caplog):
    caplog.set_level(logging.DEBUG)
    handler = DSAppTokenHandler(dss.host, dss.port, "dssadmin", TRICKY_PASSWORD)

    await handler.request_apptoken()

    # the fake server logs complete urls itself, only look at our loggers
    ours = [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("custom_components.digitalstrom")
    ]
    assert ours, "expected debug output from the request handler"
    for message in ours:
        assert TRICKY_PASSWORD not in message
        assert "password=" not in message
        assert "apptoken" not in message


async def test_unknown_reachable_scenes_are_skipped(dss, client):
    dss.reachable_scenes = [0, 5, 13, 200]

    await client.initialize()

    light_scenes = sorted(k for k in client.get_scenes() if k.startswith("0_1_"))
    assert light_scenes == ["0_1_0", "0_1_5"]


async def test_command_stack_survives_failing_command(dss, client):
    dss.fail_scene_calls = 1  # first command is rejected by the server

    await client.stack.start()
    for scene in (1, 2, 3):
        await client.stack.append(f"/json/zone/callScene?id=0&sceneNumber={scene}")
    for _ in range(100):
        if len(dss.scene_calls) == 3:
            break
        await asyncio.sleep(0.05)
    await client.stack.stop()

    assert dss.scene_calls == ["1", "2", "3"]


async def test_command_stack_stop_before_start_is_safe(client):
    await client.stack.stop()


async def test_websocket_reconnects_and_isolates_callbacks(
    dss, client, monkeypatch
):
    monkeypatch.setattr(websocket, "RECONNECT_MIN_DELAY", 0.01)
    received = []

    async def failing_callback(event):
        raise RuntimeError("broken subscriber")

    async def collecting_callback(event):
        received.append(event["properties"]["connection"])

    listener = DSWebsocketEventListener(client, event_name="callScene")
    listener.register(failing_callback)
    listener.register(collecting_callback)

    task = asyncio.create_task(listener.start())
    try:
        for _ in range(100):
            if len(received) >= 3:
                break
            await asyncio.sleep(0.05)
    finally:
        await listener.stop()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # one event per connection, the server drops the connection every time
    assert received[:3] == [1, 2, 3]
