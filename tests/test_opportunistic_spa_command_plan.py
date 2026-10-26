"""No hardware: prove the command planner never issues unsafe intent."""
import importlib.util
from pathlib import Path
import sys
import unittest

p = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual" / "opportunistic_spa_command_plan.py"
spec = importlib.util.spec_from_file_location("opportunistic_spa_command_plan", p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class CommandPlanTests(unittest.TestCase):
    def test_acquisition_denied_by_default(self):
        self.assertEqual(m.acquisition_plan(m.Snapshot()).steps, ())

    def test_claim_before_source_before_start_before_receipt(self):
        s = dict(acquisition_gates_verified=True, no_competing_writer=True, fresh_native_observation=True)
        self.assertEqual(m.acquisition_plan(m.Snapshot(**s)).steps, (m.Step.CLAIM,))
        s["claim_active"] = True
        self.assertEqual(m.acquisition_plan(m.Snapshot(**s)).steps, (m.Step.SET_SOLAR, m.Step.VERIFY_SOLAR))
        s["solar_source_verified"] = True
        self.assertEqual(m.acquisition_plan(m.Snapshot(**s)).steps, (m.Step.START_SPA, m.Step.VERIFY_SPA_ON))
        s["spa_on_verified"] = True
        self.assertEqual(m.acquisition_plan(m.Snapshot(**s)).steps, (m.Step.COMMIT_RECEIPT,))
        s["receipt_matches_current_epoch"] = True
        self.assertEqual(m.acquisition_plan(m.Snapshot(**s)).steps, ())

    def test_release_denies_unverified_and_manual(self):
        for s in (m.Snapshot(), m.Snapshot(manual_takeover=True),
                  m.Snapshot(claim_active=True, receipt_matches_current_epoch=True)):
            self.assertNotIn(m.Step.STOP_SPA, m.release_plan(s).steps)

    def test_release_requires_readback_and_epoch(self):
        s = m.Snapshot(claim_active=True, receipt_matches_current_epoch=True,
                       no_competing_writer=True, fresh_native_observation=True)
        self.assertEqual(m.release_plan(s).steps,
                         (m.Step.VERIFY_OWNER, m.Step.STOP_SPA, m.Step.VERIFY_SPA_OFF))
        s = m.Snapshot(claim_active=True, receipt_matches_current_epoch=True,
                       no_competing_writer=True, fresh_native_observation=True, spa_off_verified=True)
        self.assertEqual(m.release_plan(s).steps, (m.Step.CLEAR_CLAIM,))


if __name__ == "__main__":
    unittest.main()
