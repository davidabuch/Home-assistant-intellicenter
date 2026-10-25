"""Stage B provenance logic regression tests; no HA or physical commands."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual/cleaning_provenance.py"
spec = importlib.util.spec_from_file_location("cleaning_provenance", PATH)
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.t = datetime(2026, 10, 24, tzinfo=timezone.utc)
        self.good = dict(episode=1, cleaning_id="FTR03", command_id="dispatch-1",
                         dispatch_acknowledged=True, dispatch_at=self.t,
                         native_pool_on_at=self.t + timedelta(seconds=2),
                         native_cleaning_on=True, native_pool_on=True,
                         native_spa_off=True, pump_rpm=3000, observation_fresh=True,
                         exclusive_writer=True, manual_intent_excluded=True,
                         uninterrupted_connection=True)

    def test_complete_provenance_only(self):
        self.assertTrue(module.evaluate_start_claim(module.StartEvidence(**self.good)).accepted)

    def test_all_ambiguous_evidence_fails_closed(self):
        failures = dict(episode=0, cleaning_id="FTR02", command_id="",
                        dispatch_acknowledged=False, native_pool_on=False,
                        native_cleaning_on=False, native_spa_off=False, pump_rpm=0,
                        observation_fresh=False, exclusive_writer=False,
                        manual_intent_excluded=False, uninterrupted_connection=False,
                        native_pool_on_at=self.t - timedelta(seconds=1))
        for key, value in failures.items():
            with self.subTest(key=key):
                values = {**self.good, key: value}
                self.assertFalse(module.evaluate_start_claim(module.StartEvidence(**values)).accepted)

    def test_reconnect_and_manual_panel_on_never_prove_ownership(self):
        for values in ({"uninterrupted_connection": False},
                       {"manual_intent_excluded": False},
                       {"dispatch_acknowledged": False}):
            self.assertFalse(module.evaluate_start_claim(
                module.StartEvidence(**{**self.good, **values})).accepted)

    def test_release_never_overrides_independent_demand_or_manual_intent(self):
        claim = module.evaluate_start_claim(module.StartEvidence(**self.good))
        base = dict(claim=claim, independent_controller_authorized=True,
                    manual_intent_excluded=True, solar_or_filtration_needed=False,
                    cleaning_off_confirmed=True)
        self.assertTrue(module.release_may_stop_pool(**base).accepted)
        for key, value in (("independent_controller_authorized", False),
                           ("manual_intent_excluded", False),
                           ("solar_or_filtration_needed", True),
                           ("cleaning_off_confirmed", False),
                           ("claim", module.ClaimDecision(False, "ambiguous"))):
            with self.subTest(key=key):
                self.assertFalse(module.release_may_stop_pool(**{**base, key: value}).accepted)


if __name__ == "__main__":
    unittest.main()
