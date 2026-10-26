"""No-hardware contract tests for native heat-source confirmation.

Inspect the transport method AST rather than opening a TCP connection.
"""
import ast
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual" / "transport.py"


class HeatSourceReadbackTests(unittest.TestCase):
    def test_source_requires_fresh_native_readback_and_timeout(self):
        tree = ast.parse(PATH.read_text())
        methods = [node for node in ast.walk(tree)
                   if isinstance(node, ast.AsyncFunctionDef) and node.name == "set_heat_source"]
        self.assertEqual(len(methods), 1)
        source = ast.get_source_segment(PATH.read_text(), methods[0])
        self.assertIn("dispatched_at = await self._send(", source)
        self.assertIn("observation.observed_at > dispatched_at", source)
        self.assertIn("body.heat_source == heater_id", source)
        self.assertIn("observation.connected", source)
        self.assertIn("deadline = asyncio.get_running_loop().time() + 25.0", source)
        self.assertIn("raise ManualCommandError(", source)

    def test_no_spa_target_or_rpm_write_in_source_method(self):
        tree = ast.parse(PATH.read_text())
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.AsyncFunctionDef) and node.name == "set_heat_source")
        source = ast.get_source_segment(PATH.read_text(), method)
        self.assertNotIn("set_target(", source)
        self.assertNotIn("set_pump_rpm(", source)
        self.assertNotIn("set_configured_pump_program_rpm(", source)


if __name__ == "__main__":
    unittest.main()
