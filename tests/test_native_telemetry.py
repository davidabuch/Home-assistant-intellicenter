"""Unit tests for native read-only telemetry mapping and protocol interlock."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual"
pkg = types.ModuleType("native_test_pkg")
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault("native_test_pkg", pkg)
spec = importlib.util.spec_from_file_location("native_test_pkg.observation", ROOT / "observation.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class NativeTelemetryTests(unittest.TestCase):
    def test_valid_telemetry(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[], circuits=[], telemetry={"pump_rpm": 2600, "air_temperature": "72.5",
                                               "firmware_version": "3.014"})
        result = module.adapt_snapshot(snapshot, now=now)
        self.assertEqual(result.measurement("pump_rpm"), 2600.0)
        self.assertEqual(result.measurement("air_temperature"), 72.5)
        self.assertEqual(result.measurement("firmware_version"), "3.014")

    def test_invalid_and_stale_values(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[], circuits=[], telemetry={"pump_rpm": float("nan"), "pump_power": True})
        result = module.adapt_snapshot(snapshot, now=now)
        self.assertIsNone(result.measurement("pump_rpm"))
        self.assertIsNone(result.measurement("pump_power"))
        snapshot.connected = False
        self.assertFalse(module.adapt_snapshot(snapshot, now=now).connected)

    def test_protocol_guard_and_sensor_platform(self):
        tree = ast.parse((ROOT / "transport.py").read_text())
        self.assertTrue(any(isinstance(n, ast.ClassDef) and n.name == "_CommissioningController"
                            for n in tree.body))
        self.assertIn('"sensor"', (ROOT / "__init__.py").read_text())

if __name__ == "__main__":
    unittest.main()
