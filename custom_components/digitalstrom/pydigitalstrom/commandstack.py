import asyncio
import logging

from .client import DSClient


_LOGGER = logging.getLogger(__name__)

class DSCommandStack:
    def __init__(self, client: DSClient, delay: int = 500):
        self._client = client
        self._stack = list()
        self._task = None
        self._delay = delay

    async def append(self, url: str):
        self._stack.append(url)

    async def execute(self):
        while True:
            # check for command to execute
            if len(self._stack) > 0:
                url = self._stack.pop(0)
                _LOGGER.debug("Command Stack not empty, executing next request")
                try:
                    await self._client.request(url=url)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    # a failing command must never stop the stack, otherwise
                    # all following commands would be silently dropped
                    _LOGGER.error("Command %s failed: %s", url, err)

            # sleep for x ms before next execution to not overload the DS server
            await asyncio.sleep(self._delay / 1000)

    async def start(self):
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self.execute())

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None
