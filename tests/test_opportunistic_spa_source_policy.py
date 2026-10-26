"""No-hardware source authority tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

P = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual" / "opportunistic_spa_source_policy.py"
spec = importlib.util.spec_from_file_location("opportunistic_spa_source_policy", P)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class SourcePolicyTests(unittest.TestCase):
    def test_normal_manual_spa_preferences_unchanged_without_claim(self):
        self.assertEqual(mod.arbitrate_spa_source(mod.SourceContext()), mod.SourceDecision.NORMAL_PREFERENCE)

    def test_claim_never_grants_gas_fallback(self):
        for context in (
            mod.SourceContext(spa_session_claimed=True),
            mod.SourceContext(spa_session_claimed=True, recovery_required=False),
            mod.SourceContext(spa_session_claimed=True, recovery_required=False, ownership_receipt_verified=True),
            mod.SourceContext(spa_session_claimed=True, recovery_required=False, ownership_receipt_verified=True, telemetry_fresh=True, manual_override_seen=True),
        ):
            with self.subTest(context=context):
                self.assertEqual(mod.arbitrate_spa_source(context), mod.SourceDecision.DEFER)

    def test_verified_claim_only_solar(self):
        ctx = mod.SourceContext(spa_session_claimed=True, recovery_required=False, ownership_receipt_verified=True, telemetry_fresh=True)
        self.assertEqual(mod.arbitrate_spa_source(ctx), mod.SourceDecision.SOLAR_ONLY)


if __name__ == "__main__":
    unittest.main()
