"""Stage B shadows: deterministic intent, never physical command authority."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/intellicenter_manual'
parent = types.ModuleType('shadow_test_pkg')
parent.__path__ = [str(ROOT)]
sys.modules[parent.__name__] = parent

def load(name):
    spec = importlib.util.spec_from_file_location(f'{parent.__name__}.{name}', ROOT / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m

m = load('cleaning_shadow')
Frame = sys.modules[f'{parent.__name__}.cleaning_observer'].Frame
StartEvidence = sys.modules[f'{parent.__name__}.cleaning_provenance'].StartEvidence
T = datetime(2026, 10, 24, tzinfo=timezone.utc)


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.shadow = m.CleaningShadow(enabled=True, boot_id='test')

    def frame(self, second=0, **changes):
        return Frame(T + timedelta(seconds=second), 'FTR03',
                     changes.pop('cleaning', False), changes.pop('pool', False),
                     changes.pop('spa', False), **changes)

    def authority(self, second, episode='test:1', **changes):
        return m.ControllerEvidence(episode_id=episode, observed_at=T + timedelta(seconds=second),
            **{'controller_authorized': True, 'exclusive_writer': True,
               'manual_intent_excluded': True, 'solar_needed': False,
               'filtration_needed': False, **changes})

    def see(self, second=0, *, authority=False, start=None, rpm=None, **changes):
        frame = self.frame(second, **changes)
        evidence = self.authority(second) if authority is True else (authority or None)
        return self.shadow.observe(frame, now=T + timedelta(seconds=second),
                                   controller=evidence, start=start, pump_rpm=rpm)

    def begin(self, **changes):
        self.see(pool=changes.get('pool', False))
        return self.see(1, cleaning=True, **changes)

    def no_commands(self, d):
        self.assertEqual(d.commands, ())
        self.assertFalse(d.command_authority)
        self.assertFalse(d.pool_off_eligible)
        self.assertFalse(d.bypass_manual_grace)
        self.assertEqual(d.claim, 'none')

    def test_default_off_even_with_hypothetically_complete_authority(self):
        self.shadow = m.CleaningShadow(boot_id='test')
        d = self.begin(authority=True)
        self.assertEqual(d.phase, 'disabled')
        self.assertEqual(d.would_action, 'none')
        self.no_commands(d)

    def test_idle_on_requires_affirmative_single_controller_attestation(self):
        d = self.begin()
        self.assertEqual(d.reason, 'controller_arbitration_missing')
        self.assertEqual(d.would_action, 'none')
        self.no_commands(d)

    def test_affirmative_shadow_only_request_is_considered_once(self):
        d = self.begin(authority=True)
        self.assertEqual(d.would_action, 'would_request_existing_controller_pool_on')
        self.no_commands(d)
        for second in (1, 2, 20, 40):
            d = self.see(second, cleaning=True, authority=True)
            self.assertEqual(d.would_action, 'none')
            self.no_commands(d)

    def test_already_running_pool_not_claimed(self):
        d = self.begin(pool=True, authority=True)
        self.assertEqual(d.reason, 'pool_already_on')
        self.no_commands(d)

    def test_native_timer_and_early_cancel_use_same_confirmed_handoff(self):
        for duration in (5, 10800):
            self.setUp()
            self.begin(authority=True)
            for second in range(60, duration, 60):
                self.see(second, cleaning=True)
            d = self.see(duration, authority=True)
            self.assertEqual(d.phase, 'release_pending')
            self.assertEqual(self.see(duration+19, authority=True).would_action, 'none')
            d = self.see(duration+20, authority=True)
            self.assertEqual(d.would_action, 'would_reconcile_existing_controller')
            self.no_commands(d)
            self.assertEqual(self.see(duration+21, authority=True).would_action, 'none')

    def test_reactivation_cancels_pending_release_and_changes_session(self):
        self.begin(authority=True)
        self.see(2)
        d = self.see(3, cleaning=True, authority=self.authority(3, episode='test:2'))
        self.assertEqual(d.episode_id, 'test:2')
        self.assertEqual(d.would_action, 'would_request_existing_controller_pool_on')
        self.assertNotEqual(d.phase, 'released')

    def test_manual_panel_on_during_cleaning_remains_unknown(self):
        self.begin(authority=True)
        d = self.see(2, cleaning=True, pool=True, rpm=3000, authority=True)
        self.assertEqual(d.reason, 'pool_on_does_not_prove_ownership')
        self.no_commands(d)
        self.assertEqual(self.shadow.events[-2]['origin'], 'unknown')
        self.assertFalse(self.shadow.events[-1]['physical_verification'])

    def test_manual_on_immediately_before_release_fails_closed(self):
        self.begin(authority=True)
        self.see(2, cleaning=True, pool=True)
        self.see(3, pool=True)
        d = self.see(23, pool=True, authority=True)
        self.assertEqual(d.reason, 'pool_on_does_not_prove_ownership')
        self.no_commands(d)

    def test_ha_redundant_on_intent_cancels_candidate_without_native_edge(self):
        self.begin(authority=True)
        self.shadow.pool_service_intent(active=True, at=T+timedelta(seconds=2))
        d = self.see(3, cleaning=True, authority=True)
        self.assertEqual(d.reason, 'competing_or_unknown_command_authority')
        self.no_commands(d)
        self.assertEqual(self.shadow.events[-1]['dispatch_ack'], 'not_observed')

    def test_panel_redundant_on_has_no_signal_so_no_exclusive_live_claim(self):
        self.begin(pool=True)
        d = self.see(2, cleaning=True, pool=True)
        self.no_commands(d)
        self.assertEqual(self.shadow.diagnostics(d)['manual_intent_excluded'], 'not_attested')

    def test_solar_and_filtration_and_grace_never_create_off_eligibility(self):
        for solar in (True, False):
            for debt in (True, False):
                for grace in (True, False, None):
                    self.setUp()
                    self.begin(authority=True)
                    self.see(2)
                    d = self.see(22, authority=self.authority(22, solar_needed=solar,
                        filtration_needed=debt, manual_grace_complete=grace))
                    self.no_commands(d)
                    self.assertEqual(d.would_action, 'would_reconcile_existing_controller')

    def test_unknown_demand_does_not_create_handoff_eligibility(self):
        self.begin(authority=True)
        self.see(2)
        d = self.see(22, authority=self.authority(22, solar_needed=None))
        self.assertEqual(d.reason, 'independent_demand_unknown')
        self.no_commands(d)

    def test_all_safety_preemptions_cancel_pending_proposal_until_new_activation(self):
        for reason in ('sanitation_priority', 'freeze_authority', 'grid_authority', 'service_mode',
                       'guardian_interlock', 'guardian_not_normal', 'auxiliary_demand',
                       'automatic_ownership_off', 'unknown_policy'):
            self.setUp()
            self.begin(authority=True)
            self.no_commands(self.see(2, cleaning=True, blockers=(reason,), authority=True))
            self.assertEqual(self.see(3, cleaning=True, authority=True).would_action, 'none')
            self.see(4)
            self.assertEqual(self.see(24, authority=True).would_action, 'none')

    def test_spa_activation_cancels_shadow_request(self):
        self.begin(authority=True)
        self.assertEqual(self.see(2, cleaning=True, spa=True).reason, 'spa_priority')
        d = self.see(3, cleaning=True, spa=False, authority=True)
        self.assertEqual(d.would_action, 'none')

    def test_restart_on_never_replays_activation_or_retains_flag(self):
        self.begin(authority=True)
        self.shadow = m.CleaningShadow(boot_id='restart')
        d = self.see(2, cleaning=True)
        self.assertEqual(d.phase, 'disabled')
        self.no_commands(d)
        self.shadow = m.CleaningShadow(enabled=True, boot_id='restart')
        d = self.see(2, cleaning=True, authority=self.authority(2, episode='restart:1'))
        self.assertEqual(d.reason, 'recovered_active_without_start_receipt')
        self.assertEqual(d.would_action, 'none')

    def test_disconnect_reconnect_discards_pending_work_and_claims(self):
        self.begin(authority=True)
        self.assertEqual(self.see(2, connected=False).phase, 'uncertain')
        d = self.see(3, cleaning=True, authority=True)
        self.assertEqual(d.reason, 'recovered_active_without_start_receipt')
        self.no_commands(d)

    def test_duplicate_cached_off_cannot_finish_release(self):
        self.begin(authority=True)
        self.see(2)
        d = self.shadow.observe(self.frame(2), now=T+timedelta(seconds=30), controller=self.authority(30))
        self.assertEqual(d.phase, 'release_pending')

    def test_stale_future_out_of_order_and_identity_changes_fail_closed(self):
        cases = [(self.frame(2, cleaning=True), 123), (self.frame(4, cleaning=True), 3),
                 (self.frame(0, cleaning=True), 2), (replace(self.frame(2), cleaning_id='FTR99'), 2)]
        for frame, second in cases:
            self.setUp()
            self.begin(authority=True)
            d = self.shadow.observe(frame, now=T+timedelta(seconds=second))
            self.assertEqual(d.phase, 'uncertain')
            self.no_commands(d)

    def test_authority_is_bound_to_episode_and_time(self):
        for evidence in (self.authority(1, episode='old:1'), self.authority(-1),
                         self.authority(2), self.authority(1, exclusive_writer=None),
                         self.authority(1, manual_intent_excluded=None),
                         self.authority(1, controller_authorized=False)):
            self.setUp()
            d = self.begin(authority=evidence)
            self.assertEqual(d.would_action, 'none')
            self.no_commands(d)

    def test_manual_pool_off_during_cleaning_never_restarts_it(self):
        self.begin(pool=True)
        d = self.see(2, cleaning=True, pool=False, authority=True)
        self.assertEqual(d.reason, 'pool_stopped_during_cleaning')
        for second in (3, 4, 5):
            self.no_commands(self.see(second, cleaning=True, authority=True))

    def test_missing_ack_or_delayed_start_evidence_is_not_ownership(self):
        self.begin(authority=True)
        values = dict(episode=1, cleaning_id='FTR03', command_id='example',
            dispatch_acknowledged=False, dispatch_at=T+timedelta(seconds=1),
            native_pool_on_at=T+timedelta(seconds=2), native_cleaning_on=True,
            native_pool_on=True, native_spa_off=True, pump_rpm=3000,
            observation_fresh=True, exclusive_writer=True, manual_intent_excluded=True,
            uninterrupted_connection=True)
        evidence = m.BoundStartEvidence('test:1', StartEvidence(**values))
        d = self.see(2, cleaning=True, pool=True, start=evidence)
        self.assertEqual(d.start_provenance, 'missing_dispatch_ack')
        self.no_commands(d)
        for invalid in (replace(evidence, episode_id='previous_boot:1'),
                        replace(evidence, evidence=replace(evidence.evidence, native_pool_on_at=T-timedelta(seconds=200))),
                        replace(evidence, evidence=replace(evidence.evidence, pump_rpm=float('nan')))):
            d = self.see(3, cleaning=True, pool=True, start=invalid)
            self.assertEqual(d.start_provenance, 'start_evidence_not_current_session')
            self.no_commands(d)

    def test_positive_logical_provenance_never_grants_exclusive_claim_or_off(self):
        self.begin(authority=True)
        start = StartEvidence(1, 'FTR03', 'simulated-command', True, T+timedelta(seconds=1),
            T+timedelta(seconds=2), True, True, True, 3000, True, True, True, True)
        d = self.see(2, cleaning=True, pool=True, start=m.BoundStartEvidence('test:1', start))
        self.assertEqual(d.start_provenance, 'verified_start_claim')
        self.no_commands(d)

    def test_bounded_evidence_and_no_new_events_for_steady_samples(self):
        self.begin()
        before = self.shadow.revision
        for second in range(2, 30):
            self.see(second, cleaning=True)
        self.assertEqual(self.shadow.revision, before)
        for i in range(100):
            self.shadow.pool_service_intent(active=True, at=T+timedelta(seconds=30+i))
        self.assertEqual(len(self.shadow.events), 16)
        self.assertNotIn('user_id', str(self.shadow.events))

    def test_same_receipt_contradiction_discards_session(self):
        self.begin(authority=True)
        d = self.shadow.observe(self.frame(1), now=T+timedelta(seconds=2))
        self.assertEqual(d.phase, 'uncertain')
        self.no_commands(d)

    def test_flag_has_no_live_enable_mutator(self):
        shadow = m.CleaningShadow()
        with self.assertRaises(AttributeError):
            shadow.enabled = True
        self.assertFalse(shadow.enabled)

    def test_simultaneous_pool_and_cleaning_activation_is_ambiguous(self):
        self.see()
        d = self.see(1, cleaning=True, pool=True, authority=True)
        self.assertEqual(d.reason, 'pool_on_does_not_prove_ownership')
        self.no_commands(d)
        event = next(e for e in self.shadow.events if e['kind'] == 'cleaning_on')
        self.assertFalse(event['pool_before'])
        self.assertTrue(event['pool_at_activation'])

    def test_post_release_manual_intent_not_misattributed_to_old_session(self):
        self.begin()
        self.see(2)
        self.see(22)
        self.shadow.pool_service_intent(active=True, at=T+timedelta(seconds=23))
        self.assertIsNone(self.shadow.events[-1]['episode_id'])


if __name__ == '__main__':
    unittest.main()
