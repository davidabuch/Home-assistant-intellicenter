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

    def test_circuit_state_and_ambiguous_id(self):
        a = SimpleNamespace(id='C0002', is_on=True)
        snapshot = SimpleNamespace(connected=True, observed_at=NOW, bodies=[], circuits=[a])
        result = module.adapt_snapshot(snapshot, now=NOW)
        self.assertTrue(result.circuit('C0002').active)
        self.assertIsNone(result.circuit('C0003'))
        snapshot.circuits = [a, a]
        self.assertIsNone(module.adapt_snapshot(snapshot, now=NOW).circuit('C0002'))

    def test_ambiguous_body_not_authoritative(self):
        body = SimpleNamespace(id="B1101", is_on=True)
        result = module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=NOW, bodies=[body,body]), now=NOW)
        self.assertIsNone(result.body("B1101"))

    def test_heating_source_requires_distinct_pool_and_spa(self):
        pool = SimpleNamespace(id="B1101", is_on=True, heating_active=True,
                               active_heat_source="H0002")
        spa = SimpleNamespace(id="B1202", is_on=False, heating_active=False,
                              active_heat_source="H0001")
        def observe(bodies):
            return module.adapt_snapshot(
                SimpleNamespace(connected=True, observed_at=NOW, bodies=bodies),
                now=NOW,
            )
        self.assertTrue(observe([pool, spa]).heating_source_active("H0002"))
        self.assertFalse(observe([pool, spa]).heating_source_active("H0001"))
        self.assertIsNone(observe([pool, pool]).heating_source_active("H0002"))
        self.assertIsNone(observe([spa, spa]).heating_source_active("H0001"))
        self.assertIsNone(observe([pool]).heating_source_active("H0002"))

    def test_selected_heater_is_not_proof_of_active_heat(self):
        # HEATER is selected even while both bodies are idle.
        pool = SimpleNamespace(id="B1101", is_on=True, heating_active=False,
                               active_heat_source="H0002")
        spa = SimpleNamespace(id="B1202", is_on=False, heating_active=False,
                              active_heat_source="H0001")
        observed = module.adapt_snapshot(
            SimpleNamespace(connected=True, observed_at=NOW,
                            bodies=[pool, spa]), now=NOW)
        self.assertFalse(observed.heating_source_active("H0002"))
        self.assertFalse(observed.heating_source_active("H0001"))

    def test_active_heating_with_ambiguous_source_fails_closed(self):
        pool = SimpleNamespace(id="B1101", is_on=True, heating_active=True,
                               active_heat_source="unknown")
        spa = SimpleNamespace(id="B1202", is_on=False, heating_active=False,
                              active_heat_source="H0001")
        observed = module.adapt_snapshot(
            SimpleNamespace(connected=True, observed_at=NOW,
                            bodies=[pool, spa]), now=NOW)
        self.assertIsNone(observed.heating_source_active("H0001"))
        self.assertIsNone(observed.heating_source_active("H0002"))

    def test_unknown_heating_state_cannot_assert_heater_off(self):
        pool = SimpleNamespace(id="B1101", is_on=True, heating_active=None,
                               active_heat_source="H0002")
        spa = SimpleNamespace(id="B1202", is_on=False, heating_active=False,
                              active_heat_source="H0001")
        observed = module.adapt_snapshot(
            SimpleNamespace(connected=True, observed_at=NOW,
                            bodies=[pool, spa]), now=NOW)
        self.assertIsNone(observed.heating_source_active("H0001"))
        self.assertIsNone(observed.heating_source_active("H0002"))

    def test_freeze_observation_is_explicit_and_fail_closed(self):
        def observe(value, *, connected=True, observed_at=NOW):
            return module.adapt_snapshot(SimpleNamespace(
                connected=connected, observed_at=observed_at, bodies=[],
                freeze_active=value), now=NOW)
        self.assertTrue(observe(True).freeze_active)
        self.assertIs(observe(False).freeze_active, False)
        for value in (None, "OFF", 0, 1, [], {}):
            self.assertIsNone(observe(value).freeze_active)
        self.assertIsNone(observe(True, connected=False).freeze_active)
        self.assertIsNone(observe(True, observed_at=NOW-timedelta(seconds=121)).freeze_active)

    def test_freeze_absent_from_snapshot_is_unknown(self):
        observation = module.adapt_snapshot(SimpleNamespace(
            connected=True, observed_at=NOW, bodies=[]), now=NOW)
        self.assertIsNone(observation.freeze_active)

    def test_malformed_telemetry_is_unknown_not_exception(self):
        for malformed in (None, [], "bad", 42):
            observation = module.adapt_snapshot(
                SimpleNamespace(connected=True, observed_at=NOW, bodies=[],
                                telemetry=malformed), now=NOW)
            self.assertTrue(observation.connected)
            self.assertIsNone(observation.measurement("pump_rpm"))

    def test_invalid_system_mode_and_firmware_not_promoted_to_truth(self):
        observation = module.adapt_snapshot(
            SimpleNamespace(connected=True, observed_at=NOW, bodies=[],
                            telemetry={"system_mode": True,
                                       "firmware_version": {"invalid": 1},
                                       "pump_rpm": float("inf"),
                                       "solar_temperature": "91.5"}),
            now=NOW)
        self.assertIsNone(observation.measurement("system_mode"))
        self.assertIsNone(observation.measurement("firmware_version"))
        self.assertIsNone(observation.measurement("pump_rpm"))
        self.assertEqual(observation.measurement("solar_temperature"), 91.5)

    def test_missing_and_invalid_observation_not_inferred(self):
        body = SimpleNamespace(id="B1202", is_on="ON", current_temperature=float("nan"))
        result = module.adapt_snapshot(SimpleNamespace(connected=True, observed_at=NOW, bodies=[body]), now=NOW)
        self.assertIsNone(result.body("B1202").active)
        self.assertIsNone(result.body("B1202").current_temperature)

if __name__ == "__main__":
    unittest.main()
