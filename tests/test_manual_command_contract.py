"""Fail-closed command and cutover semantic contracts; no HA or equipment needed."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"


def tree(filename):
    return ast.parse((ROOT / filename).read_text())


def method(cls, name):
    return next(node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


class ManualCommandContractTests(unittest.TestCase):
    def test_read_only_setup_is_unconditional(self):
        setup = tree("__init__.py")
        calls = [node for node in ast.walk(setup) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "IntelliCenterManualTransport"]
        self.assertEqual(len(calls), 1)
        kw = {item.arg: item.value for item in calls[0].keywords}
        self.assertIn("allow_commands", kw)
        self.assertIsInstance(kw["allow_commands"], ast.Constant)
        self.assertIs(kw["allow_commands"].value, False)

    def test_protocol_mutation_denied_independently_of_transport_flag(self):
        controller = next(node for node in tree("transport.py").body if isinstance(node, ast.ClassDef) and node.name == "_CommissioningController")
        for name in ("request_changes", "_queue_property_change"):
            fn = method(controller, name)
            self.assertTrue(any(isinstance(n, ast.Raise) for n in ast.walk(fn)), name)
        send = method(controller, "send_cmd")
        self.assertTrue(any(isinstance(n, ast.Raise) for n in ast.walk(send)))

    def test_all_mutators_route_through_guard(self):
        transport = next(node for node in tree("transport.py").body if isinstance(node, ast.ClassDef) and node.name == "IntelliCenterManualTransport")
        for name in ("set_body_active", "set_pump_rpm", "set_target", "set_heat_source", "set_circuit", "set_light_effect", "set_chlorine"):
            fn = method(transport, name)
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_send"]
            self.assertEqual(len(calls), 1, name)
        send = method(transport, "_send")
        self.assertIn("if not self._allow_commands", ast.get_source_segment((ROOT / "transport.py").read_text(), send))

    def test_heat_source_options_are_not_solar_preferred(self):
        select = (ROOT / "select.py").read_text()
        self.assertIn('"Solar": "H0002"', select)
        self.assertNotIn('"Solar Preferred"', select)

    def test_spa_gauge_climate_attribute_contract(self):
        climate = (ROOT / "climate.py").read_text()
        for name in ("hvac_mode", "hvac_action", "current_temperature", "target_temperature"):
            self.assertIn(f"def {name}(self):", climate)
        self.assertIn("HVACAction.HEATING if body.heating else HVACAction.IDLE", climate)
        self.assertIn("if body.heating is None:", climate)
        self.assertIn("if not body.active:", climate)

    def test_accessory_and_chlorine_commands_use_guarded_gateway(self):
        for filename in ("switch.py", "number.py", "light.py", "select.py", "climate.py"):
            source = (ROOT / filename).read_text()
            self.assertNotIn("request_changes(", source, filename)
            self.assertNotIn("send_cmd(", source, filename)


if __name__ == "__main__":
    unittest.main()
