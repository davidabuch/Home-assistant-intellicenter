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

    def test_attribute_import_uses_library_submodule(self):
        source = (ROOT / "transport.py").read_text()
        self.assertIn("from pyintellicenter.attributes import ALL_ATTRIBUTES_BY_TYPE", source)

    def test_manual_platforms_registered_and_guarded(self):
        setup = (ROOT / "__init__.py").read_text()
        for platform in ("switch", "light", "number", "select"):
            self.assertIn(f'"{platform}"', setup)
            source = (ROOT / f"{platform}.py").read_text()
            self.assertIn("async_setup_entry", source)
            self.assertIn("observation_fanout.subscribe", source)
        transport = (ROOT / "transport.py").read_text()
        self.assertIn("allow_commands=False", setup)
        self.assertIn("Read-only commissioning: all physical commands are disabled", transport)
        self.assertIn("async def set_pump_rpm", transport)

    def test_ha_runtime_safety_contract(self):
        light = (ROOT / "light.py").read_text()
        fanout = (ROOT / "observation_coordinator.py").read_text()
        setup = (ROOT / "__init__.py").read_text()
        self.assertIn("_attr_supported_color_modes = {ColorMode.ONOFF}", light)
        self.assertIn("call_soon_threadsafe(self.refresh)", fanout)
        self.assertIn("asyncio.get_running_loop()", setup)

    def test_intellichlor_telemetry_and_manual_guard(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[], circuits=[], telemetry={"intellichlor_pool_output": 40,
                "intellichlor_spa_output": 5, "intellichlor_salt": 3300})
        obs = module.adapt_snapshot(snapshot, now=now)
        self.assertEqual(obs.measurement("intellichlor_pool_output"), 40)
        self.assertEqual(obs.measurement("intellichlor_spa_output"), 5)
        self.assertEqual(obs.measurement("intellichlor_salt"), 3300)
        self.assertIn("Both chlorine outputs must be freshly observed", (ROOT / "number.py").read_text())
        self.assertIn("allow_commands=False", (ROOT / "__init__.py").read_text())

    def test_discovery_contract(self):
        source = (ROOT / "transport.py").read_text()
        self.assertIn("class _DiscoveryPoolModel(PoolModel)", source)
        self.assertIn("self.model = _DiscoveryPoolModel()", source)
        self.assertIn("self._attribute_map[SENSE_TYPE] = {SNAME_ATTR, SOURCE_ATTR}", source)

    def test_protocol_guard_and_sensor_platform(self):
        tree = ast.parse((ROOT / "transport.py").read_text())
        self.assertTrue(any(isinstance(n, ast.ClassDef) and n.name == "_CommissioningController"
                            for n in tree.body))
        self.assertIn('"sensor"', (ROOT / "__init__.py").read_text())

if __name__ == "__main__":
    unittest.main()
