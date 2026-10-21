# digitalSTROM component for Home Assistant

## What is this about?

[Home Assistant](https://www.home-assistant.io/) is an open source home automation and control system.

[digitalSTROM](https://www.digitalstrom.com/) is a smart home control solution developed by the Swiss digitalSTROM AG

## What does it do?

This integration makes digitalSTROM lights, covers, switches and scenes available in Home Assistant.

However it does not support YAML config setup (anymore). The future is the frontend!

Please read [info.md](info.md) carefully to understand how this integration works with digitalSTROM features and why devices cannot be controlled directly.

## Events

Every scene that is called on the digitalSTROM server fires a `digitalstrom_scene_called` event on the Home Assistant event bus, no matter where it came from: wall buttons, the digitalSTROM app or Home Assistant itself. This includes standard scenes that are not exposed as entities, like door bell, panic or alarms.

| Field | Description |
| --- | --- |
| `entry_id` | config entry of the server |
| `zone_id`, `zone_name` | zone the scene was called in (`zone_name` is `null` for unnamed zones) |
| `group_id` | group (color) the scene was called for, e.g. 1 for lights |
| `scene_id`, `scene_name` | number and name of the scene (`scene_name` is `null` if unknown) |
| `origin_device_id` | dSID of the device (e.g. the wall button) that caused the call, `null` if the server doesn't tell |
| `properties` | everything the server sent with the event |

Example automation that reacts to the door bell:

```yaml
triggers:
  - trigger: event
    event_type: digitalstrom_scene_called
    event_data:
      scene_id: 73 # door bell
actions:
  - action: notify.notify
    data:
      message: "Someone is at the door ({{ trigger.event.data.zone_name }})"
```

To react to one particular button, add its `origin_device_id` to `event_data`. Press the button while listening to the event (see below) to find the value.

Use the *Events* tab in *Developer tools* to listen to `digitalstrom_scene_called` and see which scene numbers your buttons send.

## How can I install it?

The easiest way to install the integration is by using [Home Assistant Community Store HACS](https://hacs.netlify.com/).
For now, you have to [add the repository yourself](https://hacs.netlify.com/usage/settings/#add-custom-repositories) - chose type "Integration".

## Are there any limitations?

Yes. Based on the nature of how digitalSTROM servers communicate with single devices, a digitalSTROM installation can easily be overwhelmed with too many commands. It is therefore recommended to not issue more than 2-3 commands per second. This integration takes care of that by handling one command after the other. The default delay is 500ms. It can be changed when setting up the integration and later in the integration's options (Configure). The power meters are read with two requests per interval, no matter how many meters there are; the interval is an option as well.


## Development

The tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component), so they run the integration in a real Home Assistant core against a fake digitalSTROM server (TLS, websocket). That needs a recent Python (3.13 at the time of writing) and `openssl` to create a throw-away certificate.

```
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
ruff check .
pytest
```

The same checks run on every pull request (`.github/workflows`), together with [hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) and the HACS validation.
