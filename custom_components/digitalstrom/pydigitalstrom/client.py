# -*- coding: UTF-8 -*-
import time
import logging

import aiohttp

from .constants import GROUP_LIGHTS, SCENES, ALL_SCENES_BYID
from .exceptions import (
    DSAuthenticationException,
    DSException,
    DSCommandFailedException,
)
from .requesthandler import DSRequestHandler

_LOGGER = logging.getLogger(__name__)


class DSClient(DSRequestHandler):
    URL_SCENES = (
        "/json/property/query2?query=/apartment/zones/*(*)/" "groups/*(*)"
    )
    URL_REACHABLE_SCENES = "/json/zone/getReachableScenes?id={zoneId}&groupID={groupId}"
    URL_SCENE_GETNAME = "/json/zone/sceneGetName?id={zoneId}&groupID={groupId}&sceneNumber={scene}"

    URL_LAST_CALLED_SCENE = "/json/zone/getLastCalledScene?id={zoneId}"
    URL_LAST_CALLED_SCENE_GROUP = (
        "/json/zone/getLastCalledScene?id={zoneId}&groupID={groupId}"
    )

    URL_SESSIONTOKEN = "/json/system/loginApplication?loginToken={apptoken}"

    URL_METERS = "/json/property/getChildren?path=/apartment/dSMeters/"
    URL_METERING_LATEST = "/json/metering/getLatest?from=.meters({dsids})&type={type}"

    def __init__(
        self,
        host: str,
        port: int,
        apptoken: str,
        apartment_name: str,
        stack_delay: int = 500,
        session: aiohttp.ClientSession = None,
    ):
        self._apptoken = apptoken
        self._apartment_name = apartment_name

        self._last_request = None
        self._session_token = None
        self._scenes = dict()
        self._zones = dict()
        self._last_called = dict()
        self._warned_metering_ids = False
        self._meters = dict()

        from .commandstack import DSCommandStack

        self.stack = DSCommandStack(client=self, delay=stack_delay)

        super().__init__(host=host, port=port, session=session)

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
        _LOGGER.debug("Request to {url}".format(url = url))
        self._last_request = time.time()
        data = await self.raw_request(
            url=url, params=dict(token=self._session_token), **kwargs
        )
        return data

    async def get_session_token(self):
        try:
            data = await self.raw_request(
                self.URL_SESSIONTOKEN.format(apptoken=self._apptoken)
            )
        except DSCommandFailedException as err:
            raise DSAuthenticationException("app token rejected by server") from err
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
            self._zones[zone_id] = zone_name

            _LOGGER.debug("Zone ID: {zone_id} Name: {zone_name}".format(zone_id = zone_id, zone_name=zone_name))

            # add generic zone scenes
            _LOGGER.debug("adding generic scenes")
            for scene_name, scene_id in SCENES["GROUP_INDIPENDENT"].items():
                id = "{zone_id}_{scene_id}".format(zone_id=zone_id, scene_id=scene_id)
                
                _LOGGER.debug("adding DSScene Zone Name {zone_name} Scene Name {scene_name}".format(zone_name=zone_name, scene_name=scene_name))
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

                groupId = zone_value["group"]

                # only light group
                if groupId not in [GROUP_LIGHTS]:
                    continue

                # remember the color
                color = zone_value["color"]

                _LOGGER.debug("Group Color: {color}".format(color=color))

                # get reachable scenes
                _LOGGER.debug("Get reachable scenes for Zone {zone_id} / Group {group_id}".format(zone_id=zone_id, group_id=groupId))
                response_rs = await self.request(url=self.URL_REACHABLE_SCENES.format(zoneId=zone_id, groupId=groupId))
                if "result" not in response_rs:
                    raise DSCommandFailedException("no result in server response")
                result_rs = response_rs["result"]

                _LOGGER.debug("adding {count} reachable scenes".format(count=len(result_rs["reachableScenes"])))
                for reachable_scene in result_rs["reachableScenes"]:
                    scene_id = reachable_scene
                    scene_name = ALL_SCENES_BYID.get(scene_id)
                    if scene_name is None:
                        _LOGGER.debug("skipping unknown reachable scene {scene_id}".format(scene_id=scene_id))
                        continue

                    id = "{zone_id}_{color}_{scene_id}".format(
                        zone_id=zone_id, color=color, scene_id=scene_id
                    )

                    _LOGGER.debug("adding DSColorScene for reachable scene {scene_name}".format(scene_name=scene_name))
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
        
        await self._load_last_called_scenes()

        from .devices.meter import DSMeter
        
        # get meters
        response = await self.request(url=self.URL_METERS)
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")
        result = response["result"]

        for meter in result:

            dsuid = meter["name"]
            _LOGGER.debug("adding DSMeter with dSUID{dsuid}".format(dsuid=dsuid))
            dsmeter = DSMeter(client=self, dsuid=dsuid)
            await dsmeter.async_init()
            _LOGGER.debug("Async init done for DSMeter {dsuid}".format(dsuid=dsuid))
            if dsmeter.name == "":
                continue

            self._meters[dsuid] = dsmeter


    async def get_last_called_scene(self, zone_id: int, group_id: int = None):
        """
        ask the server which scene was called last

        :param group_id: group (color) of the scene, none for scenes that
            don't belong to a group like present or sleeping
        :return: scene number, None if the server doesn't know
        """
        if group_id is None:
            url = self.URL_LAST_CALLED_SCENE.format(zoneId=zone_id)
        else:
            url = self.URL_LAST_CALLED_SCENE_GROUP.format(
                zoneId=zone_id, groupId=group_id
            )
        response = await self.request(url=url)
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")

        scene = response["result"].get("scene")
        return None if scene is None else int(scene)

    async def _load_last_called_scenes(self):
        """
        remember the last called scene of all zones and light groups, they are
        the state lights and switches start with
        """
        from .devices.scene import DSScene, DSColorScene

        self._last_called = dict()
        queries = set()
        for scene in self._scenes.values():
            if isinstance(scene, DSColorScene) and scene.color == GROUP_LIGHTS:
                queries.add((scene.zone_id, scene.color))
            elif isinstance(scene, DSScene):
                queries.add((scene.zone_id, None))

        for zone_id, group_id in sorted(queries, key=str):
            try:
                scene_id = await self.get_last_called_scene(zone_id, group_id)
            except DSAuthenticationException:
                raise
            except DSException as err:
                # the state is a nice to have, setup must not depend on it
                _LOGGER.debug(
                    "no last called scene for zone {zone_id} group {group_id}: {err}".format(
                        zone_id=zone_id, group_id=group_id, err=err
                    )
                )
                continue
            if scene_id is not None:
                self._last_called[(zone_id, group_id)] = scene_id

    def get_last_called_scene_at_setup(self, zone_id: int, group_id: int = None):
        """the scene that was called last when the client was initialized"""
        return self._last_called.get((zone_id, group_id))

    def get_scenes(self):
        return self._scenes

    def get_zone_name(self, zone_id: int):
        """name of a zone, None for unknown or unnamed zones"""
        return self._zones.get(zone_id)

    def get_meters(self):
        return self._meters

    # keys that can hold the id of a meter in a metering result, depending on
    # the age of the server dSID is deprecated in favor of dSUID
    METERING_ID_KEYS = ("dSUID", "dsuid", "dsid", "dSID")

    async def get_latest_metering(self, meters: list, metering_type: str) -> dict:
        """
        latest values of several meters with a single request

        :param meters: the meters to read
        :param metering_type: "consumption" (W) or "energy" (Wh)
        :return: value by dSUID of the meter, meters without a value are missing
        """
        response = await self.request(
            url=self.URL_METERING_LATEST.format(
                dsids=",".join(meter.unique_id for meter in meters),
                type=metering_type,
            )
        )
        if "result" not in response:
            raise DSCommandFailedException("no result in server response")

        entries = [
            entry
            for entry in response["result"].get("values") or []
            if entry.get("value") is not None
        ]

        # a meter is known by its dSID and its dSUID, servers use either
        dsuid_by_id = {}
        for meter in meters:
            dsuid_by_id[str(meter.unique_id).lower()] = meter.dsuid
            dsuid_by_id[str(meter.dsuid).lower()] = meter.dsuid

        values = {}
        for entry in entries:
            for key in self.METERING_ID_KEYS:
                dsuid = dsuid_by_id.get(str(entry.get(key)).lower())
                if dsuid:
                    values[dsuid] = entry["value"]
                    break

        # an answer that doesn't say who it is from can only be from the one
        # meter we asked for
        if not values and len(meters) == 1 and len(entries) == 1:
            values[meters[0].dsuid] = entries[0]["value"]

        if entries and not values and not self._warned_metering_ids:
            self._warned_metering_ids = True
            _LOGGER.warning(
                "Metering values for {type} don't belong to any known meter "
                "(asked for {asked}), got: {got}".format(
                    type=metering_type,
                    asked=[(m.dsuid, m.unique_id) for m in meters],
                    got=str(entries)[:500],
                )
            )

        return values
