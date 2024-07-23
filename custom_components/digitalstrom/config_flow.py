"""Config flow to configure the digitalSTROM component."""
from urllib.parse import urlparse
import voluptuous as vol

from homeassistant import config_entries

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ALIAS,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation

from .const import (
    DOMAIN,
    HOST_FORMAT,
    DIGITALSTROM_MANUFACTURERS,
    CONF_DELAY,
    DEFAULT_ALIAS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_DELAY,
    DEFAULT_USERNAME,
    TITLE_FORMAT,
)
from .util import slugify_entry


@callback
def configured_devices(hass):
    """return a set of all configured instances"""
    configuered_devices = list()
    for entry in hass.config_entries.async_entries(DOMAIN):
        configuered_devices.append(
            slugify_entry(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
        )
    return configuered_devices


@callback
def initialized_devices(hass):
    """return a set of all initialized instances"""
    initialized_devices = list()
    for slug in hass.data.get(DOMAIN, {}).keys():
        initialized_devices.append(slug)
    return initialized_devices


class DigitalStromConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """handle a digitalSTROM config flow"""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    discovered_devices = []

    def __init__(self, *args, **kwargs):
        self.device_config = {
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "",
            CONF_ALIAS: DEFAULT_ALIAS,
            CONF_DELAY: DEFAULT_DELAY,
        }
        super().__init__(*args, **kwargs)

    async def async_step_user(self, user_input=None):
        """handle the start of the config flow"""
        errors = {}

        # validate input
        if user_input is not None:
            from .pydigitalstrom.apptokenhandler import DSAppTokenHandler
            from .pydigitalstrom.exceptions import DSException

            # build client config
            self.device_config = user_input.copy()

            # get device identifier slug
            device_slug = slugify_entry(
                host=self.device_config[CONF_HOST], port=self.device_config[CONF_PORT]
            )

            # check if server is already known
            if device_slug in configured_devices(self.hass):
                errors["base"] = "already_configured"
            else:
                # try to get an app token from the server and register it
                handler = DSAppTokenHandler(
                    host=self.device_config[CONF_HOST],
                    port=self.device_config[CONF_PORT],
                    username=self.device_config[CONF_USERNAME],
                    password=self.device_config[CONF_PASSWORD],
                )
                try:
                    token = await handler.request_apptoken()
                except DSException:
                    errors["base"] = "communication_error"
                else:
                    return self.async_create_entry(
                        title=TITLE_FORMAT.format(
                            alias=self.device_config[CONF_ALIAS],
                            host=self.device_config[CONF_HOST],
                            port=self.device_config[CONF_PORT],
                        ),
                        data={
                            CONF_TOKEN: token,
                            CONF_HOST: self.device_config[CONF_HOST],
                            CONF_PORT: self.device_config[CONF_PORT],
                            CONF_ALIAS: self.device_config[CONF_ALIAS],
                            CONF_DELAY: self.device_config[CONF_DELAY],
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.device_config[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=self.device_config[CONF_PORT]): int,
                    vol.Required(
                        CONF_USERNAME, default=self.device_config[CONF_USERNAME]
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=self.device_config[CONF_PASSWORD]
                    ): str,
                    vol.Required(
                        CONF_ALIAS, default=self.device_config[CONF_ALIAS]
                    ): str,
                    vol.Required(
                        CONF_DELAY, default=self.device_config[CONF_DELAY]
                    ): int,
                }
            ),
            errors=errors,
        )
