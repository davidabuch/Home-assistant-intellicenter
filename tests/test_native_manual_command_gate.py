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

    def test_dispatch_checks_freshness_under_lock(self):
        source = SOURCE.read_text()
        dispatch = source.split("    async def _send(", 1)[1].split("    async def set_body_active(", 1)[0]
        self.assertIn("async with self._lock:", dispatch)
        self.assertIn("observation = self.read_observation()", dispatch)
        self.assertIn("not observation.connected", dispatch)
        self.assertIn("not self.controller.manual_writes_enabled", dispatch)
        self.assertNotIn("self._observed_at = None", dispatch)
        self.assertIn("observed_at > dispatched_at", dispatch)

    def test_thermostat_requires_new_native_confirmation(self):
        source = SOURCE.read_text()
        self.assertIn('async def _confirm_body(', source)
        self.assertIn('observation.body(body_id) if observation.connected else None', source)
        self.assertIn('Native confirmation timeout', source)
        self.assertIn('await self._confirm_body(body_id, "active", active, dispatched_at)', source)
        self.assertIn('await self._confirm_body(body_id, "target_temperature", target, dispatched_at)', source)

    def test_post_command_chronology_and_exclusive_authority(self):
        source = SOURCE.read_text()
        self.assertIn("observation.observed_at > dispatched_at", source)
        self.assertIn("self._manual_authority_check()", source)
        self.assertIn("self.disarm_manual_thermostats()", source)
        self.assertIn('Command outside commissioned native manual allowlist', source)
        setup = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn('manual_command_delivery_enabled") is not False', setup)
        self.assertIn('arm_manual_thermostats', setup)
        self.assertIn('disarm_manual_thermostats', setup)

    def test_all_manual_accessory_paths_are_allowlisted(self):
        source = SOURCE.read_text()
        dispatch = source.split("    async def _send(", 1)[1].split("    async def _confirm_body(", 1)[0]
        for method in ("set_circuit_state", "set_light_effect", "set_chlorinator_output",
                       "set_heating_setpoint"):
            self.assertIn('method == "' + method + '"', dispatch)
        for object_id in ('"CHR01"', '"C0002"'):
            self.assertIn(object_id, dispatch)
        self.assertIn("600 <= int(args[1][SPEED_ATTR]) <= 3450", dispatch)
        self.assertIn("0 <= v <= 100", dispatch)

    def test_outage_safety_is_enforced_at_final_dispatch(self):
        transport = SOURCE.read_text()
        setup = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn("self._outage_command_check(method, args)", transport)
        self.assertIn("Grid outage safety lockout", transport)
        self.assertIn("transport.set_outage_command_check(_outage_command_allowed)", setup)
        self.assertIn('input_boolean.grid_outage_active', setup)
        self.assertIn('input_boolean.grid_outage_protection', setup)
        self.assertIn('9 <= dt_util.as_local(dt_util.utcnow()).hour < 17', setup)
        self.assertIn('changes[SPEED_ATTR] == "1500"', setup)
        self.assertIn('return args[1] is False', setup)
        self.assertIn('return False', setup)

    def test_dynamic_pump_speed_assignment(self):
        source = SOURCE.read_text()
        self.assertIn("def _pool_speed_assignment(self)", source)
        self.assertIn("self.model.get_by_type(PMPCIRC_TYPE)", source)
        self.assertIn("candidate[CIRCUIT_ATTR]", source)
        self.assertIn("candidate[SELECT_ATTR]", source)
        self.assertIn("len(matches) != 1", source)
        self.assertIn("SPEED_ATTR: str(round(float(rpm)))", source)

    def test_emergency_pool_off_always_permitted(self):
        setup = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn("changes[STATUS_ATTR] == STATUS_OFF or", setup)

    def test_persistent_operator_bypass_latch_gates_native_safety(self):
        setup = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn("input_boolean.grid_outage_operator_bypass_latch", setup)
        self.assertIn('bypass.state == "off"', setup)

    def test_no_poolos_dependency(self):
        source = SOURCE.read_text()
        self.assertNotIn("from poolos", source)
        self.assertNotIn("import poolos", source)


if __name__ == "__main__":
    unittest.main()
