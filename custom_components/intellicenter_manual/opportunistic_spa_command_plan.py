"""Command-free two-phase plan for opportunistic Spa Solar ownership.

This module intentionally does not import HA or call a service. The runtime
adapter must separately prove identity/provenance, serialize writers, and
read back each state. No plan step by itself authorizes physical actuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Step(str, Enum):
    CLAIM = "claim"
    SET_SOLAR = "set_solar"
    VERIFY_SOLAR = "verify_solar"
    START_SPA = "start_spa"
    VERIFY_SPA_ON = "verify_spa_on"
    COMMIT_RECEIPT = "commit_receipt"
    VERIFY_OWNER = "verify_owner"
    STOP_SPA = "stop_spa"
    VERIFY_SPA_OFF = "verify_spa_off"
    CLEAR_CLAIM = "clear_claim"
    REQUIRE_RECOVERY = "require_recovery"


@dataclass(frozen=True)
class Snapshot:
    # These attestations are inputs from a future trusted adapter, not HA state guesses.
    acquisition_gates_verified: bool = False
    no_competing_writer: bool = False
    claim_active: bool = False
    solar_source_verified: bool = False
    spa_on_verified: bool = False
    spa_off_verified: bool = False
    receipt_matches_current_epoch: bool = False
    manual_takeover: bool = False
    fresh_native_observation: bool = False


@dataclass(frozen=True)
class Plan:
    steps: tuple[Step, ...]
    reason: str


def acquisition_plan(s: Snapshot) -> Plan:
    """Sequential steps require a fresh gate check and readback at every edge."""
    if not (s.acquisition_gates_verified and s.no_competing_writer
            and s.fresh_native_observation and not s.manual_takeover):
        return Plan((), "acquisition denied")
    if not s.claim_active:
        return Plan((Step.CLAIM,), "claim first, then reobserve")
    if not s.solar_source_verified:
        return Plan((Step.SET_SOLAR, Step.VERIFY_SOLAR), "source must be Solar before Spa ON")
    if not s.spa_on_verified:
        return Plan((Step.START_SPA, Step.VERIFY_SPA_ON), "start Spa and prove readback")
    if not s.receipt_matches_current_epoch:
        return Plan((Step.COMMIT_RECEIPT,), "record verified epoch")
    return Plan((), "already acquired")


def release_plan(s: Snapshot) -> Plan:
    """Never command Spa OFF on stale, competing or unproven ownership."""
    if s.manual_takeover:
        return Plan((), "manual takeover; do not write")
    if not (s.fresh_native_observation and s.no_competing_writer
            and s.receipt_matches_current_epoch and s.claim_active):
        return Plan((Step.REQUIRE_RECOVERY,), "release ownership unproven; no Spa OFF")
    if not s.spa_off_verified:
        return Plan((Step.VERIFY_OWNER, Step.STOP_SPA, Step.VERIFY_SPA_OFF),
                    "stop only after owner recheck")
    return Plan((Step.CLEAR_CLAIM,), "Spa verified OFF; clear claim")
