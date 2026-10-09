"""Read-only first-stage Home Assistant setup for IntelliCenter.

No physical commands are permitted in the observation commissioning stage.
Do not migrate entity IDs until a separately verified cutover.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .transport import IntelliCenterManualTransport
from .observation_coordinator import ObservationFanout

PLATFORMS = ["climate", "binary_sensor", "sensor", "switch", "light", "number", "select"]


@dataclass
class Runtime:
    transport: IntelliCenterManualTransport
    observation_fanout: ObservationFanout

    def __getattr__(self, name):
        # Climate platform receives runtime_data and calls transport methods.
        return getattr(self.transport, name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect without equipment actuation; publish only observed state."""
    host = str(entry.data.get("host", "")).strip()
    if not host:
        raise ConfigEntryNotReady("IntelliCenter host is not configured")

    transport = IntelliCenterManualTransport(host, allow_commands=False)
    fanout = ObservationFanout(transport)
    runtime = Runtime(transport=transport, observation_fanout=fanout)
    entry.runtime_data = runtime
    fanout.start()
    try:
        await transport.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        fanout.close()
        await transport.stop()
        raise

    # Re-publish periodically so a quiet/disconnected controller cannot leave
    # an indefinitely valid last observation in HA.
    unsubscribe = async_track_time_interval(
        hass, lambda _now: fanout.refresh(), timedelta(seconds=30)
    )
    entry.async_on_unload(unsubscribe)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities first, then disconnect and remove all listeners."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = entry.runtime_data
    runtime.observation_fanout.close()
    await runtime.transport.stop()
    return True
