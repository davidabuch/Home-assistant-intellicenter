"""Read-model safety regression tests without Home Assistant dependencies."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys

path = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual/observation.py"
spec = importlib.util.spec_from_file_location("ic_observation", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

NOW = datetime(2026, 10, 8, 18, 0, tzinfo=timezone.utc)

class ObservationTests(unittest.TestCase):
    def test_none_and_disconnected_fail_closed(self):
        self.assertFalse(module.adapt_snapshot(None, now=NOW).connected)
        self.assertFalse(module.adapt_snapshot(SimpleNamespace(connected=False, observed_at=NOW, bodies=[]), now=NOW).connected)

    def test_stale_and_future_fail_closed(self):
        for dt in (NOW-timedelta(seconds=121), NOW+timedelta(seconds=1)):
            self.assertFalse(module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=dt, bodies=[]), now=NOW).connected)

    def test_valid_body(self):
        body = SimpleNamespace(id="B1101", is_on=True, heating_active=False, current_temperature=84, target_temperature=90, active_heat_source="H0002")
        result = module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=NOW, bodies=[body]), now=NOW)
        self.assertTrue(result.connected)
        self.assertEqual(result.body("B1101").target_temperature, 90)
        self.assertIsNone(result.body("B1202"))

    def test_ambiguous_body_not_authoritative(self):
        body = SimpleNamespace(id="B1101", is_on=True)
        result = module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=NOW, bodies=[body,body]), now=NOW)
        self.assertIsNone(result.body("B1101"))

    def test_missing_and_invalid_observation_not_inferred(self):
        body = SimpleNamespace(id="B1202", is_on="ON", current_temperature=float("nan"))
        result = module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=NOW, bodies=[body]), now=NOW)
        self.assertIsNone(result.body("B1202").active)
        self.assertIsNone(result.body("B1202").current_temperature)

if __name__ == "__main__":
    unittest.main()
