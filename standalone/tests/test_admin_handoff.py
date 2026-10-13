"""No-equipment unit tests for the administrator handoff verifier."""
import base64
import hashlib
import hmac
import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin_handoff import AdminHandoff, HandoffError

SECRET = "test-only-shared-secret-not-used-in-production-1234"

def ticket(claims, secret=SECRET):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return payload + "." + sig

def claims(**updates):
    value = {"aud": "pool-spa-family", "role": "admin", "sub": "admin-user",
             "exp": 1050, "nonce": "a" * 48}
    value.update(updates)
    return value

class AdminHandoffTests(unittest.TestCase):
    def setUp(self):
        self.auth = AdminHandoff(SECRET, clock=lambda: 1000)

    def test_valid_ticket(self):
        sid = self.auth.exchange(ticket(claims()))
        self.assertTrue(self.auth.is_admin(sid))

    def test_replay_denied(self):
        signed = ticket(claims())
        self.auth.exchange(signed)
        with self.assertRaises(HandoffError):
            self.auth.exchange(signed)

    def test_non_admin_denied(self):
        with self.assertRaises(HandoffError):
            self.auth.exchange(ticket(claims(role="family")))

    def test_expired_denied(self):
        with self.assertRaises(HandoffError):
            self.auth.exchange(ticket(claims(exp=999)))

    def test_future_expiry_denied(self):
        with self.assertRaises(HandoffError):
            self.auth.exchange(ticket(claims(exp=2000)))

    def test_wrong_secret_denied(self):
        with self.assertRaises(HandoffError):
            self.auth.exchange(ticket(claims(), "another-secret-with-at-least-32-characters"))

    def test_tampered_ticket_denied(self):
        signed = ticket(claims())
        with self.assertRaises(HandoffError):
            self.auth.exchange(signed[:-1] + ("a" if signed[-1] != "a" else "b"))

    def test_session_expiration(self):
        sid = self.auth.exchange(ticket(claims()))
        self.auth.clock = lambda: 1901
        self.assertFalse(self.auth.is_admin(sid))

    def test_missing_secret_denied(self):
        with self.assertRaises(HandoffError):
            AdminHandoff("")

if __name__ == "__main__":
    unittest.main()
