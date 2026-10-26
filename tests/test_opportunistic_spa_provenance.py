"""No-hardware verification of native readback provenance."""
import importlib.util
from pathlib import Path
import sys
import unittest

path = Path(__file__).resolve().parents[1] / "custom_components" / "intellicenter_manual" / "opportunistic_spa_provenance.py"
spec = importlib.util.spec_from_file_location("opportunistic_spa_provenance", path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class ProvenanceTests(unittest.TestCase):
    def pending(self, kind=m.CommandKind.SPA_ON):
        return m.Pending(epoch="run-1", command=kind, issued_at_s=100.0, observed_generation=4)

    def readback(self, **kwargs):
        args = dict(observed_at_s=101.0, generation=5, source="Solar", spa_active=True, native_fresh=True)
        args.update(kwargs)
        return m.Readback(**args)

    def check(self, p=None, r=None, epoch="run-1"):
        return m.verify_readback(p or self.pending(), r or self.readback(), current_epoch=epoch)

    def test_valid_native_ack(self):
        self.assertEqual(self.check(), m.ReceiptStatus.VERIFIED)
        self.assertEqual(self.check(self.pending(m.CommandKind.SOURCE_SOLAR)), m.ReceiptStatus.VERIFIED)
        self.assertEqual(self.check(self.pending(m.CommandKind.SPA_OFF), self.readback(spa_active=False)), m.ReceiptStatus.VERIFIED)

    def test_stale_generation_and_unknown_native(self):
        self.assertEqual(self.check(r=self.readback(generation=4)), m.ReceiptStatus.UNPROVEN)
        self.assertEqual(self.check(r=self.readback(native_fresh=False)), m.ReceiptStatus.UNPROVEN)
        self.assertEqual(self.check(r=self.readback(spa_active=None)), m.ReceiptStatus.UNPROVEN)

    def test_timeout_clock_and_restart_epoch(self):
        self.assertEqual(self.check(r=self.readback(observed_at_s=116)), m.ReceiptStatus.EXPIRED)
        self.assertEqual(self.check(r=self.readback(observed_at_s=99)), m.ReceiptStatus.CONFLICT)
        self.assertEqual(self.check(epoch="run-2"), m.ReceiptStatus.CONFLICT)

    def test_nonfinite_receipt_metadata_is_conflict(self):
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(bad=bad):
                self.assertEqual(self.check(r=self.readback(observed_at_s=bad)), m.ReceiptStatus.CONFLICT)
                self.assertEqual(self.check(p=m.Pending("run-1", m.CommandKind.SPA_ON, bad, 4)), m.ReceiptStatus.CONFLICT)
        self.assertEqual(self.check(r=self.readback(generation=5.0)), m.ReceiptStatus.CONFLICT)

    def test_concurrent_writer_never_claimed(self):
        self.assertEqual(self.check(r=self.readback(competing_writer_seen=True)), m.ReceiptStatus.CONFLICT)
        self.assertEqual(self.check(self.pending(m.CommandKind.SOURCE_SOLAR), self.readback(source="Gas")), m.ReceiptStatus.UNPROVEN)


if __name__ == "__main__":
    unittest.main()
