"""Config flow to configure the digitalSTROM component."""
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ALIAS,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .pydigitalstrom.apptokenhandler import DSAppTokenHandler
from .pydigitalstrom.client import DSClient
from .pydigitalstrom.exceptions import DSAuthenticationException, DSException

from .const import (
    DOMAIN,
    CONF_DELAY,
    DEFAULT_ALIAS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    MAX_DELAY,
    MAX_SCAN_INTERVAL,
    MIN_DELAY,
    MIN_SCAN_INTERVAL,
    TITLE_FORMAT,
)
from .util import get_option, get_session, slugify_entry

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
DELAY_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=MIN_DELAY, max=MAX_DELAY))
SCAN_INTERVAL_VALIDATOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
)


def _error_key(err: DSException) -> str:
    if isinstance(err, DSAuthenticationException):
        return "invalid_auth"
    return "cannot_connect"


class DigitalStromConfigFlow(ConfigFlow, domain=DOMAIN):
    """handle a digitalSTROM config flow"""

    VERSION = 1

    def __init__(self) -> None:
        # new host, port and name while reconfiguring
        self._reconfigure_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "DigitalStromOptionsFlow":
        return DigitalStromOptionsFlow()

    async def _async_request_token(
        self, host: str, port: int, username: str, password: str
    ) -> str:
        """get an app token from the server and register it"""
        handler = DSAppTokenHandler(
            host=host,
            port=port,
            username=username,
            password=password,
            session=get_session(self.hass),
        )
        return await handler.request_apptoken()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """handle the start of the config flow"""
        errors = {}

        if user_input is not None:
            # check if server is already known
            await self.async_set_unique_id(
                slugify_entry(host=user_input[CONF_HOST], port=user_input[CONF_PORT])
            )
            self._abort_if_unique_id_configured()

            try:
                token = await self._async_request_token(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except DSException as err:
                errors["base"] = _error_key(err)
            else:
                return self.async_create_entry(
                    title=TITLE_FORMAT.format(
                        alias=user_input[CONF_ALIAS],
                        host=user_input[CONF_HOST],
                        port=user_input[CONF_PORT],
                    ),
                    data={
                        CONF_TOKEN: token,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_ALIAS: user_input[CONF_ALIAS],
                        CONF_DELAY: user_input[CONF_DELAY],
                    },
                )

        defaults = user_input or {
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "",
            CONF_ALIAS: DEFAULT_ALIAS,
            CONF_DELAY: DEFAULT_DELAY,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=defaults[CONF_PORT]): int,
                    vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
                    vol.Required(
                        CONF_PASSWORD, default=defaults[CONF_PASSWORD]
                    ): PASSWORD_SELECTOR,
                    vol.Required(CONF_ALIAS, default=defaults[CONF_ALIAS]): str,
                    vol.Required(CONF_DELAY, default=defaults[CONF_DELAY]): DELAY_VALIDATOR,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """the app token is missing or was rejected by the server"""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """ask for the credentials again and request a new app token"""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            try:
                token = await self._async_request_token(
                    host=entry.data[CONF_HOST],
                    port=entry.data[CONF_PORT],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except DSException as err:
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
                }
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """change host, port or name, e.g. after the server got a new address"""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            host, port = user_input[CONF_HOST], user_input[CONF_PORT]
            unique_id = slugify_entry(host=host, port=port)
            if any(
                other.unique_id == unique_id and other.entry_id != entry.entry_id
                for other in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

            self._reconfigure_data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_ALIAS: user_input[CONF_ALIAS],
            }

            # the token we have is all that is needed if it is the same server
            client = DSClient(
                host=host,
                port=port,
                apptoken=entry.data.get(CONF_TOKEN, ""),
                apartment_name=user_input[CONF_ALIAS],
                session=get_session(self.hass),
            )
            try:
                await client.get_session_token()
            except DSAuthenticationException:
                # a different server doesn't know our token, get a new one
                return await self.async_step_reconfigure_credentials()
            except DSException:
                errors["base"] = "cannot_connect"
            else:
                return self._async_finish_reconfigure(entry)

        defaults = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=defaults[CONF_PORT]): int,
                    vol.Required(CONF_ALIAS, default=defaults[CONF_ALIAS]): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """the new address doesn't accept our token, request a new one"""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            try:
                token = await self._async_request_token(
                    host=self._reconfigure_data[CONF_HOST],
                    port=self._reconfigure_data[CONF_PORT],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except DSException as err:
                errors["base"] = _error_key(err)
            else:
                return self._async_finish_reconfigure(entry, token)

        return self.async_show_form(
            step_id="reconfigure_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
                }
            ),
            description_placeholders={"host": self._reconfigure_data[CONF_HOST]},
            errors=errors,
        )

    def _async_finish_reconfigure(
        self, entry: ConfigEntry, token: str | None = None
    ) -> ConfigFlowResult:
        data = dict(self._reconfigure_data)
        if token:
            data[CONF_TOKEN] = token
        return self.async_update_reload_and_abort(
            entry,
            unique_id=slugify_entry(host=data[CONF_HOST], port=data[CONF_PORT]),
            title=TITLE_FORMAT.format(
                alias=data[CONF_ALIAS], host=data[CONF_HOST], port=data[CONF_PORT]
            ),
            data_updates=data,
        )


class DigitalStromOptionsFlow(OptionsFlow):
    """handle the options of a digitalSTROM server"""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DELAY,
                        default=get_option(self.config_entry, CONF_DELAY, DEFAULT_DELAY),
                    ): DELAY_VALIDATOR,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=get_option(
                            self.config_entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): SCAN_INTERVAL_VALIDATOR,
                }
            ),
        )
