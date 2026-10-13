"""Offline regression tests: never connect to HA or operate pool equipment."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from standalone.device_sessions import DeviceSessions
except ImportError:
    from device_sessions import DeviceSessions


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sessions.json"
        self.store = DeviceSessions(self.path, "1234", "9876")

    def test_family_never_admin(self):
        sid, role = self.store.login("1234")
        self.assertEqual(role, "family")
        self.assertEqual(self.store.role(sid), "family")
        self.assertIsNone(self.store.login("bad"))

    def test_admin_is_separate(self):
        sid, role = self.store.login("9876")
        self.assertEqual(role, "admin")
        self.assertEqual(self.store.role(sid), "admin")

    def test_persistence_and_rotation(self):
        sid, _ = self.store.login("9876")
        self.assertEqual(DeviceSessions(self.path, "1234", "9876").role(sid), "admin")
        self.assertIsNone(DeviceSessions(self.path, "1234", "changed-pin").role(sid))

    def test_admin_fails_closed(self):
        for pin in ("", "1234", "123"):
            store = DeviceSessions(self.path, "1234", pin)
            self.assertIsNone(store.login(pin) if pin != "1234" else store.login("bad"))
            self.assertEqual(store.login("1234")[1], "family")

    def test_four_digit_admin_pin_and_rotation(self):
        sid, role = self.store.login("9876")
        self.assertEqual(role, "admin")
        self.assertEqual(self.store.role(sid), "admin")
        self.store.rotate("admin", "4567")
        self.assertIsNone(self.store.role(sid))
        self.assertEqual(self.store.login("4567")[1], "admin")
        with self.assertRaises(ValueError):
            self.store.rotate("admin", "1234")
        with self.assertRaises(ValueError):
            self.store.rotate("admin", "123")

    def test_logout(self):
        sid, _ = self.store.login("1234")
        self.store.logout(sid)
        self.assertIsNone(self.store.role(sid))

    def test_expired(self):
        sid, _ = self.store.login("1234")
        with patch("standalone.device_sessions.time.time", return_value=10**12):
            self.assertIsNone(self.store.role(sid))


if __name__ == "__main__":
    unittest.main()
