"""Offline regression coverage for read-only cutover observation semantics.

These tests never import Home Assistant, open sockets, or issue commands.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"
PKG = "consumer_regression_pkg"
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, package)
spec = importlib.util.spec_from_file_location(PKG + ".observation", ROOT / "observation.py")
observation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = observation
spec.loader.exec_module(observation)


def body(id, *, active, heating, current, target, source):
    return types.SimpleNamespace(
        id=id, is_on=active, heating_active=heating,
        current_temperature=current, target_temperature=target,
        active_heat_source=source,
    )


def snapshot(now, *, connected=True, age=0, pool=None, spa=None, circuit=None):
    return types.SimpleNamespace(
        connected=connected,
        observed_at=now - timedelta(seconds=age),
        bodies=[pool, spa] if pool is not None and spa is not None else [],
        circuits=[circuit] if circuit is not None else [],
        telemetry={},
    )


class ConsumerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 9, 2, 38, tzinfo=timezone.utc)

    def test_spa_gauge_session_truth_and_target_attributes(self):
        spa = body("B1202", active=True, heating=True, current=84, target=98, source="H0001")
        pool = body("B1101", active=False, heating=False, current=84, target=90, source="H0002")
        observed = observation.adapt_snapshot(snapshot(self.now, pool=pool, spa=spa), now=self.now)
        self.assertTrue(observed.body("B1202").active)
        self.assertTrue(observed.body("B1202").heating)
        self.assertEqual(observed.body("B1202").current_temperature, 84)
        self.assertEqual(observed.body("B1202").target_temperature, 98)
        self.assertFalse(observed.body("B1101").active)

    def test_native_solar_selected_is_not_active_heating(self):
        pool = body("B1101", active=True, heating=False, current=84, target=90, source="H0002")
        spa = body("B1202", active=False, heating=False, current=84, target=98, source=None)
        observed = observation.adapt_snapshot(snapshot(self.now, pool=pool, spa=spa), now=self.now)
        self.assertEqual(observed.body("B1101").heat_source, "H0002")
        self.assertFalse(observed.body("B1101").heating)
        self.assertFalse(observed.heating_source_active("H0002"))
        self.assertFalse(observed.heating_source_active("H0001"))

    def test_gas_delivery_not_inferred_from_selected_heater(self):
        pool = body("B1101", active=True, heating=True, current=84, target=90, source="H0001")
        spa = body("B1202", active=False, heating=False, current=84, target=98, source="H0001")
        observed = observation.adapt_snapshot(snapshot(self.now, pool=pool, spa=spa), now=self.now)
        self.assertTrue(observed.heating_source_active("H0001"))
        self.assertFalse(observed.heating_source_active("H0002"))
        pool.heating_active = False
        observed = observation.adapt_snapshot(snapshot(self.now, pool=pool, spa=spa), now=self.now)
        self.assertFalse(observed.heating_source_active("H0001"))

    def test_stale_disconnected_and_incomplete_observations_fail_closed(self):
        pool = body("B1101", active=True, heating=True, current=84, target=90, source="H0001")
        spa = body("B1202", active=False, heating=False, current=84, target=98, source=None)
        for kwargs in ({"age": 121}, {"connected": False}):
            with self.subTest(kwargs=kwargs):
                observed = observation.adapt_snapshot(
                    snapshot(self.now, pool=pool, spa=spa, **kwargs), now=self.now)
                self.assertFalse(observed.connected)
                self.assertIsNone(observed.heating_source_active("H0001"))
        incomplete = types.SimpleNamespace(
            connected=True, observed_at=self.now, bodies=[pool], circuits=[], telemetry={})
        self.assertIsNone(observation.adapt_snapshot(incomplete, now=self.now).heating_source_active("H0001"))

    def test_pool_light_effect_is_readback_not_command(self):
        circuit = types.SimpleNamespace(id="C0002", is_on=True, effect_code="BLUER")
        observed = observation.adapt_snapshot(snapshot(self.now, circuit=circuit), now=self.now)
        self.assertTrue(observed.circuit("C0002").active)
        self.assertEqual(observed.circuit("C0002").effect_code, "BLUER")
        circuit.is_on = False
        self.assertIsNone(
            observation.adapt_snapshot(snapshot(self.now, circuit=circuit), now=self.now)
            .circuit("C0002").effect_code
        )

    def test_compatibility_boundaries_remain_explicit(self):
        select = (ROOT / "select.py").read_text()
        setup = (ROOT / "__init__.py").read_text()
        self.assertIn('"Solar": "H0002"', select)
        self.assertNotIn('"Solar Preferred"', select)
        self.assertIn("allow_commands=False", setup)


if __name__ == "__main__":
    unittest.main()
