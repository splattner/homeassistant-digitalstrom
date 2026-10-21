import aiohttp
import asyncio

from .requesthandler import DSRequestHandler
from .exceptions import DSException


class DSAppTokenHandler(DSRequestHandler):
    URL_APPTOKEN = (
        "/json/system/requestApplicationToken?applicationName=" "homeassistant"
    )
    URL_TEMPTOKEN = "/json/system/login"
    URL_ACTIVATE = "/json/system/enableToken"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        self.username = username
        self.password = password

        super().__init__(host=host, port=port, loop=loop)

    async def request_apptoken(self) -> str:
        """
        request a new app token from the server

        :raises: DSException if the token could not be requested or activated
        """
        # get fresh app token and activate it
        apptoken = await self.get_application_token_from_server()
        temptoken = await self.get_temp_token()
        await self.activate_application_token(apptoken=apptoken, temptoken=temptoken)
        return apptoken

    async def get_application_token_from_server(self) -> str:
        """
        request a fresh non-activated app token from the server
        """
        data = await self.raw_request(self.URL_APPTOKEN)
        if "result" not in data or "applicationToken" not in data["result"]:
            raise DSException("invalid api response")
        return data["result"]["applicationToken"]

    async def get_temp_token(self) -> str:
        """
        get an authenticated temp token
        """
        # pass credentials as params so they get url-encoded
        data = await self.raw_request(
            self.URL_TEMPTOKEN,
            params=dict(user=self.username, password=self.password),
        )
        if "result" not in data or "token" not in data["result"]:
            raise DSException("invalid api response")
        return data["result"]["token"]

    async def activate_application_token(self, apptoken, temptoken) -> None:
        """
        activate our app token using the authenticated temp token

        :raises: DSCommandFailedException if the server rejects the activation
        """
        await self.raw_request(
            self.URL_ACTIVATE,
            params=dict(applicationToken=apptoken, token=temptoken),
        )
