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

@dataclass(frozen=True)
class ReadObservation:
    connected: bool
    observed_at: datetime
    bodies: tuple[BodyObservation, ...]
    circuits: tuple[CircuitObservation, ...] = ()

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
        circuits.append(CircuitObservation(native_id, _boolean(getattr(item, 'is_on', None))))
    return ReadObservation(True, observed_at, tuple(bodies), tuple(circuits))
