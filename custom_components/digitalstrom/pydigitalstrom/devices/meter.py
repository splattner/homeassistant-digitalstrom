# -*- coding: UTF-8 -*-
from ..client import DSClient
from ..devices.base import DSDevice

from ..exceptions import (
    DSException,
    DSCommandFailedException,
    DSRequestException,
)

import logging
_LOGGER = logging.getLogger(__name__)


class DSMeter(DSDevice):
    URL_GET_LATEST_CONSUMPTION= (
        "/json/metering/getLatest?from=.meters({dsid})&type=consumption"
    )

    URL_GET_LATEST_ENERGY= (
        "/json/metering/getLatest?from=.meters({dsid})&type=energy"
    )

    URL_GET_METER_NAME= (
        "/json/property/getString?path=/apartment/dSMeters/{dsuid}/name"
    )

    URL_GET_METER_DSID= (
        "/json/property/getString?path=/apartment/dSMeters/{dsuid}/dSID"
    )

    def __init__(
        self,
        client: DSClient,
        dsuid,
        *args,
        **kwargs
    ):
        self.dsuid = dsuid

        super().__init__(
            client=client, device_id="", device_name="", *args, **kwargs
        )

    async def async_init(self):

        response = await self._client.request(url=self.URL_GET_METER_NAME.format(dsuid = self.dsuid))        
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")
        self._name = response["result"]["value"]

        response = await self._client.request(url=self.URL_GET_METER_DSID.format(dsuid = self.dsuid))
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")
        self._id = response["result"]["value"]



    async def get_latest(self):
        response = await self._client.request(
            url=self.URL_GET_LATEST_CONSUMPTION.format(dsid=self._id)
        )
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")

        return response["result"]["values"][0]["value"]

    async def get_latest_energy(self):
        response = await self._client.request(
            url=self.URL_GET_LATEST_ENERGY.format(dsid=self._id)
        )
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")

        return response["result"]["values"][0]["value"]