# -*- coding: UTF-8 -*-
from ..client import DSClient
from ..devices.base import DSDevice


class DSScene(DSDevice):
    URL_TURN_ON = (
        "/json/zone/callScene?id={zone_id}&" "sceneNumber={scene_id}&force=true"
    )

    def __init__(
        self,
        client: DSClient,
        zone_id,
        zone_name,
        scene_id,
        scene_name,
        *args,
        **kwargs
    ):
        self._scene_id = scene_id
        self._scene_name = scene_name.replace("SCENE_","").title()

        device_id = "{zone_id}_{scene_id}".format(
            zone_id=zone_id, scene_id=self._scene_id
        )
        device_name = "{zone} / {name}".format(
            zone=zone_name, name=self._scene_name
        )

        super().__init__(
            client=client, device_id=device_id, device_name=device_name, zone_name=zone_name, zone_id=zone_id, *args, **kwargs
        )

    async def turn_on(self):
        await self.request(
            url=self.URL_TURN_ON.format(zone_id=self._zone_id, scene_id=self._scene_id)
        )

    @property
    def scene_name(self):
        return self._scene_name
    
    @property
    def scene_id(self):
        return self._scene_id
    

class DSColorScene(DSDevice):
    URL_TURN_ON = (
        "/json/zone/callScene?id={zone_id}&"
        "sceneNumber={scene_id}&groupID={color}&force=true"
    )

    def __init__(
        self,
        client: DSClient,
        zone_id,
        zone_name,
        scene_id,
        scene_name,
        color,
        *args,
        **kwargs
    ):
        self._scene_id = scene_id
        self._scene_name = scene_name.replace("SCENE_","").title()
        self._color = color

        device_id = "{zone_id}_{color}_{scene_id}".format(
            zone_id=zone_id, color=self._color, scene_id=self._scene_id
        )
        device_name = "{zone} / {name}".format(
            zone=zone_name, name=self._scene_name
        )

        super().__init__(
            client=client, device_id=device_id, device_name=device_name, zone_name=zone_name, zone_id=zone_id, *args, **kwargs
        )

    async def turn_on(self):
        await self.request(
            url=self.URL_TURN_ON.format(
                zone_id=self._zone_id, color=self._color, scene_id=self._scene_id
            )
        )

    @property
    def scene_name(self):
        return self._scene_name
    
    @property
    def scene_id(self):
        return self._scene_id
    
    @property
    def color(self):
        return self._color