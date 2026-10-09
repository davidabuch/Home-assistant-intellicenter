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
        self.assertIn("self._observed_at = None", dispatch)
        self.assertIn("self._publish()", dispatch)

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
        self.assertIn('Only Pool/Spa thermostat commands commissioned', source)
        setup = (SOURCE.parent / "__init__.py").read_text()
        self.assertIn('manual_command_delivery_enabled") is not False', setup)
        self.assertIn('arm_manual_thermostats', setup)
        self.assertIn('disarm_manual_thermostats', setup)

    def test_no_poolos_dependency(self):
        source = SOURCE.read_text()
        self.assertNotIn("from poolos", source)
        self.assertNotIn("import poolos", source)


if __name__ == "__main__":
    unittest.main()
