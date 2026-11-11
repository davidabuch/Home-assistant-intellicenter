"""Read-only native Spa policy adapter regression, no Home Assistant dependency."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"
pkg = "spa_adapter_test_package"
if pkg not in sys.modules:
    package = types.ModuleType(pkg)
    package.__path__ = [str(ROOT)]
    sys.modules[pkg] = package


def load(name):
    fullname = pkg + "." + name
    if fullname not in sys.modules:
        spec = importlib.util.spec_from_file_location(fullname, ROOT / (name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = mod
        spec.loader.exec_module(mod)
    return sys.modules[fullname]


policy = load("opportunistic_spa_policy")
adapter = load("opportunistic_spa_native_adapter")
observation = load("observation")


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
        self.safe = adapter.HASafety(
            enabled=True, recovery_required=False, manual_lockout=False,
            pool_demand=False, filtration_due=False, automatic_ownership=True,
            higher_priority_active=False,
        )

    def native(self, **kwargs):
        pool = observation.BodyObservation("B1101", False, False, 85, 85, "H0002")
        spa = observation.BodyObservation("B1202", False, False, 95, 99, "H0002")
        params = dict(connected=True, observed_at=self.now, bodies=(pool, spa),
                      telemetry=(observation.TelemetryObservation("solar_temperature", 135.0),))
        params.update(kwargs)
        return observation.ReadObservation(**params)

    def test_valid_native_observation_qualifies(self):
        result = adapter.adapt_native_spa(self.native(), self.safe, now=self.now)
        self.assertTrue(result.telemetry_fresh)
        self.assertTrue(result.pool_off and result.spa_off)
        self.assertEqual(result.native_spa_source, "Solar")
        self.assertEqual(result.roof_f, 135.0)
        self.assertEqual(policy.evaluate(policy.Session(), result, 10).session.phase, policy.Phase.SOLAR_QUALIFYING)

    def test_stale_missing_duplicate_and_future_observations_fail(self):
        for changes in (
            dict(connected=False),
            dict(observed_at=self.now - timedelta(seconds=31)),
            dict(observed_at=self.now + timedelta(seconds=1)),
            dict(bodies=()),
            dict(bodies=(self.native().bodies[0],)),
            dict(bodies=(self.native().bodies[0], self.native().bodies[1], self.native().bodies[1])),
            dict(telemetry=()),
            dict(telemetry=(observation.TelemetryObservation("solar_temperature", float("nan")),)),
        ):
            with self.subTest(changes=changes):
                result = adapter.adapt_native_spa(self.native(**changes), self.safe, now=self.now)
                self.assertFalse(result.telemetry_fresh)
                self.assertNotEqual(policy.evaluate(policy.Session(), result, 10).decision, policy.Decision.ACQUIRE)

    def test_gas_and_unknown_source(self):
        spa = observation.BodyObservation("B1202", False, False, 95, 99, "H0001")
        pool = self.native().bodies[0]
        result = adapter.adapt_native_spa(self.native(bodies=(pool, spa)), self.safe, now=self.now)
        self.assertEqual(result.native_spa_source, "Gas")
        spa = observation.BodyObservation("B1202", False, False, 95, 99, "BAD")
        result = adapter.adapt_native_spa(self.native(bodies=(pool, spa)), self.safe, now=self.now)
        self.assertFalse(result.telemetry_fresh)

    def test_safety_flags_never_inferred(self):
        result = adapter.adapt_native_spa(self.native(), adapter.HASafety(), now=self.now)
        self.assertTrue(result.recovery_required)
        self.assertTrue(result.pool_demand)
        self.assertTrue(result.filtration_due)
        self.assertFalse(result.automatic_ownership)


if __name__ == "__main__":
    unittest.main()
