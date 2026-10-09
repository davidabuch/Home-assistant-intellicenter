"""Isolated transport lifecycle fault injection; never opens a controller socket.

Exercise the actual transport callback methods with a synthetic model and
clock-independent freshness assertions. No Home Assistant or network access.
"""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "custom_components/intellicenter_manual"
PKG = "isolated_intellicenter_test"
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules[PKG] = pkg

# Import the real adapter, but replace only the external socket/protocol library.
spec = importlib.util.spec_from_file_location(f"{PKG}.observation", ROOT / "observation.py")
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)

fake = types.ModuleType("pyintellicenter")
class FakeModel:
    def __init__(self, *args, **kwargs):
        pass
    def get_by_type(self, kind):
        return ()
    def add_object(self, objnam, params):
        return None
class FakeController:
    def __init__(self, *args, **kwargs):
        pass
class FakeHandler:
    def __init__(self, *args, **kwargs):
        pass
for name, obj in {"ICConnectionHandler": FakeHandler, "ICModelController": FakeController,
                  "PoolModel": FakeModel, "LIGHT_EFFECTS": {}}.items():
    setattr(fake, name, obj)
for name in ("STATUS_ATTR", "STATUS_ON", "STATUS_OFF", "HEATER_ATTR",
             "BODY_TYPE", "CIRCUIT_TYPE", "SENSE_TYPE", "PUMP_TYPE", "SYSTEM_TYPE",
             "CHEM_TYPE", "BODY_ATTR", "PRIM_ATTR", "SEC_ATTR", "SALT_ATTR",
             "LOTMP_ATTR", "LSTTMP_ATTR", "HTMODE_ATTR", "SOURCE_ATTR",
             "RPM_ATTR", "GPM_ATTR", "PWR_ATTR", "MIN_ATTR", "MAX_ATTR",
             "VER_ATTR", "SERVICE_ATTR", "OBJTYP_ATTR", "SNAME_ATTR",
             "HITMP_ATTR", "MODE_ATTR", "VOL_ATTR", "PARENT_ATTR", "SUBTYP_ATTR"):
    setattr(fake, name, name)
fake.STATUS_ON = "ON"
fake.STATUS_OFF = "OFF"
sys.modules["pyintellicenter"] = fake
attrs = types.ModuleType("pyintellicenter.attributes")
attrs.ALL_ATTRIBUTES_BY_TYPE = {}
sys.modules["pyintellicenter.attributes"] = attrs

spec = importlib.util.spec_from_file_location(f"{PKG}.transport", ROOT / "transport.py")
transport_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = transport_module
spec.loader.exec_module(transport_module)


class TransportLifecycleFaultTests(unittest.TestCase):
    def setUp(self):
        self.transport = transport_module.IntelliCenterManualTransport("127.0.0.1")
        self.transport._started = True
        self.events = []
        self.transport.set_observation_callback(
            lambda: self.events.append(self.transport.read_observation())
        )

    def test_disconnect_reconnect_requires_new_native_update(self):
        self.transport._connection_changed(True)
        self.assertFalse(self.transport.read_observation().connected)
        self.transport._model_updated()
        self.assertTrue(self.transport.read_observation().connected)

        self.transport._connection_changed(False)
        self.assertFalse(self.transport.read_observation().connected)
        self.assertIsNone(self.transport._observed_at)

        self.transport._connection_changed(True)
        self.assertFalse(self.transport.read_observation().connected)
        self.assertIsNone(self.transport._observed_at)

        self.transport._model_updated()
        self.assertTrue(self.transport.read_observation().connected)
        self.assertEqual([event.connected for event in self.events],
                         [False, True, False, False, True])

    def test_stale_snapshot_invalidates_even_while_socket_connected(self):
        self.transport._connection_changed(True)
        self.transport._model_updated()
        self.assertTrue(self.transport.read_observation().connected)
        self.transport._observed_at = datetime.now(timezone.utc) - timedelta(seconds=121)
        self.assertFalse(self.transport.read_observation().connected)
        self.assertIsNone(self.transport.read_observation().measurement("pump_rpm"))
        self.transport._model_updated()
        self.assertTrue(self.transport.read_observation().connected)

    def test_retry_drops_previous_observation(self):
        self.transport._connection_changed(True)
        self.transport._model_updated()
        self.transport.handler.on_retrying(30)
        self.assertFalse(self.transport.read_observation().connected)
        self.transport.handler.on_reconnected(self.transport.controller)
        self.assertFalse(self.transport.read_observation().connected)
        self.transport.handler.on_updated(self.transport.controller, {})
        self.assertTrue(self.transport.read_observation().connected)

if __name__ == "__main__":
    unittest.main()
