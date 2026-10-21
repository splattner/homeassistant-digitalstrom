import aiohttp
import asyncio
import json
import logging
import time

from .client import DSClient

_LOGGER = logging.getLogger(__name__)

RECONNECT_MIN_DELAY = 1
RECONNECT_MAX_DELAY = 60


class DSWebsocketEventListener:
    def __init__(self, client: DSClient, event_name: str):
        self._client = client
        self._event_name = event_name
        self._callbacks = []

        self._ws = None
        self._running = False
        self._last_keepalive = None

    def register(self, callback: callable):
        self._callbacks.append(callback)

    async def _get_cookie(self):
        return dict(token=await self._client.get_session_token())

    async def start(self):
        """
        listen for events and reconnect with backoff until stop() is called
        """
        _LOGGER.debug("DSWebsocketEventListener start")
        self._running = True
        delay = RECONNECT_MIN_DELAY

        while self._running:
            try:
                if await self._listen():
                    delay = RECONNECT_MIN_DELAY
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.warning("DS websocket failed: %s", err)

            if not self._running:
                break

            _LOGGER.debug("DS websocket reconnecting in %s seconds", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _listen(self) -> bool:
        """
        connect and handle messages until the connection is closed

        :return: True if a connection was established
        """
        session = await self._client.get_aiohttp_session(
            cookies=await self._get_cookie()
        )
        url = f"wss://{self._client.host}:{self._client.port}/websocket"

        try:
            async with session.ws_connect(url=url) as ws:
                self._ws = ws
                _LOGGER.debug("WS connected")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            event = json.loads(msg.data)
                        except json.JSONDecodeError:
                            _LOGGER.warning("DS websocket got invalid json: %s", msg.data)
                            continue
                        await self._handle_event(event=event)
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        _LOGGER.warning("DS websocket closed or error: %s", msg)
                        break
                    else:
                        _LOGGER.warning("DS websocket got unknown message: %s", msg)
        finally:
            self._ws = None
            await session.close()

        return True

    async def stop(self):
        self._running = False
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def _handle_event(self, event: dict):
        _LOGGER.debug("WS Event %s", event)

        if "name" not in event:
            return

        if event["name"] == "keepWebserviceAlive":
            self._last_keepalive = time.time() * 1000.0

        # subscribed event
        if event["name"] == self._event_name:
            for callback in self._callbacks:
                # one broken subscriber must not stop the others or the listener
                try:
                    await callback(event=event)
                except Exception:
                    _LOGGER.exception("Error in DS websocket event callback")
