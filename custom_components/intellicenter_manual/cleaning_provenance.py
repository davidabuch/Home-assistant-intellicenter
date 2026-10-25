"""Pure, read-only cleaning circulation provenance gate.

A native Pool ON observation alone never proves a cleaning-owned start.
This model does not send commands or grant control authority.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StartEvidence:
    episode: int
    cleaning_id: str
    command_id: str
    dispatch_acknowledged: bool
    dispatch_at: datetime
    native_pool_on_at: datetime
    native_cleaning_on: bool
    native_pool_on: bool
    native_spa_off: bool
    pump_rpm: int | None
    observation_fresh: bool
    exclusive_writer: bool
    manual_intent_excluded: bool
    uninterrupted_connection: bool


@dataclass(frozen=True)
class ClaimDecision:
    accepted: bool
    reason: str


def evaluate_start_claim(e: StartEvidence) -> ClaimDecision:
    """Require positive evidence; missing or ambiguous facts fail closed."""
    if e.episode <= 0 or e.cleaning_id != "FTR03" or not e.command_id:
        return ClaimDecision(False, "unidentified_episode_or_dispatch")
    if not e.dispatch_acknowledged:
        return ClaimDecision(False, "missing_dispatch_ack")
    if e.dispatch_at.tzinfo is None or e.native_pool_on_at.tzinfo is None:
        return ClaimDecision(False, "naive_timestamp")
    if not (0 <= (e.native_pool_on_at - e.dispatch_at).total_seconds() <= 120):
        return ClaimDecision(False, "unverified_native_chronology")
    if not (e.native_cleaning_on and e.native_pool_on and e.native_spa_off):
        return ClaimDecision(False, "native_state_not_verified")
    if e.pump_rpm is None or e.pump_rpm < 500:
        return ClaimDecision(False, "pump_not_running")
    if not e.observation_fresh or not e.uninterrupted_connection:
        return ClaimDecision(False, "native_continuity_lost")
    if not e.exclusive_writer:
        return ClaimDecision(False, "competing_writer_not_excluded")
    if not e.manual_intent_excluded:
        return ClaimDecision(False, "manual_intent_ambiguous")
    return ClaimDecision(True, "verified_start_claim")


def release_may_stop_pool(*, claim: ClaimDecision, independent_controller_authorized: bool,
                          manual_intent_excluded: bool, solar_or_filtration_needed: bool,
                          cleaning_off_confirmed: bool) -> ClaimDecision:
    """This is a *logical* gate only; no Pool OFF dispatcher exists."""
    if not claim.accepted:
        return ClaimDecision(False, "no_verified_claim")
    if not cleaning_off_confirmed:
        return ClaimDecision(False, "cleaning_release_unconfirmed")
    if not manual_intent_excluded:
        return ClaimDecision(False, "manual_intent_ambiguous")
    if not independent_controller_authorized:
        return ClaimDecision(False, "controller_arbitration_missing")
    if solar_or_filtration_needed:
        return ClaimDecision(False, "circulation_still_required")
    return ClaimDecision(True, "eligible_for_controller_reconciliation_only")
