"""Read-only HA gate evidence regression; unknown means blocked."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"
PKG = "spa_gate_test_package"
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, pkg)


def load(name):
    fullname = PKG + "." + name
    if fullname not in sys.modules:
        spec = importlib.util.spec_from_file_location(fullname, ROOT / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return sys.modules[fullname]


load("opportunistic_spa_policy")
load("opportunistic_spa_native_adapter")
gates = load("opportunistic_spa_ha_gates")


class State:
    def __init__(self, state):
        self.state = state


class GateTests(unittest.TestCase):
    def test_missing_all_states_fail_closed(self):
        evidence = gates.inspect_ha_gates({})
        self.assertFalse(evidence.safety.enabled)
        self.assertTrue(evidence.safety.recovery_required)
        self.assertTrue(evidence.safety.filtration_due)
        self.assertIn("ownership_receipt:unproven", evidence.blockers)

    def test_all_visible_safe_states_still_cannot_grant_authority(self):
        states = {name: State("off") for name in gates.REQUIRED_OFF}
        states.update({name: State("on") for name in gates.REQUIRED_ON})
        states.update({name: State("1") for name in gates.REQUIRED_KNOWN})
        evidence = gates.inspect_ha_gates(states)
        self.assertFalse(evidence.safety.enabled)
        self.assertFalse(evidence.safety.automatic_ownership)
        self.assertTrue(evidence.safety.manual_lockout)
        self.assertIn("competing_writer_provenance:unproven", evidence.blockers)

    def test_unavailable_or_active_safety_signal_is_blocker(self):
        states = {name: State("off") for name in gates.REQUIRED_OFF}
        states.update({name: State("on") for name in gates.REQUIRED_ON})
        states.update({name: State("1") for name in gates.REQUIRED_KNOWN})
        states["switch.pool_cleaning"] = State("on")
        states["binary_sensor.freeze_protection_active"] = State("unavailable")
        evidence = gates.inspect_ha_gates(states)
        self.assertIn("switch.pool_cleaning:not_confirmed_off", evidence.blockers)
        self.assertIn("binary_sensor.freeze_protection_active:not_confirmed_off", evidence.blockers)


if __name__ == "__main__":
    unittest.main()
