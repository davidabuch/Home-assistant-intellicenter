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
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            sessions = server.DeviceSessions(Path(directory) / "roles.json", "1234", "987654")
            family = sessions.login("1234")
            self.assertIsNotNone(family)
            self.assertEqual(sessions.role(family[0]), "family")
            self.assertIsNone(sessions.login("123"))
    def test_climate_on_off_uses_explicit_hvac_mode(self):
        script = (ROOT / "server.py").read_text()
        self.assertIn('service = "set_hvac_mode"', script)
        self.assertIn('"hvac_mode": "heat" if operation == "on" else "off"', script)
    def test_status_visuals_do_not_infer_heating_from_on(self):
        script = (ROOT / "web" / "app.js").read_text()
        self.assertNotIn('a.hvac_action==="heating"', script)
        self.assertIn('root.classList.toggle("is-heating",heating)', script)
        self.assertIn('heating?"Heating":on?"On · Ready":"Off"', script)
    def test_compact_power_and_feature_switches(self):
        script = (ROOT / "web" / "app.js").read_text()
        self.assertIn('power.classList.add("power-button")', script)
        self.assertIn('toggle.setAttribute("role","switch")', script)
        self.assertIn('root.append(top,readout,step)', script)
    def test_heating_requires_physical_heat_delivery(self):
        script = (ROOT / "web" / "app.js").read_text()
        self.assertIn("binary_sensor.solar_heating_active", script)
        self.assertIn("binary_sensor.gas_heater_active", script)
        self.assertIn("const heating=on&&(solarActive||gasActive)", script)
    def test_pool_admin_gate_is_fail_closed_when_enabled(self):
        script = (ROOT / "server.py").read_text()
        self.assertIn('if key in ("pool", "light"):', script)
        self.assertIn('"Administrator authorization required"', script)
        self.assertIn('if key not in CONTROLS:', script)
    def test_exact_allowlist(self):
        self.assertEqual(set(server.CONTROLS), {"pool", "spa", "jets", "spillway", "slide", "light"})
        self.assertNotIn("input_boolean.grid_outage_protection", [v[0] for v in server.CONTROLS.values()])
    def test_admin_light_boundary_and_effect_allowlist(self):
        script = (ROOT / "server.py").read_text()
        self.assertIn('if key == "light":\n            continue', script)
        self.assertIn('if self.admin_authorized():', script)
        self.assertIn('"light_control": self.admin_authorized()', script)
        self.assertIn('if value not in current.get("attributes", {}).get("effect_list", []):', script)
        self.assertIn('{"entity_id": entity, "effect": value}', script)

    def test_compact_layout_and_light_picker(self):
        html = (ROOT / "web" / "index.html").read_text()
        css = (ROOT / "web" / "style.css").read_text()
        js = (ROOT / "web" / "app.js").read_text()
        self.assertIn('class="water-bodies"', html)
        self.assertIn('.water-bodies{display:grid', css)
        self.assertIn('root.hidden=!allowed', js)
        self.assertIn('send("light","effect",effect)', js)
        self.assertNotIn("Other Features", html)

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
