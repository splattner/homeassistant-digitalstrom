import json
import logging
from contextlib import asynccontextmanager

import aiohttp
import asyncio
import socket
from .exceptions import DSCommandFailedException, DSRequestException

_LOGGER = logging.getLogger(__name__)

# a dSS that doesn't answer must not block callers (and the command stack) forever
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class DSRequestHandler:
    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession = None,
    ):
        """
        :param session: an optional shared session that stays owned by the
            caller. Without one, a short-lived session (that doesn't verify
            ssl certificates) is created per request.
        """
        self.host = host
        self.port = port
        self._session = session

    @asynccontextmanager
    async def session_scope(self):
        """
        yield the shared session, or a temporary one that is closed afterwards
        """
        if self._session is not None:
            yield self._session
            return

        session = await self.get_aiohttp_session()
        try:
            yield session
        finally:
            await session.close()

    async def raw_request(self, url: str, retries : int = 2, interval = 0.9, backoff = 3, **kwargs) -> str:
        """
        run a raw request against the digitalstrom server

        :param url: URL path to request
        :param kwargs: kwargs to be forwarded to aiohttp.get
        :return: json response
        :raises: DSRequestException
        :raises: DSCommandFailedException
        """
        url = f"https://{self.host}:{self.port}{url}"
        # the query string can contain passwords and tokens, never log it
        log_url = url.split("?", 1)[0]

        if retries == -1:  # -1 means retry indefinitely
            attempt = -1
        elif retries == 0: # Zero means don't retry
            attempt = 1
        else:  # any other value means retry N times
            attempt = retries + 1

        kwargs.setdefault("timeout", REQUEST_TIMEOUT)

        backoff_interval = interval
        raised_exc = None

        while attempt != 0:

            if raised_exc:
                _LOGGER.debug('caught "%s" url:%s , remaining tries %s, '
                    'sleeping %.2fsecs', raised_exc, log_url,
                    attempt, backoff_interval)
                await asyncio.sleep(backoff_interval)
                # bump interval for the next possible attempt
                backoff_interval = backoff_interval * backoff

            _LOGGER.debug("Raw Request to {url}, remaining attempts {attempt} of {retries}".format(url = log_url, attempt = attempt - 1, retries = retries))

            async with self.session_scope() as session:
                try:
                    async with session.get(url=url, **kwargs) as response:
                        # check for server errors
                        if not response.status == 200:
                            raise DSRequestException(await response.text())

                        try:
                            data = await response.json()
                        except json.decoder.JSONDecodeError:
                            raise DSRequestException("failed to json decode response")
                        if "ok" not in data or not data["ok"]:
                            raise DSCommandFailedException(
                                "{path}: {message}".format(
                                    path=log_url.split("/", 3)[-1],
                                    message=data.get("message", "request failed"),
                                )
                            )
                        return data
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # Only retry on these Errors
                    raised_exc = DSRequestException("request failed")

            attempt -= 1

        if raised_exc:
            raise raised_exc

    async def get_aiohttp_session(self) -> aiohttp.ClientSession:
        """
        create a standalone session, ssl verification is turned off since
        most digitalstrom servers use self-signed certificates

        :return the initialized aiohttp client session
        """
        return aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(family=socket.AF_INET, ssl=False),
        )
