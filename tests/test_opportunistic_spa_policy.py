"""Deterministic no-hardware policy tests. No HA connection required."""
import unittest

import importlib.util
from pathlib import Path
import sys

POLICY_PATH = Path(__file__).resolve().parents[1] / 'custom_components' / 'intellicenter_manual' / 'opportunistic_spa_policy.py'
spec = importlib.util.spec_from_file_location('opportunistic_spa_policy', POLICY_PATH)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)
Decision, Observation, Phase, Session, evaluate = (policy.Decision, policy.Observation, policy.Phase, policy.Session, policy.evaluate)


def eligible(**kw):
    args = dict(
        feature_enabled=True, recovery_required=False, manual_lockout=False,
        telemetry_fresh=True, pool_off=True, spa_off=True,
        pool_demand=False, filtration_due=False, automatic_ownership=True,
        higher_priority_active=False, roof_f=135.0,
        native_spa_target_f=99.0, native_spa_source="Solar",
    )
    args.update(kw)
    return Observation(**args)


class TestOpportunisticSpaPolicy(unittest.TestCase):
    def test_disabled_default_fails_closed(self):
        result = evaluate(Session(), Observation(), 0)
        self.assertEqual(result.decision, Decision.YIELD_NO_WRITE)
        self.assertEqual(result.session.phase, Phase.RECOVERY_REQUIRED)

    def test_two_minute_qualification(self):
        a = evaluate(Session(Phase.IDLE), eligible(), 100)
        self.assertEqual(a.session.phase, Phase.SOLAR_QUALIFYING)
        self.assertEqual(evaluate(a.session, eligible(), 219).decision, Decision.NONE)
        self.assertEqual(evaluate(a.session, eligible(), 220).decision, Decision.ACQUIRE)

    def test_low_roof_blocks(self):
        self.assertEqual(evaluate(Session(), eligible(roof_f=129), 0).decision, Decision.NONE)

    def test_pool_and_safety_gates(self):
        for changes in (
            dict(pool_demand=True), dict(filtration_due=True),
            dict(higher_priority_active=True), dict(automatic_ownership=False),
            dict(pool_off=False), dict(spa_off=False), dict(telemetry_fresh=False),
            dict(native_spa_target_f=None), dict(roof_f=None),
        ):
            with self.subTest(changes=changes):
                self.assertEqual(evaluate(Session(), eligible(**changes), 0).decision, Decision.NONE)

    def test_solar_loss_and_recovery(self):
        owned = Session(Phase.OWNED, receipt_id="ack-1")
        o = eligible(spa_off=False, owned_receipt_verified=True, roof_f=115)
        first = evaluate(owned, o, 100)
        self.assertEqual(first.session.phase, Phase.SOLAR_RECOVERY)
        self.assertEqual(evaluate(first.session, o, 399).decision, Decision.MAINTAIN)
        self.assertEqual(evaluate(first.session, o, 400).decision, Decision.RELEASE_IF_OWNED)
        self.assertEqual(evaluate(first.session, eligible(spa_off=False, owned_receipt_verified=True, roof_f=121), 300).decision, Decision.MAINTAIN)

    def test_solar_only_and_priority_preemption(self):
        owned = Session(Phase.OWNED, receipt_id="ack-1")
        base = dict(spa_off=False, owned_receipt_verified=True)
        self.assertEqual(evaluate(owned, eligible(**base, native_spa_source="Gas"), 100).decision, Decision.RELEASE_IF_OWNED)
        self.assertEqual(evaluate(owned, eligible(**base, filtration_due=True), 100).decision, Decision.RELEASE_IF_OWNED)
        self.assertEqual(evaluate(owned, eligible(**base, pool_demand=True), 100).decision, Decision.RELEASE_IF_OWNED)

    def test_manual_override_yields_without_off(self):
        owned = Session(Phase.OWNED, receipt_id="ack-1")
        self.assertEqual(evaluate(owned, eligible(manual_override_seen=True), 100).decision, Decision.YIELD_NO_WRITE)

    def test_no_receipt_and_stale_observation_fail_closed(self):
        self.assertEqual(evaluate(Session(Phase.OWNED), eligible(), 100).decision, Decision.YIELD_NO_WRITE)
        self.assertEqual(evaluate(Session(Phase.OWNED, receipt_id="ack"), eligible(owned_receipt_verified=True, telemetry_fresh=False), 100).decision, Decision.YIELD_NO_WRITE)

    def test_restart_latch_blocks(self):
        self.assertEqual(evaluate(Session(Phase.OWNED, receipt_id="ack"), eligible(recovery_required=True), 100).decision, Decision.YIELD_NO_WRITE)

    def test_target_satisfaction_does_not_end_session(self):
        owned = Session(Phase.OWNED, receipt_id="ack")
        self.assertEqual(evaluate(owned, eligible(spa_off=False, owned_receipt_verified=True), 100).decision, Decision.MAINTAIN)


if __name__ == "__main__":
    unittest.main()
