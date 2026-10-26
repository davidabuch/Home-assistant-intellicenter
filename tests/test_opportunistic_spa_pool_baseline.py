"""Protect the commissioned Pool scheduler from incidental Spa changes.

This SHA is the Git blob computed from the checked-out scheduler bytes
at the Spa branch baseline. Any intentional Pool scheduler change must receive a separate
review and explicit baseline update; opportunistic Spa work must not silently
change it. This test checks repository content, not live HA deployment.
"""
from hashlib import sha1
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEDULER = ROOT / "ha_automations" / "pool_simple_solar_and_filtration.json"
BASELINE_GIT_BLOB_SHA = "9e551fb1117a49c19e26ca53bf18e8c68bdb0640"


class ExistingPoolSchedulerProtection(unittest.TestCase):
    def test_commissioned_pool_scheduler_unchanged(self):
        raw = SCHEDULER.read_bytes()
        git_blob = sha1(b"blob " + str(len(raw)).encode() + b"\\0" + raw).hexdigest()
        self.assertEqual(
            git_blob, BASELINE_GIT_BLOB_SHA,
            "Existing Pool scheduler changed during Spa development. "
            "Stop and review Pool commissioning regressions separately.",
        )


if __name__ == "__main__":
    unittest.main()
