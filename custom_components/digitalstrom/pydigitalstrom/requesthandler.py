import json
import logging

import aiohttp
import asyncio
import socket
from .exceptions import DSCommandFailedException, DSRequestException

_LOGGER = logging.getLogger(__name__)


class DSRequestHandler:
    def __init__(self, host: str, port: str, loop: asyncio.AbstractEventLoop = None):
        self.host = host
        self.port = port
        self.loop = loop

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

        if retries == -1:  # -1 means retry indefinitely
            attempt = -1
        elif retries == 0: # Zero means don't retry
            attempt = 1
        else:  # any other value means retry N times
            attempt = retries + 1

        backoff_interval = interval
        raised_exc = None

        while attempt != 0:

            if raised_exc:
                _LOGGER.debug('caught "%s" url:%s , remaining tries %s, '
                    'sleeping %.2fsecs', raised_exc, url,
                    attempt, backoff_interval)
                await asyncio.sleep(backoff_interval)
                # bump interval for the next possible attempt
                backoff_interval = backoff_interval * backoff

            _LOGGER.debug("Raw Request to {url}, remaining attempts {attempt} of {retries}".format(url = url, attempt = attempt - 1, retries = retries))

            # disable ssl verification for most servers miss valid certificates
            async with await self.get_aiohttp_session() as session:
                try:
                    async with session.get(url=url, **kwargs) as response:
                        # check for server errors
                        if not response.status == 200:
                            raise DSRequestException(response.text)

                        try:
                            data = await response.json()
                        except json.decoder.JSONDecodeError:
                            raise DSRequestException("failed to json decode response")
                        if "ok" not in data or not data["ok"]:
                            raise DSCommandFailedException()
                        return data
                except aiohttp.ClientError:
                    # Only retry on this Error
                    raised_exc = DSRequestException("request failed")

            attempt -= 1

        if raised_exc:
            raise raised_exc

    async def get_aiohttp_session(self, cookies: dict = None) -> aiohttp.ClientSession:
        """
        turn off ssl verification since most digitalstrom servers use
        self-signed certificates

        :param cookies: a dict of cookies to set on the connection
        :return the initialized aiohttp client session
        """
        return aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(family=socket.AF_INET, ssl=False),
            cookies=cookies,
            loop=self.loop,
        )
