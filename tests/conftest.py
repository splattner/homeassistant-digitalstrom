"""Shared fixtures.

The tests deliberately do not need Home Assistant installed: the few
homeassistant modules the integration imports are replaced by stubs, which is
enough to test the pydigitalstrom library against a fake dSS and the entity
logic in isolation.
"""
import shutil
import ssl
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HA_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.light",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.restore_state",
    "homeassistant.helpers.typing",
    "homeassistant.util",
]


class StubEntity:
    """Stands in for RestoreEntity / LightEntity base classes."""

    def __init__(self, *args, **kwargs):
        self.state_writes = 0

    def async_write_ha_state(self):
        self.state_writes += 1

    async def async_added_to_hass(self):
        pass

    async def async_get_last_state(self):
        return None


class StubLightEntity:
    pass


def _install_homeassistant_stubs():
    for name in HA_MODULES:
        sys.modules[name] = MagicMock()
    sys.modules["homeassistant.components.light"].LightEntity = StubLightEntity
    sys.modules["homeassistant.components.light"].ATTR_EFFECT = "effect"
    sys.modules["homeassistant.helpers.restore_state"].RestoreEntity = StubEntity
    sys.modules["homeassistant.const"].CONF_HOST = "host"
    sys.modules["homeassistant.const"].CONF_PORT = "port"
    sys.modules["homeassistant.const"].STATE_ON = "on"
    sys.modules["homeassistant.util"].slugify = lambda value: value


_install_homeassistant_stubs()


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
        self.login_params = None
        self.scene_calls = []
        self.fail_scene_calls = 0
        self.ws_connections = 0
        self.reachable_scenes = [0, 5]

    @staticmethod
    def _ok(result=None):
        return web.json_response({"ok": True, "result": result})

    def _handler(self, result):
        """async handler answering with a fixed (or lazily computed) result"""

        async def handler(request):
            return self._ok(result() if callable(result) else result)

        return handler

    async def _login(self, request):
        self.login_params = dict(request.query)
        return self._ok({"token": "temptoken"})

    async def _call_scene(self, request):
        self.scene_calls.append(request.query["sceneNumber"])
        if self.fail_scene_calls > 0:
            self.fail_scene_calls -= 1
            return web.json_response({"ok": False, "message": "failed"})
        return self._ok()

    async def _websocket(self, request):
        """send one event and drop the connection, clients have to reconnect"""
        self.ws_connections += 1
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        await socket.send_json(
            {"name": "callScene", "properties": {"connection": self.ws_connections}}
        )
        await socket.close()
        return socket

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get(
            "/json/system/requestApplicationToken",
            self._handler({"applicationToken": "apptoken"}),
        )
        app.router.add_get("/json/system/login", self._login)
        app.router.add_get("/json/system/enableToken", self._handler(None))
        app.router.add_get(
            "/json/system/loginApplication",
            self._handler({"token": "sessiontoken"}),
        )
        app.router.add_get(
            "/json/property/query2",
            self._handler(
                {
                    "zone0": {
                        "name": "",
                        "ZoneID": 0,
                        "group1": {"group": 1, "color": 1},
                    }
                }
            ),
        )
        app.router.add_get(
            "/json/zone/getReachableScenes",
            self._handler(lambda: {"reachableScenes": self.reachable_scenes}),
        )
        app.router.add_get("/json/property/getChildren", self._handler([]))
        app.router.add_get("/json/zone/callScene", self._call_scene)
        app.router.add_get("/websocket", self._websocket)
        return app


@pytest_asyncio.fixture
async def dss(ssl_context):
    server = FakeDSS()
    runner = web.AppRunner(server.app())
    await runner.setup()
    site = web.TCPSite(runner, server.host, 0, ssl_context=ssl_context)
    await site.start()
    server.port = runner.addresses[0][1]
    yield server
    await runner.cleanup()
