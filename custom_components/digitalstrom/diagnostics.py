"""Diagnostics for a digitalSTROM config entry."""
from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import DigitalstromConfigEntry

# unique id and title are made of host and port, the ids identify the
# installation
TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    "title",
    "unique_id",
    "dsuid",
    "dsid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DigitalstromConfigEntry
) -> dict[str, Any]:
    """what is needed to understand a problem report, without secrets"""
    data = entry.runtime_data
    client, listener = data.client, data.listener

    scenes = client.get_scenes().values()
    coordinator = data.meter_coordinator

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "command_stack": {
            "running": client.stack.running,
            "delay_ms": client.stack.delay,
            "pending": client.stack.pending,
        },
        "websocket": {
            "running": listener.running,
            "connected": listener.connected,
            "last_keepalive": listener.last_keepalive,
            "callbacks": listener.callback_count,
        },
        "zones": client.get_zone_names(),
        "scenes": dict(Counter(type(scene).__name__ for scene in scenes)),
        "last_called_scenes_at_setup": {
            f"zone {zone_id} group {group_id}": scene_id
            for (zone_id, group_id), scene_id in client.get_last_called_scenes().items()
        },
        "meters": async_redact_data(
            {
                "known": [
                    {"name": meter.name, "dsuid": dsuid, "dsid": meter.unique_id}
                    for dsuid, meter in client.get_meters().items()
                ],
                "last_update_success": None
                if coordinator is None
                else coordinator.last_update_success,
                "update_interval_s": None
                if coordinator is None
                else coordinator.update_interval.total_seconds(),
                "readings": None
                if coordinator is None or coordinator.data is None
                else {
                    f"meter {index}": {
                        "consumption": values.consumption,
                        "energy": values.energy,
                    }
                    for index, values in enumerate(coordinator.data.values(), 1)
                },
            },
            TO_REDACT,
        ),
    }
