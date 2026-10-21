# digitalSTROM component for Home Assistant

This integration makes digitalSTROM lights, covers, switches and scenes available in Home Assistant.

It supports config flows so that you can easily add your digitalSTROM server from the Home Assistant frontend (Settings -> Devices & services).

However it does not support YAML config setup (anymore). The future is the frontend!

## digitalSTROM basics

The digitalSTROM state machine works best when devices are not controlled directly. Therefore this integration works exclusively with the concept of digitalSTROM scenes. However to be more convenient, some scenes are combined to form meta devices.

**Only named scenes are supported** - so make sure all scenes you would like to control have a name in digitalSTROM.
If there are matching on/off scenes as the broadcast scene and area scenes, the name of the turn off scene is used as it comes first in numerical order.

## Devices

### Lights

These are not real lights! e.g. no GE-KM200 or similar is exposed directly.
Instead the activation and deactivation scenes of digitalSTROM light areas are combined to light devices.
Each room consists of four areas and a broadcast (all on/off). The name of the turn-off-scene is used as the device name,

Lights and switches start with the state the digitalSTROM server reports (the scene that was called last in the zone) instead of guessing from the last known state. The server only remembers one scene per zone and group, so this is exact when the last scene called is one of the light's own scenes or a "turn everything off". If another area or scene was called last, the light starts with the state Home Assistant remembered. The same applies to the sleeping and present switches, which share one slot. From then on, state follows the scenes called on the server.

### Covers

Same behavior as with lights for area cover scenes

### Switches

Only sleeping and presence on/off scenes are merged in meta switch devices for now.

### Scenes

Every scene that is not an area light or cover scene is exposed as a regular scene to Home Assistant.

### Meters

Every power meter.

## Options and authentication

The delay between commands can be changed at any time in the integration's options. If the app token is missing or was revoked in the digitalSTROM server, Home Assistant asks you to authenticate again; your password is only used to request a new token and is not stored.

## BREAKING CHANGES

Release 1.1.0 introduced a backwards incompatible change that makes it necessary to set up the integration from scratch
