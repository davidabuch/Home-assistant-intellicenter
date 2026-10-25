"""Default-OFF shadow arbitration and bounded, non-authoritative evidence.

No dispatcher, services, HA events, timers, storage or transport access exists.
Attestations are hypothetical inputs, not facts inferred from service contexts.
Even an accepted provenance-model result cannot grant Pool OFF eligibility.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from uuid import uuid4

from .cleaning_observer import CleaningObserver, Frame
from .cleaning_provenance import StartEvidence, evaluate_start_claim


@dataclass(frozen=True)
class ControllerEvidence:
    episode_id: str | None = None
    observed_at: datetime | None = None
    controller_authorized: bool | None = None
    exclusive_writer: bool | None = None
    manual_intent_excluded: bool | None = None
    solar_needed: bool | None = None
    filtration_needed: bool | None = None
    manual_grace_complete: bool | None = None


@dataclass(frozen=True)
class BoundStartEvidence:
    episode_id: str
    evidence: StartEvidence


@dataclass(frozen=True)
class ShadowDecision:
    phase: str
    reason: str
    episode_id: str | None = None
    would_action: str = 'none'
    start_provenance: str = 'not_observed'
    claim: str = 'none'
    pool_off_eligible: bool = False
    bypass_manual_grace: bool = False
    command_authority: bool = False
    commands: tuple = ()


class CleaningShadow:
    """In-memory commissioning model; a new instance always starts disabled.

    Tests may explicitly opt in at construction. There is no live enable method,
    saved flag, task or command sink. Each activation is considered once; lost
    authority/continuity cancels it until a new observed OFF -> ON episode.
    """

    def __init__(self, *, enabled=False, boot_id=None):
        self._enabled = enabled is True
        self._boot = boot_id or uuid4().hex
        self._number = 0
        self._observer = CleaningObserver()
        self._previous = None
        self._episode = None
        self._in_session = False
        self._considered = False
        self._released = False
        self._handoff_considered = False
        self._cancelled = None
        self._running_seen = False
        self._sequence = 0
        self._events = deque(maxlen=16)

    @property
    def enabled(self):
        return self._enabled

    @property
    def next_episode_id(self):
        return f'{self._boot}:{self._number + 1}'

    @property
    def events(self):
        return [dict(event) for event in self._events]

    @property
    def revision(self):
        return self._sequence

    def _note(self, kind, at, **fields):
        self._sequence += 1
        self._events.append(dict(sequence=self._sequence, kind=kind, at=at.isoformat(),
                                 **{'episode_id': self._episode, **fields}))

    def pool_service_intent(self, *, active: bool, at: datetime):
        """HA request observed, NOT dispatch ACK or native-panel attribution."""
        if type(active) is not bool or at.tzinfo is None:
            return
        self._note('ha_pool_service_intent', at, requested_active=active,
                   dispatch_ack='not_observed', origin='HA_service_actor_unattributed',
                   episode_id=self._episode if self._in_session else None)
        if self._in_session:
            self._cancelled = 'competing_or_unknown_command_authority'

    def _authority_reason(self, evidence, frame, now):
        if evidence is None or evidence.episode_id != self._episode:
            return 'controller_arbitration_missing'
        at = evidence.observed_at
        if at is None or at.tzinfo is None or not 0 <= (now - at).total_seconds() <= 120:
            return 'controller_evidence_stale'
        # Evidence preceding this native sample cannot authorize a later decision.
        if at < frame.observed_at:
            return 'controller_evidence_precedes_native_sample'
        for field, reason in (('controller_authorized', 'controller_arbitration_missing'),
                              ('exclusive_writer', 'competing_writer_not_excluded'),
                              ('manual_intent_excluded', 'manual_intent_ambiguous')):
            if getattr(evidence, field) is not True:
                return reason
        return None

    def observe(self, frame: Frame, *, now: datetime,
                controller: ControllerEvidence | None = None,
                start: BoundStartEvidence | None = None, pump_rpm=None) -> ShadowDecision:
        proposal = self._observer.observe(frame, now=now)
        previous = self._previous
        broken = proposal.phase == 'uncertain' or frame.cleaning_id != 'FTR03'
        if previous is not None:
            gap = (frame.observed_at - previous.observed_at).total_seconds()
            broken = broken or gap < 0 or gap > 120 or frame.cleaning_id != previous.cleaning_id
        if broken:
            if self._in_session:
                self._note('continuity_lost', now)
            self._episode = None
            self._in_session = False
            self._previous = None
            self._cancelled = 'native_continuity_lost'
            # Discard the observer episode too, including a pending OFF hold.
            self._observer = CleaningObserver()
            return ShadowDecision('uncertain' if self.enabled else 'disabled', 'native_continuity_lost')
        rising = frame.cleaning and (previous is None or previous.cleaning is False)
        if rising:
            self._episode = self.next_episode_id
            self._number += 1
            self._in_session = True
            self._considered = False
            self._released = False
            self._handoff_considered = False
            self._cancelled = None
            self._running_seen = False
            self._note('cleaning_on', frame.observed_at,
                       pool_before=None if previous is None else previous.pool,
                       pool_at_activation=frame.pool,
                       recovered=previous is None, native_ack_scope='global_model_snapshot')
        if self._in_session:
            if previous is not None and previous.pool != frame.pool:
                self._note('native_pool_transition', frame.observed_at, active=frame.pool,
                           origin='unknown', dispatch_ack='not_observed')
                self._cancelled = ('pool_stopped_during_cleaning' if not frame.pool
                                   else 'pool_on_does_not_prove_ownership')
            rpm_running = (frame.pool and type(pump_rpm) in (int, float)
                           and isfinite(pump_rpm) and pump_rpm >= 500)
            if rpm_running and not self._running_seen:
                self._running_seen = True
                self._note('motor_running_observed', frame.observed_at,
                           rpm=pump_rpm, attribution='unknown', physical_verification=False)
            if not frame.cleaning and previous is not None and previous.cleaning:
                self._note('cleaning_off', frame.observed_at)
        self._previous = frame
        if proposal.phase == 'released':
            self._in_session = False
            if not self._released:
                self._note('settled_release_candidate', frame.observed_at,
                           authority='existing_controller_only', pool_off_eligible=False)
                self._released = True
        if not self.enabled:
            return ShadowDecision('disabled', 'shadow_default_off', self._episode)
        if self._episode is None:
            return ShadowDecision('idle', 'no_session')
        provenance = 'not_observed'
        if start is not None:
            e = start.evidence
            if (start.episode_id != self._episode or e.episode != self._number
                    or e.cleaning_id != frame.cleaning_id
                    or e.dispatch_at.tzinfo is None or e.native_pool_on_at.tzinfo is None
                    or e.native_pool_on_at > frame.observed_at
                    or not 0 <= (now - e.native_pool_on_at).total_seconds() <= 120
                    or type(e.pump_rpm) not in (int, float) or not isfinite(e.pump_rpm)
                    or not frame.cleaning or not frame.pool or frame.spa):
                provenance = 'start_evidence_not_current_session'
            else:
                provenance = evaluate_start_claim(e).reason
        if frame.spa or frame.blockers:
            self._cancelled = 'spa_priority' if frame.spa else frame.blockers[0]
            return ShadowDecision(proposal.phase, self._cancelled, self._episode,
                                  start_provenance=provenance)
        if proposal.phase == 'release_pending':
            return ShadowDecision('release_pending', 'awaiting_confirmed_release', self._episode)
        if proposal.phase == 'released':
            if self._handoff_considered:
                return ShadowDecision('released', 'release_already_considered', self._episode)
            self._handoff_considered = True
            if self._cancelled:
                return ShadowDecision('released', self._cancelled, self._episode)
            reason = self._authority_reason(controller, frame, now)
            if reason:
                return ShadowDecision('released', reason, self._episode)
            if any(type(value) is not bool for value in (controller.solar_needed, controller.filtration_needed)):
                return ShadowDecision('released', 'independent_demand_unknown', self._episode)
            # Never invoke release_may_stop_pool: this increment prohibits OFF
            # even when its older pure logical gate could hypothetically accept.
            return ShadowDecision('released', 'preserve_controller_and_manual_grace', self._episode,
                                  would_action='would_reconcile_existing_controller')
        if self._cancelled:
            return ShadowDecision('active', self._cancelled, self._episode,
                                  start_provenance=provenance)
        if self._considered:
            return ShadowDecision('active', 'activation_already_considered', self._episode,
                                  start_provenance=provenance)
        self._considered = True
        if proposal.action != 'would_request_pool_on':
            self._cancelled = proposal.reason
            return ShadowDecision(proposal.phase, proposal.reason, self._episode,
                                  start_provenance=provenance)
        reason = self._authority_reason(controller, frame, now)
        if reason:
            self._cancelled = reason
            return ShadowDecision('active', reason, self._episode)
        return ShadowDecision('active', 'hypothetical_single_controller_request', self._episode,
                              would_action='would_request_existing_controller_pool_on')

    def diagnostics(self, decision):
        return {**asdict(decision), 'shadow_enabled': self.enabled, 'evidence': self.events,
                'dispatch_ack': 'not_observed', 'physical_verification': False,
                'exclusive_writer': 'not_attested', 'manual_intent_excluded': 'not_attested'}
