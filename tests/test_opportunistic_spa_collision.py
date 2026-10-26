"""No-hardware tests of manual-takeover collision detection."""
import importlib.util
from pathlib import Path
import sys
import unittest

p = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual" / "opportunistic_spa_collision.py"
spec = importlib.util.spec_from_file_location("opportunistic_spa_collision", p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class CollisionTests(unittest.TestCase):
    def before(self):
        return m.Witness("epoch-1", "Solar", True, 99.0, 10, True)

    def after(self, **changes):
        values = dict(epoch="epoch-1", source="Solar", spa_active=True, target_f=99.0, generation=11, fresh=True)
        values.update(changes)
        return m.Witness(**values)

    def test_unchanged_native_observation(self):
        self.assertEqual(m.classify_transition(self.before(), self.after(), None), m.Collision.NONE)

    def test_external_spa_off_yields(self):
        self.assertEqual(m.classify_transition(self.before(), self.after(spa_active=False), None), m.Collision.YIELD)

    def test_external_source_or_target_yields(self):
        self.assertEqual(m.classify_transition(self.before(), self.after(source="Gas"), None), m.Collision.YIELD)
        self.assertEqual(m.classify_transition(self.before(), self.after(target_f=101), None), m.Collision.YIELD)

    def test_matching_epoch_and_intent_only(self):
        expected = m.ExpectedTransition("epoch-1", spa_active=False)
        self.assertEqual(m.classify_transition(self.before(), self.after(spa_active=False), expected), m.Collision.NONE)
        self.assertEqual(m.classify_transition(self.before(), self.after(source="Gas", spa_active=False), expected), m.Collision.YIELD)

    def test_restart_and_stale_fail_closed(self):
        self.assertEqual(m.classify_transition(self.before(), self.after(epoch="epoch-2"), None), m.Collision.RECOVERY_REQUIRED)
        self.assertEqual(m.classify_transition(self.before(), self.after(generation=10), None), m.Collision.RECOVERY_REQUIRED)
        self.assertEqual(m.classify_transition(self.before(), self.after(fresh=False), None), m.Collision.RECOVERY_REQUIRED)


if __name__ == "__main__":
    unittest.main()
