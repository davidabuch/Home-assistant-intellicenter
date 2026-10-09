"""Diagnostic entity behavior without requiring a running Home Assistant."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual"
for name, entity_class in (("binary_sensor", "BinarySensorEntity"), ("sensor", "SensorEntity")):
    component = types.ModuleType("homeassistant.components." + name)
    setattr(component, entity_class, type(entity_class, (), {}))
    sys.modules[component.__name__] = component
sys.modules["homeassistant"] = types.ModuleType("homeassistant")
sys.modules["homeassistant.components"] = types.ModuleType("homeassistant.components")

def load(name):
    spec = importlib.util.spec_from_file_location("isolated_" + name, root / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

binary = load("binary_sensor")
sensor = load("sensor")
entry = SimpleNamespace(entry_id="test")

class DiagnosticTests(unittest.TestCase):
    def test_health_is_unknown_before_first_observation(self):
        entity = binary.NativeStatus(entry, None, "native_observation_fresh",
                                     "Native Observation Fresh", "health", "native")
        self.assertFalse(entity.available)
        self.assertIsNone(entity.is_on)

    def test_disconnected_is_explicit_off_not_unavailable(self):
        entity = binary.NativeStatus(entry, None, "native_observation_fresh",
                                     "Native Observation Fresh", "health", "native")
        entity._observation = SimpleNamespace(connected=False)
        self.assertTrue(entity.available)
        self.assertFalse(entity.is_on)

    def test_disconnected_telemetry_and_freeze_are_unavailable(self):
        obs = SimpleNamespace(connected=False)
        freeze = binary.NativeStatus(entry, None, "freeze_protection_active",
                                     "Freeze Protection Active", "freeze", "_FEA2")
        freeze._observation = obs
        self.assertFalse(freeze.available)
        age = sensor.NativeTelemetry(entry, None, "native_observation_age",
                                     "Native Observation Age", "s")
        age._observation = obs
        self.assertFalse(age.available)
        self.assertIsNone(age.native_value)

    def test_recovered_health_and_observation_age(self):
        now = datetime.now(timezone.utc)
        obs = SimpleNamespace(connected=True, observed_at=now)
        health = binary.NativeStatus(entry, None, "native_observation_fresh",
                                     "Native Observation Fresh", "health", "native")
        health._observation = obs
        self.assertTrue(health.available)
        self.assertTrue(health.is_on)
        age = sensor.NativeTelemetry(entry, None, "native_observation_age",
                                     "Native Observation Age", "s")
        age._observation = obs
        self.assertTrue(age.available)
        self.assertGreaterEqual(age.native_value, 0)
        self.assertLess(age.native_value, 5)

if __name__ == "__main__":
    unittest.main()
