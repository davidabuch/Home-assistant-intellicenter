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
    ICConnectionHandler, ICModelController, PoolModel,
    STATUS_ATTR, STATUS_ON, STATUS_OFF, HEATER_ATTR,
    BODY_TYPE, CIRCUIT_TYPE, SENSE_TYPE, PUMP_TYPE, SYSTEM_TYPE,
    LOTMP_ATTR, LSTTMP_ATTR, HTMODE_ATTR, SOURCE_ATTR,
    RPM_ATTR, GPM_ATTR, PWR_ATTR, MIN_ATTR, MAX_ATTR, VER_ATTR, SERVICE_ATTR,
    ALL_ATTRIBUTES_BY_TYPE, OBJTYP_ATTR, SNAME_ATTR, HITMP_ATTR, MODE_ATTR,
    VOL_ATTR, PARENT_ATTR, SUBTYP_ATTR,
)

BODY_IDS = frozenset({"B1101", "B1202"})
CIRCUIT_IDS = frozenset({"C0002", "C0003", "C0004", "FTR01"})
HEATER_IDS = frozenset({"00000", "H0001", "H0002"})


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
    """Hard protocol boundary: no mutation can cross during commissioning."""
    async def send_cmd(self, cmd, extra=None):
        if cmd not in {"GetParamList", "RequestParamList"}:
            raise ManualCommandError(f"Unsafe protocol operation blocked: {cmd}")
        return await super().send_cmd(cmd, extra)

    async def request_changes(self, objnam, changes):
        raise ManualCommandError("Physical writes disabled in commissioning controller")

    async def _queue_property_change(self, objnam, changes):
        raise ManualCommandError("Physical writes disabled in commissioning controller")


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

    @property
    def connected(self) -> bool:
        return self._connected and self._started

    def set_observation_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_observation = callback

    def _connection_changed(self, connected: bool) -> None:
        self._connected = connected
        # Connection establishment is not proof that a complete model was read.
        self._observed_at = None
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
                active = str(status).upper() != str(STATUS_OFF).upper()
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
                active = None if status is None else str(status).upper() != str(STATUS_OFF).upper()
                circuits.append(SimpleNamespace(id=str(obj.objnam), is_on=active))
            probe_keys = {'AIR': 'air_temperature', 'SOLAR': 'solar_temperature', 'POOL': 'water_temperature'}
            for obj in self.model.get_by_type(SENSE_TYPE):
                key = probe_keys.get(str(obj.subtype or '').upper())
                if key is not None and key not in telemetry:
                    telemetry[key] = obj.properties.get(SOURCE_ATTR)
            for obj in self.model.get_by_type(PUMP_TYPE):
                if 'pump_rpm' in telemetry:
                    break
                props = obj.properties
                telemetry.update(pump_rpm=props.get(RPM_ATTR),
                    pump_flow_rate=props.get(GPM_ATTR), pump_power=props.get(PWR_ATTR),
                    pump_minimum_rpm=props.get(MIN_ATTR), pump_maximum_rpm=props.get(MAX_ATTR))
            for obj in self.model.get_by_type(SYSTEM_TYPE):
                if 'firmware_version' in telemetry:
                    break
                telemetry.update(firmware_version=obj.properties.get(VER_ATTR),
                                 system_mode=obj.properties.get(SERVICE_ATTR))
        return adapt_snapshot(SimpleNamespace(
            connected=self.connected, observed_at=self._observed_at,
            bodies=bodies, circuits=circuits, telemetry=telemetry,
        ))

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
        self.handler.stop()
        try:
            await self.controller.stop()
        finally:
            self._started = False
            self._connected = False
            self._observed_at = None
            self._publish()

    async def _send(self, method: str, *args: Any) -> Any:
        if not self._allow_commands:
            raise ManualCommandError("Read-only commissioning: all physical commands are disabled")
        if not self.connected:
            raise ManualCommandError("IntelliCenter connection not started")
        async with self._lock:
            try:
                return await getattr(self.controller, method)(*args)
            except Exception as exc:
                raise ManualCommandError(f"{method} dispatch failed") from exc

    async def set_body_active(self, body_id: str, active: bool) -> None:
        if body_id not in BODY_IDS or type(active) is not bool:
            raise ValueError("invalid body or active state")
        await self._send(
            "request_changes", body_id,
            {STATUS_ATTR: STATUS_ON if active else STATUS_OFF},
        )

    async def set_target(self, body_id: str, fahrenheit: float) -> None:
        if body_id not in BODY_IDS or isinstance(fahrenheit, bool):
            raise ValueError("invalid body or target")
        target = round(float(fahrenheit))
        if not 40 <= target <= 104:
            raise ValueError("temperature outside safe range")
        await self._send("set_heating_setpoint", body_id, target)

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
