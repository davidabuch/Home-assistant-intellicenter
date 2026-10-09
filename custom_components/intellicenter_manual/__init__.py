"""Read-only first-stage Home Assistant setup for IntelliCenter.

No physical commands are permitted in the observation commissioning stage.
Do not migrate entity IDs until a separately verified cutover.
"""
from __future__ import annotations

from dataclasses import dataclass
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
from homeassistant.util import dt as dt_util
from pyintellicenter import STATUS_ATTR, STATUS_ON, STATUS_OFF, HEATER_ATTR, SPEED_ATTR

from .transport import IntelliCenterManualTransport
from .observation_coordinator import ObservationFanout

DIAGNOSTIC_SERVICE = "commission_abort_own_tcp"
DOMAIN = "intellicenter_manual"

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
    def _exclusive_manual_authority() -> bool:
        # After cutover, absence of the PoolOS config entry proves that no
        # legacy PoolOS writer can be loaded. Never infer this from missing
        # entities while a PoolOS config entry still exists.
        legacy_entries = hass.config_entries.async_entries("poolos")
        if not legacy_entries:
            return True
        # Do not treat disabled autonomy as proof that PoolOS manual writes
        # have been disabled. Both legacy thermostats must explicitly attest
        # that manual delivery is OFF; unknown/unavailable fails closed.
        for entity_id in (
            "climate.poolos_native_intellicenter_pool_thermostat",
            "climate.poolos_native_intellicenter_hot_tub_thermostat",
        ):
            state = hass.states.get(entity_id)
            if (state is None or state.state in {"unknown", "unavailable"}
                    or state.attributes.get("manual_command_delivery_enabled") is not False):
                return False
        for entity_id in (
            "switch.poolos_autonomous_pool_control",
            "switch.poolos_autonomous_hot_tub_control",
        ):
            state = hass.states.get(entity_id)
            if state is None or state.state != "off":
                return False
        return True

    transport.set_manual_authority_check(_exclusive_manual_authority)

    def _reacquire_native_authority() -> None:
        """Rearm only after fresh native telemetry and exclusive ownership."""
        if not entry.options.get("native_command_authority", False):
            return
        observation = transport.read_observation()
        if (transport.connected and observation.connected
                and observation.observed_at is not None
                and _exclusive_manual_authority()):
            transport.arm_manual_thermostats()

    def _outage_command_allowed(method: str, args: tuple) -> bool:
        """Safety wins while both the physical outage latch and policy are active.

        This checks at the final command gateway, not only in automations.
        Operator bypass releases the lockout for this outage.
        """
        active = hass.states.get("input_boolean.grid_outage_active")
        protection = hass.states.get("input_boolean.grid_outage_protection")
        bypass = hass.states.get("input_boolean.grid_outage_operator_bypass_latch")
        if not (active and active.state == "on"
                and protection and protection.state == "on"
                and bypass and bypass.state == "off"):
            return True
        within_window = 9 <= dt_util.as_local(dt_util.utcnow()).hour < 17
        if method == "request_changes" and len(args) == 2:
            obj, changes = args
            if obj in {"B1101", "B1202"} and set(changes) == {HEATER_ATTR}:
                return changes[HEATER_ATTR] == "00000"
            if obj == "B1202" and set(changes) == {STATUS_ATTR}:
                return changes[STATUS_ATTR] == STATUS_OFF
            if obj == "B1101" and set(changes) == {STATUS_ATTR}:
                return changes[STATUS_ATTR] == STATUS_OFF or (within_window and changes[STATUS_ATTR] == STATUS_ON)
            if obj == transport._pool_speed_assignment() and set(changes) == {SPEED_ATTR}:
                return within_window and changes[SPEED_ATTR] == "1500"
        if method == "set_circuit_state" and len(args) == 2:
            return args[1] is False
        return False

    transport.set_outage_command_check(_outage_command_allowed)

    fanout = ObservationFanout(transport, asyncio.get_running_loop())
    runtime = Runtime(transport=transport, observation_fanout=fanout)
    entry.runtime_data = runtime
    fanout.start()
    try:
        await transport.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _reacquire_native_authority()
    except Exception:
        fanout.close()
        await transport.stop()
        raise

    # Commissioning-only service. Never sends physical commands. The exact
    # config entry ID is required so a different integration cannot be targeted.
    async def _abort_own_tcp(call: ServiceCall) -> None:
        if call.data.get("entry_id") != entry.entry_id:
            raise ValueError("Replacement config entry ID mismatch")
        if call.data.get("confirm") != "ABORT_REPLACEMENT_TCP_ONLY":
            raise ValueError("Explicit diagnostic confirmation required")
        runtime.transport.commission_abort_own_tcp()

    async def _arm_manual_thermostats(call: ServiceCall) -> None:
        if call.data.get("entry_id") != entry.entry_id:
            raise ValueError("Replacement config entry ID mismatch")
        if call.data.get("confirm") != "ARM_NATIVE_THERMOSTATS":
            raise ValueError("Explicit manual commissioning confirmation required")
        transport.arm_manual_thermostats()
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "native_command_authority": True}
        )

    async def _disarm_manual_thermostats(call: ServiceCall) -> None:
        if call.data.get("entry_id") != entry.entry_id:
            raise ValueError("Replacement config entry ID mismatch")
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "native_command_authority": False}
        )
        transport.disarm_manual_thermostats()

    hass.services.async_register(DOMAIN, "arm_manual_thermostats", _arm_manual_thermostats)
    hass.services.async_register(DOMAIN, "disarm_manual_thermostats", _disarm_manual_thermostats)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "arm_manual_thermostats"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "disarm_manual_thermostats"))
    hass.services.async_register(DOMAIN, DIAGNOSTIC_SERVICE, _abort_own_tcp)
    entry.async_on_unload(
        lambda: hass.services.async_remove(DOMAIN, DIAGNOSTIC_SERVICE)
    )

    # Re-publish periodically so a quiet/disconnected controller cannot leave
    # an indefinitely valid last observation in HA.
    unsubscribe = async_track_time_interval(
        hass, lambda _now: (fanout.refresh(), _reacquire_native_authority()),
        timedelta(seconds=30)
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
