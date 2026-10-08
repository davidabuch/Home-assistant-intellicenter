"""Static regression checks for the manual command surface (no HA required)."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "intellicenter_manual"


class TestManualSurface(unittest.TestCase):
    def test_no_poolos_imports(self):
        for file in PACKAGE.glob("*.py"):
            tree = ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith("poolos") for alias in node.names))
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module.startswith("poolos"))

    def test_no_automation_engine(self):
        for file in PACKAGE.glob("*.py"):
            name = file.name
            self.assertNotIn(name, {
                "thermal_runtime.py", "filtration_runtime.py",
                "grid_outage_runtime.py", "ownership.py",
            })

    def test_manual_gateway_allowlist(self):
        tree = ast.parse((PACKAGE / "transport.py").read_text())
        gateway = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IntelliCenterManualTransport")
        methods = {n.name for n in gateway.body if isinstance(n, ast.AsyncFunctionDef)}
        self.assertTrue({"set_body_active", "set_target", "set_heat_source", "set_circuit", "set_light_effect", "set_chlorine"} <= methods)
        self.assertFalse(any("automatic" in name or "schedule" in name for name in methods))


if __name__ == "__main__":
    unittest.main()
