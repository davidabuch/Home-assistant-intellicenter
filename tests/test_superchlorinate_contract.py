"""Native Super Chlorinate safety contract."""
import ast
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class SuperchlorinateContract(unittest.TestCase):
    def test_native_only(self):
        transport = (ROOT / "custom_components/intellicenter_manual/transport.py").read_text()
        switch = (ROOT / "custom_components/intellicenter_manual/switch.py").read_text()
        ast.parse(transport)
        ast.parse(switch)
        for token in ('method == "set_super_chlorinate"', 'args[0] == "CHR01"',
                      'self.intellichlor_object() is not None',
                      'self.superchlorinate_state() is not None',
                      'await self._send("set_super_chlorinate", "CHR01", enabled)'):
            self.assertIn(token, transport)
        self.assertIn("class NativeSuperchlorinate", switch)
        self.assertIn('"native_boost_value"', switch)
        self.assertNotIn("set_chlorine(", switch)
if __name__ == "__main__":
    unittest.main()
