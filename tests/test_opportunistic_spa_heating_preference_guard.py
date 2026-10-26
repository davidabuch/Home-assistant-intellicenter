"""Regression guard for existing heating-preference automation.

This validates repository JSON only. It does NOT prove a live HA automation
was updated or that the coordinator's ownership receipt is trustworthy.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUTOMATION = ROOT / "ha_automations" / "heating_preference.json"
CLAIM = "input_boolean.opportunistic_spa_session_claim"


class HeatingPreferenceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(AUTOMATION.read_text())

    def test_pool_path_remains_independent(self):
        pool = self.doc["actions"][0]
        self.assertEqual(pool["if"][0]["entity_id"], "input_boolean.pool_automatic_ownership")
        self.assertNotIn(CLAIM, json.dumps(pool))

    def test_spa_path_denies_all_preference_writes_while_claimed(self):
        spa = self.doc["actions"][1]
        self.assertEqual(spa["if"][0], {
            "condition": "state", "entity_id": CLAIM, "state": "off",
        })
        options = [item["sequence"][0]["data"]["option"] for item in spa["then"][-1]["choose"]]
        self.assertIn("Gas", options)
        self.assertIn("Solar", options)
        self.assertIn("Off", options)

    def test_guard_is_before_spa_source_choose(self):
        spa = self.doc["actions"][1]
        self.assertEqual(spa["if"][0]["condition"], "state")
        self.assertTrue(any("choose" in a for a in spa["then"]))


if __name__ == "__main__":
    unittest.main()
