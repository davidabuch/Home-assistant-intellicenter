"""Offline regression checks for documented Spa interlock migration gates.

No HA service calls or equipment actuation. These tests intentionally fail if
the audited evidence/required scenario matrix is silently weakened.
"""
from pathlib import Path
import unittest

DOC = (Path(__file__).resolve().parents[1] / "docs" /
       "SPA_INTERLOCK_STALE_TRUTH_AUDIT_2026-10-08.md")


class TestSpaInterlockAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = DOC.read_text(encoding="utf-8")

    def test_current_legacy_actuators_preserved(self):
        for entity in (
            "binary_sensor.poolos_native_intellicenter_spa_active",
            "switch.poolos_native_intellicenter_spillway",
            "switch.poolos_native_intellicenter_jets_bubbles",
        ):
            with self.subTest(entity=entity):
                self.assertIn(entity, self.contract)

    def test_stale_truth_scenarios_explicit(self):
        for scenario in ("unknown", "unavailable", "stale ON/OFF", "HA restart",
                         "ON→OFF", "OFF→ON"):
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, self.contract)

    def test_no_unsafe_automatic_migration(self):
        self.assertIn("allow_commands=False", self.contract)
        self.assertIn("No HomeKit entity/identity edits", self.contract)
        self.assertIn("no physical commands", self.contract)
        self.assertIn("no default branch", self.contract)


if __name__ == "__main__":
    unittest.main()
