"""Explicit manual-only IntelliCenter command gateway.

No scheduler, owner arbitration, PoolOS dependency, or autonomous commands.
This module must only be called by an explicit HA service/entity action.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any
from pyintellicenter import (
    ICConnectionHandler, ICModelController, PoolModel, LIGHT_EFFECTS,
    STATUS_ATTR, STATUS_ON, STATUS_OFF, HEATER_ATTR,
    BODY_TYPE, CIRCUIT_TYPE, SENSE_TYPE, PUMP_TYPE, SYSTEM_TYPE,
    CHEM_TYPE, PMPCIRC_TYPE, CIRCUIT_ATTR, SELECT_ATTR, SPEED_ATTR, BODY_ATTR, PRIM_ATTR, SEC_ATTR, SALT_ATTR,
    LOTMP_ATTR, LSTTMP_ATTR, HTMODE_ATTR, SOURCE_ATTR,
    RPM_ATTR, GPM_ATTR, PWR_ATTR, MIN_ATTR, MAX_ATTR, VER_ATTR, SERVICE_ATTR,
    OBJTYP_ATTR, SNAME_ATTR, HITMP_ATTR, MODE_ATTR,
    VOL_ATTR, PARENT_ATTR, SUBTYP_ATTR,
)
from pyintellicenter.attributes import ALL_ATTRIBUTES_BY_TYPE

BODY_IDS = frozenset({"B1101", "B1202"})
CIRCUIT_IDS = frozenset({"C0002", "C0003", "C0004", "FTR01"})
HEATER_IDS = frozenset({"00000", "H0001", "H0002"})

def _native_status(value):
    """Only exact commissioned ON/OFF codes are trusted as boolean truth."""
    if value is None:
        return None
    normalized = str(value).upper()
    if normalized == str(STATUS_ON).upper():
        return True
    if normalized == str(STATUS_OFF).upper():
        return False
    return None



class ManualCommandError(RuntimeError):
    """Explicit command could not be dispatched."""


class _DiscoveryPoolModel(PoolModel):
    """Use PoolOS-commissioned narrow BODY and SENSE subscriptions."""

    def __init__(self):
        self._attribute_map = {key: set(value) for key, value in ALL_ATTRIBUTES_BY_TYPE.items()}
        self._attribute_map[BODY_TYPE] = {
            SNAME_ATTR, HEATER_ATTR, HITMP_ATTR, HTMODE_ATTR, LOTMP_ATTR,
            LSTTMP_ATTR, MODE_ATTR, STATUS_ATTR, VOL_ATTR,
        }
        self._attribute_map[SENSE_TYPE] = {SNAME_ATTR, SOURCE_ATTR}
        super().__init__(self._attribute_map)

    def add_object(self, objnam, params):
        objtype = params.get(OBJTYP_ATTR)
        if isinstance(objtype, str) and objtype:
            self._attribute_map.setdefault(
                objtype, {SNAME_ATTR, PARENT_ATTR, STATUS_ATTR, SUBTYP_ATTR}
            )
        return super().add_object(objnam, params)


class _CommissioningController(ICModelController):
    """Fail-closed write boundary, independently enforced at protocol layer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manual_writes_enabled = False

    async def send_cmd(self, cmd, extra=None):
        if not self.manual_writes_enabled and cmd not in {"GetParamList", "RequestParamList"}:
            raise ManualCommandError(f"Unsafe protocol operation blocked: {cmd}")
        return await super().send_cmd(cmd, extra)

    async def request_changes(self, objnam, changes):
        if not self.manual_writes_enabled:
            raise ManualCommandError("Physical writes disabled in commissioning controller")
        return await super().request_changes(objnam, changes)

    async def _queue_property_change(self, objnam, changes):
        if not self.manual_writes_enabled:
            raise ManualCommandError("Physical writes disabled in commissioning controller")
        return await super()._queue_property_change(objnam, changes)


