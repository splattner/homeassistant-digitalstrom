"""Shared fixtures: a fake digitalSTROM server and helpers to set up the integration."""
import asyncio
import shutil
import ssl
import subprocess

import pytest
import pytest_asyncio
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.digitalstrom.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """load the integration from custom_components"""


@pytest.fixture(scope="session")
def ssl_context(tmp_path_factory) -> ssl.SSLContext:
    """server side tls context with a throw-away self-signed certificate"""
    if not shutil.which("openssl"):
        pytest.skip("openssl is needed to create a test certificate")
    directory = tmp_path_factory.mktemp("cert")
    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context


class FakeDSS:
    """minimal digitalSTROM server, records what clients send"""

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = None

        # behaviour
        self.app_token = "apptoken"
        self.reachable_scenes = [0, 5]
        self.meters = []  # dSUIDs
        self.reject_login = False  # wrong username / password
        self.reject_app_token = False  # revoked app token
        self.fail_enable_token = False
        self.http_status = None  # answer every json request with this status
        self.fail_requests = 0  # answer this many json requests with status 500
        self.invalid_api_response = False  # ok, but without the expected result
        self.fail_scene_calls = 0
        # "drop": send one event and close, clients have to reconnect
        # "hold": keep the connection open, use push_event
        self.ws_mode = "drop"

        # recordings
        self.login_params = None
        self.scene_calls = []
        self.ws_connections = 0
        self.ws_cookies = []
        self._sockets = []

    @staticmethod
    def _ok(result=None):
        return web.json_response({"ok": True, "result": result})

    @staticmethod
    def _failed(message):
        return web.json_response({"ok": False, "message": message})

    def _handler(self, result):
        """async handler answering with a fixed (or lazily computed) result"""

        async def handler(request):
            return self._ok(result() if callable(result) else result)

        return handler

    @web.middleware
    async def _middleware(self, request, handler):
        if request.path.startswith("/json/"):
            if self.http_status:
                return web.Response(status=self.http_status, text="server error")
            if self.fail_requests > 0:
                self.fail_requests -= 1
                return web.Response(status=500, text="server error")
        return await handler(request)

    async def _request_application_token(self, request):
        if self.invalid_api_response:
            return self._ok({})
        return self._ok({"applicationToken": self.app_token})

    async def _login(self, request):
        self.login_params = dict(request.query)
        if self.reject_login:
            return self._failed("Authentication failed")
        return self._ok({"token": "temptoken"})

    async def _enable_token(self, request):
        if self.fail_enable_token:
            return self._failed("invalid token")
        return self._ok()

    async def _login_application(self, request):
        if self.invalid_api_response:
            return self._ok({})
        if self.reject_app_token:
            return self._failed("Application-Authentication failed")
        return self._ok({"token": "sessiontoken"})

    async def _call_scene(self, request):
        self.scene_calls.append(request.query["sceneNumber"])
        if self.fail_scene_calls > 0:
            self.fail_scene_calls -= 1
            return self._failed("failed")
        return self._ok()

    async def _error(self, request):
        return web.Response(status=500, text="kaboom")

    async def _bad_json(self, request):
        return web.Response(content_type="application/json", text="{not json")

    async def _slow(self, request):
        await asyncio.sleep(0.5)
        return self._ok()

    async def _meter_children(self, request):
        return self._ok([{"name": dsuid} for dsuid in self.meters])

    async def _meter_property(self, request):
        # /apartment/dSMeters/<dsuid>/<name|dSID>
        _, _, _, dsuid, prop = request.query["path"].split("/")
        return self._ok({"value": f"Meter {dsuid}" if prop == "name" else f"dsid-{dsuid}"})

    async def _metering(self, request):
        value = 1500.0 if request.query["type"] == "energy" else 42.0
        return self._ok({"values": [{"value": value}]})

    async def _websocket(self, request):
        self.ws_connections += 1
        self.ws_cookies.append(request.headers.get("Cookie"))
        socket = web.WebSocketResponse()
        await socket.prepare(request)

        if self.ws_mode == "drop":
            await socket.send_json(
                {"name": "callScene", "properties": {"connection": self.ws_connections}}
            )
            await socket.close()
            return socket

        self._sockets.append(socket)
        try:
            async for _ in socket:
                pass
        finally:
            self._sockets.remove(socket)
        return socket

    async def push_event(self, event: dict) -> None:
        """send an event to all connected websocket clients"""
        for socket in list(self._sockets):
            await socket.send_json(event)

    async def push_raw(self, data: str | bytes) -> None:
        """send something that is not a json event"""
        for socket in list(self._sockets):
            if isinstance(data, bytes):
                await socket.send_bytes(data)
            else:
                await socket.send_str(data)

    async def push_scene(self, zone_id: int, group_id: int, scene_id: int) -> None:
        await self.push_event(
            {
                "name": "callScene",
                "properties": {
                    "zoneID": str(zone_id),
                    "groupID": str(group_id),
                    "sceneID": str(scene_id),
                },
            }
        )

    async def close_sockets(self) -> None:
        for socket in list(self._sockets):
            await socket.close()

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._middleware])
        get = app.router.add_get
        get("/json/system/requestApplicationToken", self._request_application_token)
        get("/json/system/login", self._login)
        get("/json/system/enableToken", self._enable_token)
        get("/json/system/loginApplication", self._login_application)
        get(
            "/json/property/query2",
            self._handler(
                {
                    "zone0": {
                        "name": "",
                        "ZoneID": 0,
                        "group1": {
                            "group": 1,
                            "color": 1,
                            "scene0": {"scene": 40, "name": "Movie Night"},
                        },
                    }
                }
            ),
        )
        get(
            "/json/zone/getReachableScenes",
            self._handler(lambda: {"reachableScenes": self.reachable_scenes}),
        )
        get("/json/property/getChildren", self._meter_children)
        get("/json/property/getString", self._meter_property)
        get("/json/metering/getLatest", self._metering)
        get("/json/zone/callScene", self._call_scene)
        get("/json/test/error", self._error)
        get("/json/test/bad_json", self._bad_json)
        get("/json/test/slow", self._slow)
        get("/websocket", self._websocket)
        return app


@pytest_asyncio.fixture
async def dss(ssl_context, socket_enabled):
    server = FakeDSS()
    runner = web.AppRunner(server.app())
    await runner.setup()
    site = web.TCPSite(runner, server.host, 0, ssl_context=ssl_context)
    await site.start()
    server.port = runner.addresses[0][1]
    yield server
    await server.close_sockets()
    await runner.cleanup()


def make_entry(dss: FakeDSS, **overrides) -> MockConfigEntry:
    data = {
        "host": dss.host,
        "port": dss.port,
        "token": "apptoken",
        "alias": "Apartment",
        "delay": 10,
    }
    data.update(overrides)
    return MockConfigEntry(
        domain=DOMAIN, data={k: v for k, v in data.items() if v is not None}
    )


@pytest_asyncio.fixture
async def setup_entry(hass, dss):
    """set up the integration against the fake dSS, unload it after the test"""
    entries = []

    async def setup(**overrides) -> MockConfigEntry:
        dss.ws_mode = "hold"
        entry = make_entry(dss, **overrides)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entries.append(entry)
        return entry

    yield setup

    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def wait_for(predicate, timeout: float = 5.0) -> None:
    """wait for something that happens in a background task"""
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)
