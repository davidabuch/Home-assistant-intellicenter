"""Fail-closed native write boundary regression checks."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual/transport.py"


class NativeManualCommandGateTests(unittest.TestCase):
    def test_controller_starts_disarmed(self):
        source = SOURCE.read_text()
        self.assertIn("self.manual_writes_enabled = False", source)
        self.assertIn("if not self.manual_writes_enabled:", source)
        self.assertIn('raise ManualCommandError("Physical writes disabled in commissioning controller")', source)

    def test_integration_starts_read_only(self):
        source = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn("allow_commands=False", source)
        self.assertNotIn("manual_writes_enabled = True", source)

    def test_no_poolos_dependency(self):
        source = SOURCE.read_text()
        self.assertNotIn("from poolos", source)
        self.assertNotIn("import poolos", source)


if __name__ == "__main__":
    unittest.main()
