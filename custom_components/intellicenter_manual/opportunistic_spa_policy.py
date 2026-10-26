"""Pure fail-closed policy model for *future* opportunistic Spa Solar sessions.

This module has no Home Assistant, IntelliCenter, PWA or transport imports.
It does not grant physical command authority. A separate, tested HA coordinator
must prove provenance, recheck gates, and verify each native write.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    DISABLED = "disabled"
    IDLE = "idle"
    SOLAR_QUALIFYING = "solar_qualifying"
    READY = "ready"
    OWNED = "owned"
    SOLAR_RECOVERY = "solar_recovery"
    YIELDED = "yielded"
    RECOVERY_REQUIRED = "recovery_required"


class Decision(str, Enum):
    NONE = "none"
    ACQUIRE = "acquire"
    MAINTAIN = "maintain"
    RELEASE_IF_OWNED = "release_if_owned"
    YIELD_NO_WRITE = "yield_no_write"


@dataclass(frozen=True)
class Observation:
    feature_enabled: bool = False
    recovery_required: bool = True
    manual_lockout: bool = False
    telemetry_fresh: bool = False
    pool_off: bool = False
    spa_off: bool = False
    pool_demand: bool = True
    filtration_due: bool = True
    automatic_ownership: bool = False
    higher_priority_active: bool = True
    roof_f: float | None = None
    native_spa_source: str | None = None
    native_spa_target_f: float | None = None
    owned_receipt_verified: bool = False
    manual_override_seen: bool = False


@dataclass(frozen=True)
class Session:
    phase: Phase = Phase.DISABLED
    solar_qualified_since_s: float | None = None
    solar_lost_since_s: float | None = None
    receipt_id: str | None = None


@dataclass(frozen=True)
class Outcome:
    session: Session
    decision: Decision
    reason: str


def _safe_to_acquire(o: Observation) -> bool:
    return (
        o.feature_enabled and not o.recovery_required
        and not o.manual_lockout and o.telemetry_fresh
        and o.pool_off and o.spa_off and not o.pool_demand
        and not o.filtration_due and o.automatic_ownership
        and not o.higher_priority_active and not o.manual_override_seen
        and o.native_spa_target_f is not None
        and o.roof_f is not None
    )


def evaluate(session: Session, o: Observation, now_s: float) -> Outcome:
    """Decide *intent* only. Never actuate from this return value alone.

    Caller supplies monotonic seconds and trusted, freshly sampled observations.
    A receipt must be issued by an external command-acknowledgment coordinator,
    never synthesized by this policy.
    """
    if o.manual_override_seen or o.manual_lockout:
        return Outcome(Session(Phase.YIELDED), Decision.YIELD_NO_WRITE, "manual takeover")
    if o.recovery_required:
        return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "recovery required")
    if session.phase in (Phase.OWNED, Phase.SOLAR_RECOVERY):
        if not session.receipt_id or not o.owned_receipt_verified:
            return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "ownership unproven")
        if not o.telemetry_fresh:
            return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "stale telemetry")
        if (not o.feature_enabled or not o.automatic_ownership
                or o.higher_priority_active or o.pool_demand or o.filtration_due):
            return Outcome(session, Decision.RELEASE_IF_OWNED, "priority preemption")
        if o.spa_off:
            return Outcome(Session(Phase.YIELDED), Decision.YIELD_NO_WRITE, "Spa stopped externally; do not restart")
        if o.native_spa_source != "Solar":
            return Outcome(session, Decision.RELEASE_IF_OWNED, "non-Solar source")
        if o.roof_f is None:
            return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "roof unknown")
        if o.roof_f >= 120:
            return Outcome(Session(Phase.OWNED, receipt_id=session.receipt_id), Decision.MAINTAIN, "Solar viable")
        since = session.solar_lost_since_s if session.phase == Phase.SOLAR_RECOVERY else now_s
        if since is None or now_s < since:
            return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "clock invalid")
        if now_s - since >= 300:
            return Outcome(session, Decision.RELEASE_IF_OWNED, "Solar lost five minutes")
        return Outcome(Session(Phase.SOLAR_RECOVERY, solar_lost_since_s=since, receipt_id=session.receipt_id), Decision.MAINTAIN, "Solar recovery")
    if not o.feature_enabled:
        return Outcome(Session(Phase.DISABLED), Decision.NONE, "disabled")
    if not _safe_to_acquire(o):
        return Outcome(Session(Phase.IDLE), Decision.NONE, "acquisition blocked")
    if o.roof_f < 130:
        return Outcome(Session(Phase.IDLE), Decision.NONE, "roof below acquisition threshold")
    since = session.solar_qualified_since_s if session.phase == Phase.SOLAR_QUALIFYING else now_s
    if since is None or now_s < since:
        return Outcome(Session(Phase.RECOVERY_REQUIRED), Decision.YIELD_NO_WRITE, "clock invalid")
    if now_s - since < 120:
        return Outcome(Session(Phase.SOLAR_QUALIFYING, solar_qualified_since_s=since), Decision.NONE, "qualifying Solar")
    return Outcome(Session(Phase.READY), Decision.ACQUIRE, "eligible; external source readback and command verification required")
