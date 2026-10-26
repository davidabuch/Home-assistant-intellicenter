"""Observation-only opportunistic Spa coordinator for HA integration.

Not an actuator. It intentionally has no transport, HA service, or command
methods. Each HA reload starts with recovery required; a persisted claim
cannot establish physical ownership or bypass the disabled feature gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

from .opportunistic_spa_native_adapter import HASafety, adapt_native_spa
from .opportunistic_spa_policy import Decision, Outcome, Phase, Session, evaluate


@dataclass(frozen=True)
class ShadowReport:
    phase: Phase
    decision: Decision
    reason: str
    observed_at: datetime | None
    telemetry_fresh: bool


class SpaSolarShadowCoordinator:
    """Read-only native fanout subscriber; never executes policy intent."""

    def __init__(self, *, clock=time.monotonic, wall_clock=None):
        self._clock = clock
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._session = Session()
        self._closed = False
        self._report = ShadowReport(Phase.DISABLED, Decision.NONE, "not observed", None, False)

    @property
    def report(self) -> ShadowReport:
        return self._report

    def observe(self, native, *, safety: HASafety | None = None) -> ShadowReport:
        if self._closed:
            return self._report
        # A live caller may not enable acquisition through this shadow observer.
        # In particular, a restored HA helper is not a verified ownership receipt.
        requested = safety or HASafety()
        shadow_safety = HASafety(
            enabled=False,
            recovery_required=True,
            manual_lockout=True,
            pool_demand=requested.pool_demand,
            filtration_due=requested.filtration_due,
            automatic_ownership=False,
            higher_priority_active=True,
            owned_receipt_verified=False,
            manual_override_seen=requested.manual_override_seen,
        )
        obs = adapt_native_spa(native, shadow_safety, now=self._wall_clock())
        outcome: Outcome = evaluate(self._session, obs, self._clock())
        self._session = outcome.session
        self._report = ShadowReport(
            outcome.session.phase, outcome.decision, outcome.reason,
            getattr(native, "observed_at", None), obs.telemetry_fresh,
        )
        return self._report

    def close(self) -> None:
        self._closed = True
