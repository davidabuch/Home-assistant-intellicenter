"""Explicit manual-only IntelliCenter command gateway.

No scheduler, owner arbitration, PoolOS dependency, or autonomous commands.
This module must only be called by an explicit HA service/entity action.
"""
from __future__ import annotations

import asyncio
from typing import Any
from pyintellicenter import (
    ICConnectionHandler, ICModelController, PoolModel,
    STATUS_ATTR, STATUS_ON, STATUS_OFF, HEATER_ATTR,
)

BODY_IDS = frozenset({"B1101", "B1202"})
CIRCUIT_IDS = frozenset({"C0002", "C0003", "C0004", "FTR01"})
HEATER_IDS = frozenset({"00000", "H0001", "H0002"})


class ManualCommandError(RuntimeError):
    """Explicit command could not be dispatched."""


class IntelliCenterManualTransport:
    """Small allow-listed command interface; never makes autonomous decisions."""

    def __init__(self, host: str) -> None:
        if not host or not host.strip():
            raise ValueError("IntelliCenter host is required")
        self.model = PoolModel()
        self.controller = ICModelController(
            host.strip(), self.model, keepalive_interval=90.0, transport="tcp"
        )
        self.handler = ICConnectionHandler(self.controller, time_between_reconnects=30)
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.handler.start()
        self._started = True

    async def stop(self) -> None:
        self.handler.stop()
        try:
            await self.controller.stop()
        finally:
            self._started = False

    async def _send(self, method: str, *args: Any) -> Any:
        if not self._started:
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
