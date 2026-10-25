"""Stage A command-intent scenarios: no equipment, helpers or events are written."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cleaning_stage_a', ROOT / 'custom_components/intellicenter_manual/cleaning_observer.py')
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
Frame, Observer = module.Frame, module.CleaningObserver
START = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


class CleaningObserverTests(unittest.TestCase):
    def setUp(self):
        self.observer = Observer()

    def frame(self, second=0, **kwargs):
        return Frame(observed_at=START + timedelta(seconds=second), cleaning_id='FTR03',
                     cleaning=False, pool=False, spa=False, **kwargs)

    def see(self, second=0, **changes):
        frame = replace(self.frame(second), **changes)
        return self.observer.observe(frame, now=START + timedelta(seconds=second))

    def begin(self, **changes):
        self.see()
        return self.see(1, cleaning=True, **changes)

    def release(self, **changes):
        self.see(2, **changes)
        return self.see(22, **changes)

    def test_idle_activation_proposes_existing_body_activation_without_claim(self):
        result = self.begin()
        self.assertEqual(result.action, 'would_request_pool_on')
        self.assertEqual(result.claim, 'none')
        self.assertEqual(result.proposed_claim, 'only_after_verified_pool_start')
        self.assertEqual(result.commands, ())

    def test_pool_already_on_is_never_claimed(self):
        result = self.begin(pool=True)
        self.assertEqual(result.action, 'none')
        self.assertEqual(result.reason, 'pool_already_on')
        self.assertEqual(result.claim, 'none')

    def test_spa_prevents_activation(self):
        result = self.begin(spa=True)
        self.assertEqual(result.reason, 'spa_priority')
        self.assertEqual(result.action, 'none')

    def test_duplicate_on_and_delayed_confirmation_do_not_create_new_proposals(self):
        first = self.begin()
        for second in (2, 10, 40):
            result = self.see(second, cleaning=True)
            self.assertEqual(result.activation_proposal, first.activation_proposal)
        result = self.see(41, cleaning=True, pool=True)
        self.assertEqual(result.reason, 'external_pool_activation')
        self.assertEqual(result.claim, 'none')
        self.assertEqual(result.action, 'none')

    def test_unfulfilled_proposal_does_not_retry_or_claim_success(self):
        first = self.begin()
        result = self.see(100, cleaning=True)
        self.assertEqual(first.activation_proposal, result.activation_proposal)
        self.assertEqual(result.claim, 'none')
        self.assertFalse(result.physically_verified)

    def test_manual_pool_off_during_cleaning_is_respected(self):
        self.begin(pool=True)
        result = self.see(2, cleaning=True)
        self.assertEqual(result.reason, 'pool_stopped_during_cleaning')
        self.assertEqual(result.action, 'none')
        self.assertEqual(self.see(3, cleaning=True).action, 'none')

    def test_release_requires_twenty_seconds_and_distinct_native_receipts(self):
        self.begin()
        self.assertEqual(self.see(2).action, 'none')
        self.assertEqual(self.see(21).action, 'none')
        result = self.see(22)
        self.assertEqual(result.action, 'would_reconcile_existing_controller')
        self.assertEqual(result.release_proposal, 1)
        self.assertEqual(self.see(23).release_proposal, 1)
        self.assertFalse(result.bypass_manual_grace)

    def test_cached_off_refresh_is_not_a_second_native_receipt(self):
        self.begin()
        frame = self.frame(2)
        self.observer.observe(frame, now=frame.observed_at)
        result = self.observer.observe(frame, now=START + timedelta(seconds=25))
        self.assertEqual(result.action, 'none')
        self.assertEqual(result.phase, 'release_pending')

    def test_early_cancellation_and_native_timer_use_same_release(self):
        for duration in (5, 10800):
            with self.subTest(duration=duration):
                self.observer = Observer()
                self.begin()
                # Continuous observations; no independent software session timer.
                for second in range(60, duration, 60):
                    self.see(second, cleaning=True)
                self.see(duration)
                result = self.see(duration + 20)
                self.assertEqual(result.action, 'would_reconcile_existing_controller')

    def test_off_on_race_cancels_old_release(self):
        self.begin()
        self.see(2)
        result = self.see(3, cleaning=True)
        self.assertEqual(result.phase, 'active')
        self.assertIsNone(result.release_proposal)
        self.assertEqual(result.activation_proposal, 2)
        self.assertEqual(self.see(22, cleaning=True).phase, 'active')

    def test_release_with_spa_has_no_normal_authority(self):
        self.begin()
        result = self.release(spa=True)
        self.assertEqual(result.reason, 'spa_priority')
        self.assertEqual(result.action, 'none')

    def test_release_never_claims_preexisting_or_externally_started_pool(self):
        for was_already_on in (True, False):
            with self.subTest(was_already_on=was_already_on):
                self.observer = Observer()
                self.begin(pool=was_already_on)
                if not was_already_on:
                    self.see(1.5, cleaning=True, pool=True)
                result = self.release(pool=True)
                self.assertEqual(result.action, 'would_reconcile_existing_controller')
                self.assertEqual(result.claim, 'none')
                self.assertFalse(result.bypass_manual_grace)
                self.assertEqual(result.commands, ())

    def test_restart_on_does_not_replay_start_or_invent_claim(self):
        result = self.see(cleaning=True)
        self.assertEqual(result.reason, 'recovered_active_without_start_receipt')
        self.assertEqual(result.action, 'none')
        self.assertEqual(self.see(1, cleaning=True).action, 'none')
        self.assertEqual(self.release().action, 'would_reconcile_existing_controller')

    def test_restart_after_release_does_not_replay_handoff(self):
        result = self.see()
        self.assertEqual(result.phase, 'idle')
        self.assertIsNone(result.release_proposal)
        self.assertEqual(self.see(30).action, 'none')

    def test_stale_unavailable_and_future_native_observations_fail_closed(self):
        for frame, now in (
            (replace(self.frame(), connected=False), START),
            (replace(self.frame(), cleaning=None), START),
            (replace(self.frame(), pool=None), START),
            (self.frame(), START + timedelta(seconds=121)),
            (self.frame(1), START),
        ):
            with self.subTest(frame=frame, now=now):
                self.begin()
                result = self.observer.observe(frame, now=now)
                self.assertEqual(result.phase, 'uncertain')
                self.assertEqual(result.action, 'none')

    def test_gap_during_release_cannot_confirm_off(self):
        self.begin()
        self.see(2)
        result = self.see(200)
        self.assertEqual(result.phase, 'idle')
        self.assertIsNone(result.release_proposal)

    def test_reconnect_on_does_not_restart_pool(self):
        self.begin()
        self.see(2, connected=False)
        result = self.see(3, cleaning=True)
        self.assertEqual(result.reason, 'recovered_active_without_start_receipt')
        self.assertEqual(result.action, 'none')

    def test_unknown_or_changed_native_identity_discards_continuity(self):
        self.begin()
        result = self.see(2, cleaning=True, cleaning_id='FTR99')
        self.assertEqual(result.action, 'none')
        self.assertEqual(result.reason, 'recovered_active_without_start_receipt')
        result = self.see(3, cleaning_id=None)
        self.assertEqual(result.phase, 'uncertain')

    def test_out_of_order_native_receipt_is_not_a_transition(self):
        self.begin()
        self.see(3, cleaning=True)
        result = self.observer.observe(self.frame(2), now=START + timedelta(seconds=4))
        self.assertEqual(result.phase, 'uncertain')
        self.assertEqual(result.action, 'none')

    def test_all_authority_suppressions_prevent_proposed_start_and_handoff(self):
        for reason in ('automatic_ownership_off', 'grid_authority', 'freeze_authority',
                       'service_mode', 'guardian_not_normal', 'sanitation_priority',
                       'auxiliary_demand', 'unknown_policy'):
            with self.subTest(reason=reason):
                self.observer = Observer()
                result = self.begin(blockers=(reason,))
                self.assertEqual(result.action, 'none')
                self.assertEqual(result.reason, reason)
                result = self.release(blockers=(reason,))
                self.assertEqual(result.action, 'none')
                self.assertEqual(result.commands, ())

    def test_blocked_activation_is_not_replayed_when_safety_clears(self):
        self.begin(blockers=('grid_authority',))
        result = self.see(2, cleaning=True)
        self.assertEqual(result.action, 'none')
        self.assertIsNone(result.activation_proposal)

    def test_policy_changes_do_not_count_as_native_off_confirmations(self):
        self.begin()
        frame = self.frame(2)
        self.observer.observe(frame, now=frame.observed_at)
        result = self.observer.observe(replace(frame, blockers=('grid_authority',)),
                                       now=START + timedelta(seconds=30))
        self.assertEqual(result.phase, 'release_pending')
        self.assertIsNone(result.release_proposal)

    def test_contradictory_same_receipt_fails_closed(self):
        self.begin()
        result = self.observer.observe(self.frame(1), now=START + timedelta(seconds=2))
        self.assertEqual(result.reason, 'contradictory_native_receipt')
        self.assertEqual(result.action, 'none')

    def test_clock_requires_aware_times(self):
        with self.assertRaises(ValueError):
            self.observer.observe(self.frame(), now=datetime(2026, 10, 24))


if __name__ == '__main__':
    unittest.main()
