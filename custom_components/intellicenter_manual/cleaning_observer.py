"""Stage A only: describe cleaning handoff intent without acquiring authority.

No writer, timer, HA event, helper, recovery journal or command callback exists
here. A proposal is NOT a dispatch receipt. In particular, a subsequent Pool ON
observation cannot establish that cleaning initiated that circulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Frame:
    observed_at: datetime
    cleaning_id: str | None
    cleaning: bool | None
    pool: bool | None
    spa: bool | None
    connected: bool = True
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Proposal:
    phase: str
    action: str
    reason: str
    activation_proposal: int | None = None
    release_proposal: int | None = None
    claim: str = 'none'
    proposed_claim: str = 'none'
    physically_verified: bool = False
    bypass_manual_grace: bool = False
    commands: tuple = ()


class CleaningObserver:
    """Volatile observation continuity; deliberately no persistent ownership.

    Startup/reconnect ON is recovered, never a new start request. OFF continuity
    needs two distinct native receipts spanning 20 seconds. Cache refreshes do
    not count. A gap, identity change, unknown or backwards time abandons the
    old episode; recovering OFF never replays an old release.
    """

    def __init__(self):
        self._last: Frame | None = None
        self._session = 0
        self._activation = None
        self._release = None
        self._off_since = None
        self._off_receipts = 0
        self._active_reason = 'not_observed'

    def _forget(self):
        self._last = None
        self._activation = None
        self._release = None
        self._off_since = None
        self._off_receipts = 0

    def observe(self, frame: Frame, *, now: datetime) -> Proposal:
        if now.tzinfo is None or frame.observed_at.tzinfo is None:
            raise ValueError('Observation and evaluation times must be timezone-aware')
        age = (now - frame.observed_at).total_seconds()
        valid = (frame.connected is True and 0 <= age <= 120
                 and bool(frame.cleaning_id)
                 and all(type(v) is bool for v in (frame.cleaning, frame.pool, frame.spa)))
        if not valid:
            self._forget()
            return Proposal('uncertain', 'none', 'native_observation_untrusted')
        previous = self._last
        if previous is not None:
            delta = (frame.observed_at - previous.observed_at).total_seconds()
            if delta < 0:
                self._forget()
                return Proposal('uncertain', 'none', 'native_time_went_backwards')
            # A different value under the same receipt is contradictory, not an edge.
            if delta == 0 and (frame.cleaning, frame.pool, frame.spa) != (
                    previous.cleaning, previous.pool, previous.spa):
                self._forget()
                return Proposal('uncertain', 'none', 'contradictory_native_receipt')
            if delta > 120 or frame.cleaning_id != previous.cleaning_id:
                self._forget()
                previous = None
        distinct = previous is None or frame.observed_at > previous.observed_at
        new_on = frame.cleaning and (previous is None or not previous.cleaning)
        if new_on:
            self._session += 1
            self._off_since = None
            self._off_receipts = 0
            self._release = None
            self._activation = None
            if previous is None:
                self._active_reason = 'recovered_active_without_start_receipt'
            elif frame.spa:
                self._active_reason = 'spa_priority'
            elif frame.blockers:
                self._active_reason = frame.blockers[0]
            elif frame.pool:
                self._active_reason = 'pool_already_on'
            else:
                self._active_reason = 'idle_pool_activation_candidate'
                self._activation = self._session
        elif frame.cleaning and previous is not None:
            if previous.pool and not frame.pool:
                self._active_reason = 'pool_stopped_during_cleaning'
                self._activation = None
            elif frame.pool and self._activation is not None:
                # Stage A did not dispatch anything; this is somebody else's ON.
                self._active_reason = 'external_pool_activation'
                self._activation = None
            if frame.spa or frame.blockers:
                # Do not replay a blocked proposal after authority changes.
                if self._activation is not None:
                    self._active_reason = 'activation_cancelled_by_authority_change'
                self._activation = None
        if not frame.cleaning:
            if previous is not None and previous.cleaning:
                self._off_since = frame.observed_at
                self._off_receipts = 1
                self._activation = None
            elif self._off_since is not None and distinct:
                self._off_receipts += 1
            if (self._off_since is not None and self._off_receipts >= 2
                    and (frame.observed_at - self._off_since).total_seconds() >= 20):
                self._release = self._session
        self._last = frame
        if frame.cleaning:
            phase = 'active'
            action = 'would_request_pool_on' if self._activation is not None else 'none'
            reason = self._active_reason
        elif self._release is not None:
            phase, action, reason = ('released', 'would_reconcile_existing_controller',
                                     'confirmed_release_no_cleaning_circulation_claim')
        elif self._off_since is not None:
            phase, action, reason = 'release_pending', 'none', 'awaiting_consecutive_off_receipts'
        else:
            phase, action, reason = 'idle', 'none', 'no_observed_session_to_release'
        if frame.spa:
            action, reason = 'none', 'spa_priority'
        elif frame.blockers:
            action, reason = 'none', frame.blockers[0]
        return Proposal(phase, action, reason, self._activation, self._release,
                        proposed_claim=('only_after_verified_pool_start'
                                        if action == 'would_request_pool_on' else 'none'))
