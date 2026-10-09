"""Exercise subscription lifecycle and callback fanout without HA installation."""
from datetime import datetime, timezone
import importlib.util
import asyncio
import threading
from pathlib import Path
import sys
import types
import unittest

PKG = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual"
parent = types.ModuleType("test_ic_pkg")
parent.__path__ = [str(PKG)]
sys.modules.setdefault("test_ic_pkg", parent)

def load(name):
    spec = importlib.util.spec_from_file_location(f"test_ic_pkg.{name}", PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

load("observation")
fanout_module = load("observation_coordinator")

class FakeTransport:
    def __init__(self):
        self.callback = None
        self.count = 0

    def set_observation_callback(self, callback):
        self.callback = callback

    def read_observation(self):
        self.count += 1
        return self.count

class FanoutTests(unittest.TestCase):
    def test_subscribe_refresh_unsubscribe_close(self):
        transport = FakeTransport()
        fanout = fanout_module.ObservationFanout(transport, asyncio.new_event_loop())
        seen = []
        remove = fanout.subscribe(seen.append)
        self.assertEqual(seen, [1])
        fanout.start()
        self.assertEqual(seen, [1, 2])
        transport.callback()
        self.assertEqual(seen, [1, 2, 3])
        remove()
        fanout.refresh()
        self.assertEqual(seen, [1, 2, 3])
        fanout.close()
        self.assertIsNone(transport.callback)
        with self.assertRaises(RuntimeError):
            fanout.subscribe(seen.append)

    def test_late_cross_thread_callback_after_close_does_not_touch_closed_loop(self):
        transport = FakeTransport()
        loop = asyncio.new_event_loop()
        fanout = fanout_module.ObservationFanout(transport, loop)
        fanout.start()
        callback = transport.callback
        fanout.close()
        loop.close()
        errors = []
        worker = threading.Thread(target=lambda: self._capture_callback_error(callback, errors))
        worker.start()
        worker.join()
        self.assertEqual(errors, [])
        self.assertEqual(transport.count, 1)

    @staticmethod
    def _capture_callback_error(callback, errors):
        try:
            callback()
        except Exception as exc:
            errors.append(exc)

    def test_listener_failure_isolated_and_close_stops_delivery(self):
        transport = FakeTransport()
        loop = asyncio.new_event_loop()
        try:
            fanout = fanout_module.ObservationFanout(transport, loop)
            healthy = []
            fanout.start()
            fanout.subscribe(healthy.append)
            def broken(_):
                raise ValueError("synthetic listener fault")
            with self.assertRaises(ValueError):
                fanout.subscribe(broken)
            # Failed initial delivery must roll back the subscription.
            self.assertNotIn(broken, fanout._listeners)
            transport.callback()
            self.assertEqual(healthy, [2, 4])
            fanout.close()
            self.assertIsNone(transport.callback)
            fanout.refresh()
            self.assertEqual(healthy, [2, 4])
        finally:
            loop.close()

if __name__ == "__main__":
    unittest.main()
