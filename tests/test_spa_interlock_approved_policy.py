"""Non-actuating contract tests for operator-approved unknown Spa state policy."""
from pathlib import Path
import unittest

TEXT = (Path(__file__).resolve().parents[1] / "docs" /
        "SPA_INTERLOCK_APPROVED_UNKNOWN_STATE_POLICY_2026-10-08.md")


class TestApprovedSpaFailSafe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = TEXT.read_text(encoding="utf-8")

    def test_explicit_unknown_unavailable_policy(self):
        for required in ("unknown", "unavailable", "both", "switch.turn_off"):
            with self.subTest(required=required):
                self.assertIn(required, self.policy)

    def test_existing_poolos_actuators_preserved(self):
        for entity in (
            "binary_sensor.poolos_native_intellicenter_spa_active",
            "switch.poolos_native_intellicenter_spillway",
            "switch.poolos_native_intellicenter_jets_bubbles",
        ):
            with self.subTest(entity=entity):
                self.assertIn(entity, self.policy)

    def test_unverified_deployment_not_claimed(self):
        self.assertIn("BLOCKED, NOT DEPLOYED", self.policy)
        self.assertIn("No commands from", self.policy)
        self.assertIn("stale-but-still", self.policy)


if __name__ == "__main__":
    unittest.main()
