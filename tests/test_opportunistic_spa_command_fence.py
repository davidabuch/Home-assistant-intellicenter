"""No-hardware tests for the command fence."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual"
pkg = types.ModuleType("fence_tests")
pkg.__path__ = [str(root)]
sys.modules["fence_tests"] = pkg
for name in ("opportunistic_spa_provenance", "opportunistic_spa_command_fence"):
    spec = importlib.util.spec_from_file_location("fence_tests." + name, root / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from fence_tests.opportunistic_spa_command_fence import SpaCommandFence, Gate
from fence_tests.opportunistic_spa_provenance import CommandKind, Readback, ReceiptStatus


class FenceTests(unittest.TestCase):
    def test_restart_cannot_grant_ownership(self):
        guard = SpaCommandFence()
        self.assertEqual(guard.start_epoch("first", externally_authorized=True), Gate.RECOVERY_REQUIRED)
        self.assertEqual(guard.reserve(CommandKind.SPA_ON, epoch="first", observed_generation=1,
            now_s=10, all_external_writers_excluded=True,
            fresh_priority_gates=True, native_fresh=True), Gate.RECOVERY_REQUIRED)
        self.assertIsNone(guard.pending)

    def test_epoch_change_and_invalidation(self):
        guard = SpaCommandFence()
        guard.start_epoch("first")
        guard.start_epoch("second")
        self.assertEqual(guard.reserve(CommandKind.SPA_OFF, epoch="first",
            observed_generation=5, now_s=12), Gate.RECOVERY_REQUIRED)
        self.assertEqual(guard.confirm(Readback(13, 6, "Solar", False, True),
            epoch="second"), ReceiptStatus.UNPROVEN)
        guard.invalidate()
        self.assertTrue(guard.recovery_required)


if __name__ == "__main__":
    unittest.main()
