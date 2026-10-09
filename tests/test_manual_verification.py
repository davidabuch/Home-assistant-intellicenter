"""Pure regression tests for future manual delivery verification (no HA/IO)."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual"
pkg = ModuleType("manual_verify_pkg")
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg
for name in ("observation", "manual_verification"):
    spec = importlib.util.spec_from_file_location(f"{pkg.__name__}.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
obs = sys.modules[f"{pkg.__name__}.observation"]
verification = sys.modules[f"{pkg.__name__}.manual_verification"]
NOW = datetime(2026, 10, 8, 20, tzinfo=timezone.utc)


class ManualVerificationTests(unittest.TestCase):
    def observation(self, *, time=None, connected=True, rpm=2900.0, active=True):
        return obs.ReadObservation(
            connected, time or NOW + timedelta(seconds=1),
            (obs.BodyObservation("B1101", active, True, 82, 90, "H0002"),),
            (obs.CircuitObservation("C0003", False),),
            (obs.TelemetryObservation("pump_rpm", rpm),),
        )

    def check(self, kind, native_id, value, observation=None):
        expected = verification.ExpectedChange(kind, native_id, value, NOW)
        return verification.verify_change(expected, observation or self.observation())

    def test_exact_body_and_circuit(self):
        self.assertEqual(self.check("body_active", "B1101", True), verification.VerificationStatus.VERIFIED)
        self.assertEqual(self.check("body_active", "B1101", False), verification.VerificationStatus.PENDING)
        self.assertEqual(self.check("circuit_active", "C0003", False), verification.VerificationStatus.VERIFIED)

    def test_target_source_and_rpm(self):
        self.assertEqual(self.check("target", "B1101", 90), verification.VerificationStatus.VERIFIED)
        self.assertEqual(self.check("heater_id", "B1101", "H0002"), verification.VerificationStatus.VERIFIED)
        self.assertEqual(self.check("pump_rpm", "PMP01", 2925), verification.VerificationStatus.VERIFIED)
        self.assertEqual(self.check("pump_rpm", "PMP01", 2926), verification.VerificationStatus.PENDING)

    def test_stale_and_untrusted_never_verify(self):
        for sample in (
            self.observation(time=NOW),
            self.observation(time=NOW - timedelta(seconds=1)),
            self.observation(connected=False),
            self.observation(rpm=None),
        ):
            self.assertEqual(self.check("pump_rpm", "PMP01", 2900, sample), verification.VerificationStatus.UNTRUSTED)

    def test_ambiguous_identity_and_bad_expectation(self):
        sample = self.observation()
        duplicate = obs.ReadObservation(sample.connected, sample.observed_at, sample.bodies * 2, sample.circuits, sample.telemetry)
        self.assertEqual(self.check("body_active", "B1101", True, duplicate), verification.VerificationStatus.UNTRUSTED)
        self.assertEqual(self.check("pump_rpm", "PMP02", 2900), verification.VerificationStatus.UNTRUSTED)
        self.assertEqual(self.check("target", "B1101", True), verification.VerificationStatus.UNTRUSTED)
        self.assertEqual(self.check("heater_id", "B1101", "UNKNOWN"), verification.VerificationStatus.UNTRUSTED)


if __name__ == "__main__":
    unittest.main()
