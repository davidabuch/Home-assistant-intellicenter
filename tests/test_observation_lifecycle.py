"""Regression checks for HA lifecycle and commissioning command interlock."""
import ast
from pathlib import Path
import unittest

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"

class LifecycleTests(unittest.TestCase):
    def test_entry_lifecycle_present(self):
        tree = ast.parse((PKG / "__init__.py").read_text())
        funcs = {n.name for n in tree.body if isinstance(n, ast.AsyncFunctionDef)}
        self.assertEqual(funcs, {"async_setup", "async_setup_entry", "async_unload_entry"})
        setup = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_setup")
        calls = [n.func.id for n in ast.walk(setup) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertEqual(calls, ["async_register_guardian_services"])
        self.assertFalse(any(isinstance(n, ast.Await) for n in ast.walk(setup)))

    def test_observation_fanout_has_teardown(self):
        tree = ast.parse((PKG / "observation_coordinator.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ObservationFanout")
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({"start", "refresh", "subscribe", "close"} <= methods)

    def test_commands_disabled_on_startup(self):
        source = (PKG / "__init__.py").read_text()
        self.assertIn("allow_commands=False", source)
        self.assertNotIn("allow_commands=True", source)

    def test_spa_compatibility_suffix(self):
        source = (PKG / "climate.py").read_text()
        self.assertIn('("spa", "Hot Tub Thermostat", "B1202")', source)

if __name__ == "__main__":
    unittest.main()
