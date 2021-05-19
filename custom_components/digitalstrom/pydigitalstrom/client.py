# -*- coding: UTF-8 -*-
import time
import logging

import aiohttp
import asyncio

from .constants import SCENES, ALL_SCENES_BYNAME, ALL_SCENES_BYID
from .exceptions import (
    DSException,
    DSCommandFailedException,
    DSRequestException,
)
from .requesthandler import DSRequestHandler

_LOGGER = logging.getLogger(__name__)


class DSClient(DSRequestHandler):
    URL_SCENES = (
        "/json/property/query2?query=/apartment/zones/*(*)/" "groups/*(*)"
    )
    URL_REACHABLE_SCENES = "json/zone/getReachableScenes?id={zoneId}&groupID={groupId}"
    URL_SCENE_GETNAME = "json/zone/sceneGetName?id={zoneId}&groupID={groupId}&sceneNumber={scene}"

    URL_EVENT_SUBSCRIBE = "/json/event/subscribe?name={name}&" "subscriptionID={id}"
    URL_EVENT_UNSUBSCRIBE = "/json/event/unsubscribe?name={name}&" "subscriptionID={id}"
    URL_EVENT_POLL = "/json/event/get?subscriptionID={id}&timeout={timeout}"

    URL_SESSIONTOKEN = "/json/system/loginApplication?loginToken={apptoken}"

    def __init__(
        self,
        host: str,
        port: int,
        apptoken: str,
        apartment_name: str,
        stack_delay: int = 500,
        loop: asyncio.AbstractEventLoop = None,
    ):
        self._apptoken = apptoken
        self._apartment_name = apartment_name

        self._last_request = None
        self._session_token = None
        self._scenes = dict()

        from .commandstack import DSCommandStack

        self.stack = DSCommandStack(client=self, delay=stack_delay)

        super().__init__(host=host, port=port, loop=loop)

    async def request(self, url: str, **kwargs):
        """
        run an authenticated request against the digitalstrom server

        :param str url:
        :return:
        """
        # get a session id, they time out 60 seconds after the last request,
        # we go for 50 to be secure
        if not self._last_request or self._last_request < time.time() - 50:
            self._session_token = await self.get_session_token()

        # update last request timestamp and call api
        self._last_request = time.time()
        data = await self.raw_request(
            url=url, params=dict(token=self._session_token), **kwargs
        )
        return data

    async def get_session_token(self):
        data = await self.raw_request(
            self.URL_SESSIONTOKEN.format(apptoken=self._apptoken)
        )
        if "result" not in data or "token" not in data["result"]:
            raise DSException("invalid api response")
        return data["result"]["token"]

    async def initialize(self):
        from .devices.scene import DSScene, DSColorScene

        # get scenes
        response = await self.request(url=self.URL_SCENES)
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")
        result = response["result"]

        # set name for apartment zone
        if "zone0" in result and "name" in result["zone0"]:
            result["zone0"]["name"] = self._apartment_name

        # create scene objects
        for zone in result.values():
            # skip unnamed zones
            if not zone["name"]:
                continue

            zone_id = zone["ZoneID"]
            zone_name = zone["name"]

            _LOGGER.debug("Zone {zone_name}".format(zone_name=zone_name))

            # add generic zone scenes
            _LOGGER.debug("adding generic scenes")
            for scene_name, scene_id in SCENES["GROUP_INDIPENDENT"].items():
                id = "{zone_id}_{scene_id}".format(zone_id=zone_id, scene_id=scene_id)
                
                _LOGGER.debug("adding DSScene for {id} Zone Name {zone_name}".format(id=id, zone_name=zone_name))
                self._scenes[id] = DSScene(
                    client=self,
                    zone_id=zone_id,
                    zone_name=zone_name,
                    scene_id=scene_id,
                    scene_name=scene_name,
                )

            # add reachable scenes and custom named scenes (?)
            for zone_key, zone_value in zone.items():
                # we're only interested in groups
                if not str(zone_key).startswith("group"):
                    continue

                # remember the color
                color = zone_value["color"]

                _LOGGER.debug("Group Color: {color}".format(color=color))

                # get reachable scenes
                response = await self.request(url=self.URL_REACHABLE_SCENES.format(zoneId=zone_id, groupId=color))
                if "result" not in response:
                    raise DSCommandFailedException("no result in server response")
                result = response["result"]

                _LOGGER.debug("adding reachable scenes")
                for reachable_scene in result["reachableScenes"]:
                    scene_id = reachable_scene
                    scene_name = ALL_SCENES_BYID[scene_id]

                    id = "{zone_id}_{color}_{scene_id}".format(
                        zone_id=zone_id, color=color, scene_id=scene_id
                    )

                    _LOGGER.debug("adding DSColorScene for reachable scene {id}".format(id=id))
                    self._scenes[id] = DSColorScene(
                        client=self,
                        zone_id=zone_id,
                        zone_name=zone_name,
                        scene_id=scene_id,
                        scene_name=scene_name,
                        color=color,
                    )

    
                # get custom named scenes
                _LOGGER.debug("adding custom named scenes")
                for group_key, group_value in zone_value.items():
                    # we're only interested in scenes
                    if not str(group_key).startswith("scene"):
                        continue

                    scene_id = group_value["scene"]
                    scene_name = group_value["name"]
                    id = "{zone_id}_{color}_{scene_id}".format(
                        zone_id=zone_id, color=color, scene_id=scene_id
                    )
                    _LOGGER.debug("adding DSColorScene for custom named scene {id}".format(id=id))
                    self._scenes[id] = DSColorScene(
                        client=self,
                        zone_id=zone_id,
                        zone_name=zone_name,
                        scene_id=scene_id,
                        scene_name=scene_name,
                        color=color,
                    )

    def get_scenes(self):
        return self._scenes
