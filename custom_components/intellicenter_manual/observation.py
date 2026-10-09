"""Immutable, fail-closed native IntelliCenter read-model adapter.

Uses only documented snapshot-shaped attributes from the PoolOS-commissioned
pyintellicenter read model; never imports PoolOS or dispatches commands.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass(frozen=True)
class BodyObservation:
    native_id: str
    active: bool | None
    heating: bool | None
    current_temperature: float | None
    target_temperature: float | None
    heat_source: str | None

@dataclass(frozen=True)
class CircuitObservation:
    native_id: str
    active: bool | None
    effect_code: str | None = None

@dataclass(frozen=True)
class TelemetryObservation:
    key: str
    value: float | str | None

@dataclass(frozen=True)
class ReadObservation:
    connected: bool
    observed_at: datetime
    bodies: tuple[BodyObservation, ...]
    circuits: tuple[CircuitObservation, ...] = ()
    telemetry: tuple[TelemetryObservation, ...] = ()
    freeze_active: bool | None = None

    def heating_source_active(self, heater_id: str) -> bool | None:
        """Report actual native heating source; never equate selection with firing."""
        if not self.connected or heater_id not in {"H0001", "H0002"}:
            return None
        bodies = tuple(body for body in self.bodies if body.native_id in {"B1101", "B1202"})
        if {body.native_id for body in bodies} != {"B1101", "B1202"} or len(bodies) != 2 or any(body.heating is None for body in bodies):
            return None
        heating = tuple(body for body in bodies if body.heating)
        if not heating:
            return False
        if any(body.heat_source is None or body.heat_source not in {"H0001", "H0002"} for body in heating):
            return None
        return any(body.heat_source == heater_id for body in heating)

    def measurement(self, key: str) -> float | str | None:
        matches = [item.value for item in self.telemetry if item.key == key]
        return matches[0] if len(matches) == 1 else None

    def circuit(self, native_id: str) -> CircuitObservation | None:
        matches = [item for item in self.circuits if item.native_id == native_id]
        return matches[0] if len(matches) == 1 else None

    def body(self, native_id: str) -> BodyObservation | None:
        matches = [body for body in self.bodies if body.native_id == native_id]
        return matches[0] if len(matches) == 1 else None

def _boolean(value: Any) -> bool | None:
    return value if type(value) is bool else None

def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    import math
    return result if math.isfinite(result) else None

def adapt_snapshot(snapshot: Any, *, now: datetime | None = None) -> ReadObservation:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if snapshot is None:
        return ReadObservation(False, now, ())
    observed_at = getattr(snapshot, "observed_at", None)
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        return ReadObservation(False, now, ())
    age = (now - observed_at).total_seconds()
    if not 0 <= age <= 120 or getattr(snapshot, "connected", None) is not True:
        return ReadObservation(False, observed_at, ())
    bodies = []
    for item in getattr(snapshot, "bodies", ()):
        native_id = str(getattr(item, "id", ""))
        if native_id not in {"B1101", "B1202"}:
            continue
        source = getattr(item, "active_heat_source", None)
        bodies.append(BodyObservation(
            native_id=native_id,
            active=_boolean(getattr(item, "is_on", None)),
            heating=_boolean(getattr(item, "heating_active", None)),
            current_temperature=_number(getattr(item, "current_temperature", None)),
            target_temperature=_number(getattr(item, "target_temperature", None)),
            heat_source=None if source is None else str(getattr(source, "value", source)),
        ))
    circuits = []
    for item in getattr(snapshot, 'circuits', ()):
        native_id = str(getattr(item, 'id', ''))
        if native_id not in {'C0002', 'C0003', 'C0004', 'FTR01'}:
            continue
        raw_effect = getattr(item, 'effect_code', None)
        effect_code = raw_effect if isinstance(raw_effect, str) and raw_effect else None
        circuits.append(CircuitObservation(native_id, _boolean(getattr(item, 'is_on', None)), effect_code if native_id == 'C0002' else None))
    telemetry = []
    raw_telemetry = getattr(snapshot, 'telemetry', None)
    if not isinstance(raw_telemetry, dict):
        raw_telemetry = {}
    for key, raw in raw_telemetry.items():
        if key in {'air_temperature', 'solar_temperature', 'water_temperature',
                   'pump_rpm', 'pump_flow_rate', 'pump_power',
                   'pump_minimum_rpm', 'pump_maximum_rpm',
                   'intellichlor_pool_output', 'intellichlor_spa_output', 'intellichlor_salt'}:
            telemetry.append(TelemetryObservation(key, _number(raw)))
        elif key in {'firmware_version', 'system_mode'}:
            telemetry.append(TelemetryObservation(key, str(raw) if isinstance(raw, (str, int)) and not isinstance(raw, bool) else None))
    return ReadObservation(True, observed_at, tuple(bodies), tuple(circuits), tuple(telemetry),
                           _boolean(getattr(snapshot, "freeze_active", None)))
