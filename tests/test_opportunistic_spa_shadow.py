"""No hardware: shadow observer must remain disabled across every observation."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"
PKG = "spa_shadow_test_package"
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, pkg)


def load(name):
    fullname = PKG + "." + name
    if fullname not in sys.modules:
        spec = importlib.util.spec_from_file_location(fullname, ROOT / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return sys.modules[fullname]


policy = load("opportunistic_spa_policy")
load("opportunistic_spa_native_adapter")
shadow = load("opportunistic_spa_shadow")
native_mod = load("observation")


class ShadowTests(unittest.TestCase):
    def test_disabled_even_if_caller_requests_enabled(self):
        now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        native = native_mod.ReadObservation(
            True, now, (
                native_mod.BodyObservation("B1101", False, False, 84, 84, "H0002"),
                native_mod.BodyObservation("B1202", False, False, 96, 99, "H0002"),
            ), telemetry=(native_mod.TelemetryObservation("solar_temperature", 140),))
        coordinator = shadow.SpaSolarShadowCoordinator(clock=lambda: 300, wall_clock=lambda: now)
        safety = shadow.HASafety(enabled=True, recovery_required=False,
            manual_lockout=False, pool_demand=False, filtration_due=False,
            automatic_ownership=True, higher_priority_active=False,
            owned_receipt_verified=True)
        for _ in range(5):
            result = coordinator.observe(native, safety=safety)
            self.assertNotEqual(result.decision, policy.Decision.ACQUIRE)
            self.assertNotEqual(result.decision, policy.Decision.RELEASE_IF_OWNED)
            self.assertEqual(result.phase, policy.Phase.RECOVERY_REQUIRED)
        coordinator.close()
        self.assertEqual(coordinator.observe(native), result)

    def test_initial_report_is_nonactuating(self):
        coordinator = shadow.SpaSolarShadowCoordinator()
        self.assertEqual(coordinator.report.decision, policy.Decision.NONE)


if __name__ == "__main__":
    unittest.main()
