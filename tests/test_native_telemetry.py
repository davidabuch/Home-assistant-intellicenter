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
    def test_heater_source_activity_is_fail_closed(self):
        now = datetime.now(timezone.utc)
        pool = types.SimpleNamespace(id="B1101", is_on=True, heating_active=True,
            current_temperature=85, target_temperature=90, active_heat_source="H0002")
        spa = types.SimpleNamespace(id="B1202", is_on=False, heating_active=False,
            current_temperature=98, target_temperature=98, active_heat_source="00000")
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[pool, spa], circuits=[], telemetry={})
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertTrue(observed.heating_source_active("H0002"))
        self.assertFalse(observed.heating_source_active("H0001"))
        pool.heating_active = False
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertFalse(observed.heating_source_active("H0002"))
        pool.heating_active = True
        pool.active_heat_source = None
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertIsNone(observed.heating_source_active("H0002"))
        pool.active_heat_source = "H0001"
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertTrue(observed.heating_source_active("H0001"))
        snapshot.bodies = [pool]
        self.assertIsNone(module.adapt_snapshot(snapshot, now=now).heating_source_active("H0001"))
        snapshot.connected = False
        self.assertIsNone(module.adapt_snapshot(snapshot, now=now).heating_source_active("H0001"))

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
        self.assertIn("_attr_color_mode = ColorMode.ONOFF", light)
        self.assertIn("except Exception:", fanout)
        self.assertIn("continuing other entities", fanout)
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

    def test_intellibrite_effect_control_is_explicit_and_guarded(self):
        light = (ROOT / "light.py").read_text()
        transport = (ROOT / "transport.py").read_text()
        self.assertIn("LightEntityFeature.EFFECT", light)
        self.assertIn("LIGHT_EFFECTS.values()", light)
        self.assertIn("await self._runtime.transport.set_light_effect(code)", light)
        self.assertIn("await self._send(\"set_light_effect\"", transport)
        self.assertIn("allow_commands=False", (ROOT / "__init__.py").read_text())

    def test_native_heating_and_heater_id_observations(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[types.SimpleNamespace(id="B1101", is_on=True, heating_active=True,
                current_temperature=82, target_temperature=90, active_heat_source="H0002"),
                types.SimpleNamespace(id="B1202", is_on=False, heating_active=None,
                current_temperature=98, target_temperature=100, active_heat_source=None)],
            circuits=[], telemetry={})
        obs = module.adapt_snapshot(snapshot, now=now)
        self.assertTrue(obs.body("B1101").heating)
        self.assertEqual(obs.body("B1101").heat_source, "H0002")
        self.assertIsNone(obs.body("B1202").heating)
        self.assertIsNone(obs.body("B1202").heat_source)
        status = (ROOT / "binary_sensor.py").read_text()
        sensor = (ROOT / "sensor.py").read_text()
        self.assertIn('"pool_heating_active"', status)
        self.assertIn('"spa_heating_active"', status)
        self.assertIn('item.heating if self._kind == "body_heating"', status)
        self.assertIn('"pool_heater_id"', sensor)
        self.assertIn('"spa_heater_id"', sensor)
        self.assertIn('return body.heat_source', sensor)
        self.assertIn("allow_commands=False", (ROOT / "__init__.py").read_text())

    def test_native_light_effect_readback(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[], circuits=[
                types.SimpleNamespace(id="C0002", is_on=True, effect_code="CARIB"),
                types.SimpleNamespace(id="C0003", is_on=False, effect_code="CARIB")], telemetry={})
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertEqual(observed.circuit("C0002").effect_code, "CARIB")
        self.assertIsNone(observed.circuit("C0003").effect_code)
        snapshot.circuits[0].effect_code = None
        self.assertIsNone(module.adapt_snapshot(snapshot, now=now).circuit("C0002").effect_code)
        self.assertIn("obj.properties.get('USE')", (ROOT / "transport.py").read_text())
        self.assertIn("LIGHT_EFFECTS.get(circuit.effect_code)", (ROOT / "light.py").read_text())

    def test_pool_heating_transition_states_preserve_native_truth(self):
        now = datetime.now(timezone.utc)
        body = types.SimpleNamespace(id="B1101", is_on=True, heating_active=True,
            current_temperature=85, target_temperature=90, active_heat_source="H0002")
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[body], circuits=[], telemetry={})
        heating = module.adapt_snapshot(snapshot, now=now).body("B1101")
        self.assertTrue(heating.active)
        self.assertTrue(heating.heating)
        self.assertEqual(heating.heat_source, "H0002")
        body.heating_active = False
        idle = module.adapt_snapshot(snapshot, now=now).body("B1101")
        self.assertTrue(idle.active)
        self.assertFalse(idle.heating)
        body.is_on = False
        off = module.adapt_snapshot(snapshot, now=now).body("B1101")
        self.assertFalse(off.active)
        self.assertFalse(off.heating)
        body.heating_active = None
        self.assertIsNone(module.adapt_snapshot(snapshot, now=now).body("B1101").heating)
        snapshot.connected = False
        self.assertFalse(module.adapt_snapshot(snapshot, now=now).connected)

    def test_spa_heating_is_independent_of_pool_heating(self):
        now = datetime.now(timezone.utc)
        snapshot = types.SimpleNamespace(connected=True, observed_at=now,
            bodies=[
                types.SimpleNamespace(id="B1101", is_on=True, heating_active=False,
                    current_temperature=85, target_temperature=90, active_heat_source="H0002"),
                types.SimpleNamespace(id="B1202", is_on=True, heating_active=True,
                    current_temperature=98, target_temperature=100, active_heat_source="H0001")],
            circuits=[], telemetry={})
        observed = module.adapt_snapshot(snapshot, now=now)
        self.assertFalse(observed.body("B1101").heating)
        self.assertTrue(observed.body("B1202").heating)
        self.assertEqual(observed.body("B1202").heat_source, "H0001")

    def test_pump_telemetry_requires_unique_commissioned_identity(self):
        source = (ROOT / "transport.py").read_text()
        self.assertIn('str(obj.objnam) == "PMP01"', source)
        self.assertIn("if len(pumps) == 1:", source)
        self.assertNotIn("if 'pump_rpm' in telemetry:", source)
        self.assertIn("pump_rpm=props.get(RPM_ATTR)", source)

    def test_probe_roles_fail_closed_on_duplicate_discovery(self):
        source = (ROOT / "transport.py").read_text()
        self.assertIn("probes_by_key = {key: [] for key in probe_keys.values()}", source)
        self.assertIn("probes_by_key[key].append(obj)", source)
        self.assertIn("if len(probes) == 1:", source)
        self.assertNotIn("key not in telemetry", source)

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
