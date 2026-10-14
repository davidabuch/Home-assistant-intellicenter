"""Sanitation discovery regression without HA runtime or physical commands."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"


class FakeModel:
    def __init__(self, circuits):
        self.circuits = circuits

    def get_by_type(self, objtype):
        return self.circuits


class TestSanitationDiscovery(unittest.TestCase):
    def test_unique_exact_native_name_and_no_accessory_hijack(self):
        source = (ROOT / "transport.py").read_text()
        tree = ast.parse(source)
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_sanitation_candidates")
        scope = {"CIRCUIT_TYPE": "circuit", "SNAME_ATTR": "SNAME",
                 "CIRCUIT_IDS": frozenset({"C0002", "C0003", "C0004", "FTR01"})}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<discovery>", "exec"), scope)
        candidates = scope["_sanitation_candidates"]
        def obj(id, name):
            return SimpleNamespace(objnam=id, properties={"SNAME": name})
        self.assertEqual(candidates(FakeModel([obj("FTR02", "Sanitation")])), ["FTR02"])
        self.assertEqual(candidates(FakeModel([obj("FTR02", " SANITATION ")])), ["FTR02"])
        self.assertEqual(candidates(FakeModel([obj("FTR02", "Sanitation"),
                                                obj("FTR03", "Sanitation")])),
                         ["FTR02", "FTR03"])
        self.assertEqual(candidates(FakeModel([obj("C0003", "Sanitation"),
                                                obj("FTR04", "Other")])), [])

    def test_existing_accessories_preserved_and_no_auto_actuation(self):
        switches = (ROOT / "switch.py").read_text()
        for id in ("C0003", "C0004", "FTR01"):
            self.assertIn(id, switches)
        self.assertIn("discovered = set()", switches)
        self.assertIn("async_add_entities", switches)
        self.assertNotIn("async_turn_on()", switches)
        for name in ("transport.py", "observation.py", "switch.py"):
            ast.parse((ROOT / name).read_text())


if __name__ == "__main__":
    unittest.main()