class _ObservedConnectionHandler(ICConnectionHandler):
    def __init__(self, owner, controller):
        super().__init__(controller, time_between_reconnects=30)
        self.owner = owner

    def on_started(self, controller):
        self.owner._connection_changed(True)

    def on_reconnected(self, controller):
        self.owner._connection_changed(True)

    def on_disconnected(self, controller, exc):
        self.owner._connection_changed(False)

    def on_retrying(self, delay):
        self.owner._connection_changed(False)

    def on_updated(self, controller, updates):
        self.owner._model_updated()


class IntelliCenterManualTransport:
    """Small allow-listed command interface; never makes autonomous decisions."""

    def __init__(self, host: str, *, allow_commands: bool = False) -> None:
        if not host or not host.strip():
            raise ValueError("IntelliCenter host is required")
        self.model = _DiscoveryPoolModel()
        self.controller = _CommissioningController(
            host.strip(), self.model, keepalive_interval=90.0, transport="tcp"
        )
        self.handler = _ObservedConnectionHandler(self, self.controller)
        self._connected = False
        self._observed_at = None
        self._on_observation: Callable[[], None] | None = None
        self._allow_commands = allow_commands
        self._lock = asyncio.Lock()
        self._started = False
        self._manual_authority_check = None
        self._outage_command_check = None

    @property
    def connected(self) -> bool:
        return self._connected and self._started

    def set_manual_authority_check(self, callback) -> None:
        """Install an external ownership preflight; never infer ownership."""
        self._manual_authority_check = callback

    def set_outage_command_check(self, callback) -> None:
        """HA safety preflight for every physical command, under the dispatch lock."""
        self._outage_command_check = callback

    def arm_manual_thermostats(self) -> None:
        if self._manual_authority_check is None or not self._manual_authority_check():
            raise ManualCommandError("Exclusive manual authority not verified")
        self._allow_commands = True
        self.controller.manual_writes_enabled = True

    def disarm_manual_thermostats(self) -> None:
        self.controller.manual_writes_enabled = False
        self._allow_commands = False

    def set_observation_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_observation = callback

    def _connection_changed(self, connected: bool) -> None:
        self._connected = connected
        # Connection establishment is not proof that a complete model was read.
        self._observed_at = None
        if not connected:
            self.disarm_manual_thermostats()
        self._publish()

    def _model_updated(self) -> None:
        if not self._connected:
            return
        self._observed_at = datetime.now(timezone.utc)
        self._publish()

    def _publish(self) -> None:
        if self._on_observation is not None:
            self._on_observation()

    def read_observation(self):
        from .observation import adapt_snapshot
        from types import SimpleNamespace
        bodies = []
        circuits = []
        telemetry = {}
        freeze_active = None
        if self.connected and self._observed_at is not None:
            for obj in self.model.get_by_type(BODY_TYPE):
                if str(obj.objnam) not in BODY_IDS:
                    continue
                properties = obj.properties
                status = properties.get(STATUS_ATTR)
                heat_mode = properties.get(HTMODE_ATTR)
                # Incomplete discovery must not be interpreted as a live body.
                if status is None or heat_mode is None:
                    continue
                active = _native_status(status)
                try:
                    heating = self.controller.is_body_heating(obj.objnam)
                except (LookupError, AttributeError, ValueError):
                    heating = None
                bodies.append(SimpleNamespace(
                    id=str(obj.objnam), is_on=active,
                    heating_active=heating if type(heating) is bool else None,
                    current_temperature=properties.get(LSTTMP_ATTR),
                    target_temperature=properties.get(LOTMP_ATTR),
                    active_heat_source=properties.get(HEATER_ATTR),
                ))
            for obj in self.model.get_by_type(CIRCUIT_TYPE):
                if str(obj.objnam) not in CIRCUIT_IDS:
                    continue
                status = obj.properties.get(STATUS_ATTR)
                active = _native_status(status)
                raw_use = obj.properties.get('USE') if str(obj.objnam) == 'C0002' else None
                effect_code = str(raw_use) if raw_use is not None and str(raw_use) in LIGHT_EFFECTS else None
                circuits.append(SimpleNamespace(id=str(obj.objnam), is_on=active, effect_code=effect_code))
            # Freeze is a native CIRCUIT with subtype FRZ, not a temperature threshold or
            # a PoolOS entity. Reject missing/duplicate/unknown observations.
            freeze_candidates = [obj for obj in self.model.get_by_type(CIRCUIT_TYPE)
                                 if str(obj.subtype or "").strip().upper() == "FRZ"]
            if len(freeze_candidates) == 1:
                freeze_active = _native_status(
                    freeze_candidates[0].properties.get(STATUS_ATTR))
            # Probe subtype alone is not authoritative when multiple native
            # sensors advertise the same role. Fail closed on duplicates.
            probe_keys = {'AIR': 'air_temperature', 'SOLAR': 'solar_temperature', 'POOL': 'water_temperature'}
            probes_by_key = {key: [] for key in probe_keys.values()}
            for obj in self.model.get_by_type(SENSE_TYPE):
                key = probe_keys.get(str(obj.subtype or '').upper())
                if key is not None:
                    probes_by_key[key].append(obj)
            for key, probes in probes_by_key.items():
                if len(probes) == 1:
                    telemetry[key] = probes[0].properties.get(SOURCE_ATTR)
            # Never bind arbitrary pump discovery order to the commissioned PMP01.
            # Missing or duplicate identities remain unknown rather than reporting
            # a potentially different pump as authoritative.
            pumps = [obj for obj in self.model.get_by_type(PUMP_TYPE)
                     if str(obj.objnam) == "PMP01"]
            if len(pumps) == 1:
                props = pumps[0].properties
                telemetry.update(pump_rpm=props.get(RPM_ATTR),
                    pump_flow_rate=props.get(GPM_ATTR), pump_power=props.get(PWR_ATTR),
                    pump_minimum_rpm=props.get(MIN_ATTR), pump_maximum_rpm=props.get(MAX_ATTR))
            # A single commissioned IntelliChlor object and an unambiguous
            # two-body mapping are required before publishing chemistry.
            chlorinators = [obj for obj in self.model.get_by_type(CHEM_TYPE)
                            if str(obj.objnam) == 'CHR01'
                            and str(obj.subtype or '').upper() == 'ICHLOR']
            if len(chlorinators) == 1:
                props = chlorinators[0].properties
                body_ids = str(props.get(BODY_ATTR) or '').split()
                if len(body_ids) == 2 and set(body_ids) == {'B1101', 'B1202'}:
                    for body_id, attribute in zip(body_ids, (PRIM_ATTR, SEC_ATTR)):
                        key = {'B1101': 'intellichlor_pool_output',
                               'B1202': 'intellichlor_spa_output'}[body_id]
                        telemetry[key] = props.get(attribute)
                    telemetry['intellichlor_salt'] = props.get(SALT_ATTR)
            # Do not select arbitrary first system object when discovery is
            # ambiguous; no firmware or service-mode assertion is safe then.
            systems = list(self.model.get_by_type(SYSTEM_TYPE))
            if len(systems) == 1:
                props = systems[0].properties
                telemetry.update(firmware_version=props.get(VER_ATTR),
                                 system_mode=props.get(SERVICE_ATTR))
        return adapt_snapshot(SimpleNamespace(
            connected=self.connected, observed_at=self._observed_at,
            bodies=bodies, circuits=circuits, telemetry=telemetry,
            freeze_active=freeze_active,
        ))

    def commission_abort_own_tcp(self) -> None:
        """One-shot diagnostic: abort ONLY this integration's TCP transport.

        Unlike ICConnection.disconnect(), abort preserves the unexpected-loss
        callback, exercising the real ICConnectionHandler reconnect path.
        Never touches a host firewall, shared network, or PoolOS connection.
        """
        if not self._started or not self._connected or not self.handler.connected:
            raise RuntimeError("Replacement native TCP transport is not connected")
        connection = self.controller._connection
        if connection is None or not connection.connected:
            raise RuntimeError("Replacement TCP connection is unavailable")
        protocol = connection._protocol
        if protocol is None or protocol._transport is None:
            raise RuntimeError("Replacement TCP protocol transport is unavailable")
        self._connection_changed(False)
        protocol._transport.abort()

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            await self.handler.start()
        except Exception:
            self._started = False
            self._connected = False
            self._observed_at = None
            self._publish()
            raise
        self._publish()

    async def stop(self) -> None:
        self.disarm_manual_thermostats()
        self.handler.stop()
        try:
            await self.controller.stop()
        finally:
            self._started = False
            self._connected = False
            self._observed_at = None
            self._publish()

    def _pool_speed_assignment(self) -> str:
        """Resolve the unique live Pool PMPCIRC speed assignment, never PMP01."""
        matches = []
        for candidate in self.model.get_by_type(PMPCIRC_TYPE):
            if (str(candidate[CIRCUIT_ATTR] or "") != "C0006"
                    or str(candidate[SELECT_ATTR] or "").upper() != "RPM"):
                continue
            parent_id = str(candidate[PARENT_ATTR] or "").strip()
            parent = self.model[parent_id] if parent_id else None
            if parent is None or str(parent.objtype).upper() != str(PUMP_TYPE).upper():
                continue
            matches.append(str(candidate.objnam))
        if len(matches) != 1:
            raise ManualCommandError("Unique Pool RPM PMPCIRC assignment unavailable")
        return matches[0]

    async def _send(self, method: str, *args: Any) -> Any:
        if not self._allow_commands:
            raise ManualCommandError("Read-only commissioning: all physical commands are disabled")
        # Explicit manual actuator allowlist; no arbitrary protocol commands.
        if not (
            (method == "request_changes" and len(args) == 2
             and args[0] in BODY_IDS
             and isinstance(args[1], dict)
             and set(args[1]) == {STATUS_ATTR}
             and args[1][STATUS_ATTR] in {STATUS_ON, STATUS_OFF})
            or (method == "request_changes" and len(args) == 2
                and args[0] in BODY_IDS and type(args[1]) is dict
                and set(args[1]) == {HEATER_ATTR}
                and args[1][HEATER_ATTR] in HEATER_IDS)
            or (method == "request_changes" and len(args) == 2
                and args[0] == self._pool_speed_assignment() and type(args[1]) is dict
                and set(args[1]) == {SPEED_ATTR}
                and type(args[1][SPEED_ATTR]) is str
                and args[1][RPM_ATTR].isdigit()
                and 600 <= int(args[1][RPM_ATTR]) <= 3450)
            or (method == "set_circuit_state" and len(args) == 2
                and args[0] in CIRCUIT_IDS and type(args[1]) is bool)
            or (method == "set_light_effect" and len(args) == 2
                and args[0] == "C0002" and args[1] in LIGHT_EFFECTS)
            or (method == "set_chlorinator_output" and len(args) in (2, 3)
                and args[0] == "CHR01"
                and all(type(v) is int and 0 <= v <= 100 for v in args[1:]))
            or (method == "set_heating_setpoint" and len(args) == 2
                and args[0] in BODY_IDS and type(args[1]) is int
                and 40 <= args[1] <= 104)
        ):
            raise ManualCommandError("Command outside commissioned native manual allowlist")
        async with self._lock:
            # Recheck freshness after lock acquisition: waiting commands must
            # not inherit authority from an earlier observation.
            observation = self.read_observation()
            if not self.connected or not observation.connected:
                raise ManualCommandError("No fresh native IntelliCenter observation")
            if not self.controller.manual_writes_enabled:
                raise ManualCommandError("Native controller write gate is disarmed")
            if self._manual_authority_check is None or not self._manual_authority_check():
                self.disarm_manual_thermostats()
                raise ManualCommandError("Exclusive manual authority lost")
            if self._outage_command_check is not None and not self._outage_command_check(method, args):
                raise ManualCommandError("Grid outage safety lockout: command prohibited")
            try:
                result = await getattr(self.controller, method)(*args)
            except Exception as exc:
                raise ManualCommandError(f"{method} dispatch failed") from exc
            # An ACK is not proof of physical state. Keep the last observed
            # read model available while waiting for a NEW native update:
            # clearing _observed_at here briefly marks EVERY HA entity
            # unavailable on every command, including unrelated controls.
            # _confirm_body still requires observed_at > dispatched_at.
            return datetime.now(timezone.utc)

    async def _confirm_body(self, body_id: str, field: str, expected: Any, dispatched_at: datetime) -> None:
        """Require a NEW native observation showing the commanded result.

        A successful TCP response alone is never accepted as physical proof.
        """
        deadline = asyncio.get_running_loop().time() + 25.0
        while asyncio.get_running_loop().time() < deadline:
            observation = self.read_observation()
            body = observation.body(body_id) if observation.connected else None
            if (body is not None and observation.observed_at > dispatched_at
                    and getattr(body, field) == expected):
                return
            await asyncio.sleep(0.5)
        raise ManualCommandError(
            f"Native confirmation timeout for {body_id} {field}; physical state unverified"
        )

    async def set_body_active(self, body_id: str, active: bool) -> None:
        if body_id not in BODY_IDS or type(active) is not bool:
            raise ValueError("invalid body or active state")
        dispatched_at = await self._send(
            "request_changes", body_id,
            {STATUS_ATTR: STATUS_ON if active else STATUS_OFF},
        )
        await self._confirm_body(body_id, "active", active, dispatched_at)

    async def set_pump_rpm(self, rpm: float) -> None:
        if isinstance(rpm, bool) or not 600 <= float(rpm) <= 3450:
            raise ValueError("Pump RPM outside commissioned range")
        await self._send("request_changes", self._pool_speed_assignment(), {SPEED_ATTR: str(round(float(rpm)))})

    async def set_target(self, body_id: str, fahrenheit: float) -> None:
        if body_id not in BODY_IDS or isinstance(fahrenheit, bool):
            raise ValueError("invalid body or target")
        target = round(float(fahrenheit))
        if not 40 <= target <= 104:
            raise ValueError("temperature outside safe range")
        dispatched_at = await self._send("set_heating_setpoint", body_id, target)
        await self._confirm_body(body_id, "target_temperature", target, dispatched_at)

    async def set_heat_source(self, body_id: str, heater_id: str) -> None:
        if body_id not in BODY_IDS or heater_id not in HEATER_IDS:
            raise ValueError("invalid body or heat source")
        await self._send("request_changes", body_id, {HEATER_ATTR: heater_id})

    async def set_circuit(self, circuit_id: str, active: bool) -> None:
        if circuit_id not in CIRCUIT_IDS or type(active) is not bool:
            raise ValueError("invalid circuit or state")
        await self._send("set_circuit_state", circuit_id, active)

    async def set_light_effect(self, effect_code: str) -> None:
        from pyintellicenter import LIGHT_EFFECTS
        if effect_code not in LIGHT_EFFECTS:
            raise ValueError("unsupported IntelliBrite effect")
        await self._send("set_light_effect", "C0002", effect_code)

    async def set_chlorine(self, pool_percent: int, spa_percent: int | None = None) -> None:
        if type(pool_percent) is not int or not 0 <= pool_percent <= 100:
            raise ValueError("invalid Pool chlorine percentage")
        if spa_percent is not None and (
            type(spa_percent) is not int or not 0 <= spa_percent <= 100
        ):
            raise ValueError("invalid Spa chlorine percentage")
        args = ("CHR01", pool_percent) if spa_percent is None else (
            "CHR01", pool_percent, spa_percent
        )
        await self._send("set_chlorinator_output", *args)
