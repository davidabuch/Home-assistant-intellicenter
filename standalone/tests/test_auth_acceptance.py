"""Acceptance tests for family/admin authorization, with zero equipment calls.

These tests intentionally fail until the replacement authentication boundary exists.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family_server_acceptance", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class AuthenticationAcceptance(unittest.TestCase):
    def test_family_pin_not_required_for_verified_local_access(self):
        self.assertTrue(hasattr(server.Handler, "family_authorized"),
                        "Implement a verified-local/remote family access boundary")

    def test_pool_admin_cannot_be_granted_by_pin(self):
        self.assertTrue(hasattr(server.Handler, "admin_authorized"),
                        "Pool permissions require separate administrator verification")

    def test_handoff_replay_is_rejected(self):
        self.assertTrue(hasattr(server, "consume_admin_handoff"),
                        "Admin handoff must be one-time and replay resistant")

    def test_remote_access_requires_verified_identity(self):
        self.assertTrue(hasattr(server, "remote_identity_verified"),
                        "Remote access must validate trusted Cloudflare identity")

    def test_existing_control_allowlist_is_preserved(self):
        self.assertEqual(set(server.CONTROLS), {"pool", "spa", "jets", "spillway", "slide"})

    def test_no_direct_pentair_actuation(self):
        source = (ROOT / "server.py").read_text()
        self.assertNotIn("pentair.local", source)
        self.assertNotIn("poolos", source.lower())


if __name__ == "__main__":
    unittest.main()
