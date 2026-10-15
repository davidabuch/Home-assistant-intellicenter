"""Regression contract for the independently deployed HA sanitation outage guard."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTOMATION = ROOT / "ha_automations" / "sanitation_grid_outage_two_stage.yaml"

class SanitationOutageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = AUTOMATION.read_text()

    def test_early_shutdown_and_qualified_repeat(self):
        self.assertIn('for: "00:02:00"', self.text)
        self.assertIn("entity_id: binary_sensor.1_powerwall_grid_status", self.text)
        self.assertIn("entity_id: input_boolean.grid_outage_active", self.text)
        self.assertIn("id: qualified", self.text)

    def test_restart_reconciliation_and_no_resume(self):
        self.assertIn('minutes: "/1"', self.text)
        self.assertIn("id: attempted_restart", self.text)
        self.assertNotIn("switch.turn_on", self.text)
        self.assertNotIn("timer.start", self.text)
        self.assertNotIn("input_boolean.turn_on", self.text)

    def test_shutdown_clears_all_sanitation_ownership(self):
        for text in ("switch.turn_off", "switch.sanitation", "timer.cancel",
                     "timer.sanitation_session_limit", "input_boolean.pool_sanitation_session",
                     "input_boolean.spa_sanitation_session"):
            self.assertIn(text, self.text)

    def test_real_sensor_mode_and_fail_closed_unknown(self):
        self.assertIn("input_boolean.grid_outage_use_real_sensor", self.text)
        self.assertIn('state: "off"', self.text)
        self.assertIn("mode: restart", self.text)

if __name__ == "__main__":
    unittest.main()
