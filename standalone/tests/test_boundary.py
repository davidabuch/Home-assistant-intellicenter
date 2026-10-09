"""Regression tests for the minimal family app command boundary."""
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class BoundaryTests(unittest.TestCase):
    def test_pin_accepts_four_digits(self):
        script = (ROOT / "server.py").read_text()
        self.assertIn("len(PIN) < 4", script)
        self.assertNotIn("len(PIN) < 6", script)
    def test_climate_on_off_uses_explicit_hvac_mode(self):
        script = (ROOT / "server.py").read_text()
        self.assertIn('service = "set_hvac_mode"', script)
        self.assertIn('"hvac_mode": "heat" if operation == "on" else "off"', script)
    def test_exact_allowlist(self):
        self.assertEqual(set(server.CONTROLS), {"pool", "spa", "jets", "spillway", "slide"})
        self.assertNotIn("input_boolean.grid_outage_protection", [v[0] for v in server.CONTROLS.values()])
    def test_no_startup_actuation(self):
        self.assertFalse(any("turn_on" in str(v) for v in server.CONTROLS.values()))
    def test_ha_token_only_backend(self):
        script = (ROOT / "web" / "app.js").read_text()
        self.assertNotIn("SUPERVISOR_TOKEN", script)
        self.assertNotIn("/api/services/", script)
    def test_assets_exist(self):
        for name in ["index.html", "style.css", "app.js", "manifest.webmanifest"]:
            self.assertTrue((ROOT / "web" / name).exists())

if __name__ == "__main__":
    unittest.main()
