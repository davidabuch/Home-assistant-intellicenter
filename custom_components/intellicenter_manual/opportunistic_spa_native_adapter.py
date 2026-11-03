"""Read-only native-to-policy Spa snapshot adapter.

Accepts the existing immutable ReadObservation and an explicitly supplied
Home Assistant policy snapshot. No HA imports, service calls or writes.
Unknown native body identity, age, temperature, or heat source fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math

from .opportunistic_spa_policy import Observation


@dataclass(frozen=True)
class HASafety:
    enabled: bool = False
    recovery_required: bool = True
    manual_lockout: bool = True
    pool_demand: bool = True
    filtration_due: bool = True
    automatic_ownership: bool = False
    higher_priority_active: bool = True
    owned_receipt_verified: bool = False
    manual_override_seen: bool = False


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def adapt_native_spa(
    native: object,
    safety: HASafety,
    *,
    now: datetime | None = None,
    max_age_s: float = 30.0,
) -> Observation:
    """Read-only adapter; do not infer Pool demand or manual intent from bodies."""
    if now is None:
        now = datetime.now(timezone.utc)
    observed_at = getattr(native, "observed_at", None)
    connected = getattr(native, "connected", False) is True
    age_ok = False
    if (connected and isinstance(observed_at, datetime)
            and observed_at.tzinfo is not None and now.tzinfo is not None):
        age = (now - observed_at).total_seconds()
        age_ok = 0 <= age <= max_age_s
    pool = native.body("B1101") if age_ok else None
    spa = native.body("B1202") if age_ok else None
    roof = _finite(native.measurement("solar_temperature")) if age_ok else None
    target = _finite(getattr(spa, "target_temperature", None))
    source = getattr(spa, "heat_source", None)
    source = {"H0002": "Solar", "H0001": "Gas", "00000": "Off"}.get(source)
    complete = (
        age_ok and pool is not None and spa is not None
        and type(pool.active) is bool and type(spa.active) is bool
        and roof is not None and target is not None
        and source is not None
    )
    return Observation(
        feature_enabled=safety.enabled,
        recovery_required=safety.recovery_required,
        manual_lockout=safety.manual_lockout,
        telemetry_fresh=bool(complete),
        pool_off=pool.active is False if pool is not None else False,
        spa_off=spa.active is False if spa is not None else False,
        pool_demand=safety.pool_demand,
        filtration_due=safety.filtration_due,
        automatic_ownership=safety.automatic_ownership,
        higher_priority_active=safety.higher_priority_active,
        roof_f=roof,
        native_spa_source=source,
        native_spa_target_f=target,
        owned_receipt_verified=safety.owned_receipt_verified,
        manual_override_seen=safety.manual_override_seen,
    )
