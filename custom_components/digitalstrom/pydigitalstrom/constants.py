# -*- coding: UTF-8 -*-

# https://developer.digitalstrom.org/Architecture/ds-basics.pdf
# https://developer.digitalstrom.org/Architecture/ds-light.pdf

SCENES = {
    "PRESET" : {
        "SCENE_PRESET0": 0,
        "SCENE_PRESET1": 5,
        "SCENE_PRESET2": 17,
        "SCENE_PRESET3": 18,
        "SCENE_PRESET4": 19,
        "SCENE_PRESET11": 33,
        "SCENE_PRESET10": 32,
        "SCENE_PRESET12": 32,
        "SCENE_PRESET13": 21,
        "SCENE_PRESET14": 22,
        "SCENE_PRESET20": 34,
        "SCENE_PRESET21": 35,
        "SCENE_PRESET22": 23,
        "SCENE_PRESET23": 24,
        "SCENE_PRESET24": 25,
        "SCENE_PRESET30": 36,
        "SCENE_PRESET31": 37,
        "SCENE_PRESET32": 26,
        "SCENE_PRESET33": 27,
        "SCENE_PRESET34": 28,
        "SCENE_PRESET40": 38,
        "SCENE_PRESET41": 39,
        "SCENE_PRESET42": 29,
        "SCENE_PRESET43": 30,
        "SCENE_PRESET44": 31
    },
    "STEPPING": {
        "SCENE_DECREMENT": 11,
        "SCENE_INCREMENT": 12,
    },
    "AREA": {
        "SCENE_AREA1_OFF": 1,
        "SCENE_AREA1_ON": 6,
        "SCENE_AREA1_DECREMENT": 42,
        "SCENE_AREA1_INCREMENT": 43,
        "SCENE_AREA1_STOP": 52,
        "SCENE_AREA1_STEPPING_CONTINUE": 10,
        "SCENE_AREA2_OFF": 2,
        "SCENE_AREA2_ON": 7,
        "SCENE_AREA2_DECREMENT": 44,
        "SCENE_AREA2_INCREMENT": 45,
        "SCENE_AREA2_STOP": 53,
        "SCENE_AREA2_STEPPING_CONTINUE": 10,
        "SCENE_AREA3_OFF": 3,
        "SCENE_AREA3_ON": 8,
        "SCENE_AREA3_DECREMENT": 46,
        "SCENE_AREA3_INCREMENT": 47,
        "SCENE_AREA3_STOP": 54,
        "SCENE_AREA3_STEPPING_CONTINUE": 10,
        "SCENE_AREA4_OFF": 4,
        "SCENE_AREA4_ON": 9,
        "SCENE_AREA4_DECERMENT": 48,
        "SCENE_AREA4_INCREMENT": 49,
        "SCENE_AREA4_STOP": 55,
        "SCENE_AREA4_STEPPING_CONTINUE": 10,
    },
    "GROUP_INDIPENDENT" : {
        "SCENE_DEEP_OFF": 68,
        "SCENE_STANDBY": 67,
        "SCENE_ZONE_ACTIVE": 75,
        "SCENE_AUTO_STANDBY": 64,
        "SCENE_ABSENT": 72,
        "SCENE_PRESENT": 71,
        "SCENE_SLEEPING": 69,
        "SCENE_WAKEUP": 70,
        "SCENE_DOOR_BELL": 73,
        "SCENE_PANIC": 65,
        "SCENE_FIRE": 76,
        "SCENE_ALARM_1": 74,
        "SCENE_ALARM_2": 83,
        "SCENE_ALARM_3": 84,
        "SCENE_ALARM_4": 85,
        "SCENE_WIND": 86,
        "SCENE_NO_WIND": 87,
        "SCENE_RAIN": 88,
        "SCENE_NO_RAIN": 89,
        "SCENE_HAIL": 90,
        "SCENE_NO_HAIL": 91,
        "SCENE_POLLUTION": 92,
        "SCENE_BURGLARY": 93,
    }
}

ALL_SCENES_BYNAME = {}
ALL_SCENES_BYID = {}

for scene_type, scenes in SCENES.items():
    for scene_name, scene_id in scenes.items():
        ALL_SCENES_BYNAME[scene_name] = scene_id
        ALL_SCENES_BYID[scene_id] = scene_name


GROUP_LIGHTS = 1
GROUP_BLINDS = 2
GROUP_HEATING = 3
GROUP_COOLING = 9
GROUP_VENTILATION = 10
GROUP_WINDOW = 11
GROUP_RECICULATION = 12
GROUP_APARTMENT_VENTILATION = 64
GROUP_TEMPERATURE_CONTROL = 48
GROUP_AUDIO = 4
GROUP_VIDEO = 5
GROUP_JOKER = 8
