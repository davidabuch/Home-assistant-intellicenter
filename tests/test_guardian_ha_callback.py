"""Exercise the real HA adapter listener through HA's callback dispatch contract."""
import asyncio
import importlib
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_transport_lifecycle_faults import transport_module as native


class GuardianHACallbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.listener = None
        self.services = {}

        def callback(func):
            # The real homeassistant.core.callback uses this marker to avoid
            # executor dispatch for synchronous event-loop-safe callbacks.
            func._hass_callback = True
            return func

        def track(hass, entities, listener):
            self.listener = listener
            return lambda: None

        modules = {name: ModuleType(name) for name in (
            'homeassistant', 'homeassistant.core', 'homeassistant.helpers',
            'homeassistant.helpers.storage', 'homeassistant.helpers.event')}
        modules['homeassistant.core'].callback = callback
        modules['homeassistant.helpers.storage'].Store = object
        modules['homeassistant.helpers.event'].async_track_state_change_event = track
        name = native.__package__ + '.rpm_guardian_ha'
        # Only external HA APIs are substituted; setup, invalidation and
        # publication execute from the actual deployed adapter/core.
        with patch.dict(sys.modules, modules):
            sys.modules.pop(name, None)
            module = importlib.import_module(name)
        self.guardian = module.GuardianHA.__new__(module.GuardianHA)
        self.guardian.listeners = set()
        self.guardian.hass = SimpleNamespace(
            async_add_executor_job=asyncio.to_thread,
            services=SimpleNamespace(
                async_register=lambda domain, name, handler: self.services.update({name: handler}),
                async_remove=lambda *args: None))
        self.guardian.entry = SimpleNamespace(entry_id='test', async_on_unload=lambda func: None)
        self.guardian.transport = SimpleNamespace(
            set_preset_policy_check=lambda func: None,
            set_control_policy_check=lambda func: None)

        async def load(): return None
        async def save(data): pass
        self.guardian.store = SimpleNamespace(async_load=load)
        policy = importlib.import_module(native.__package__ + '.rpm_guardian')
        self.guardian.core = policy.RPMGuardian(
            lambda key: 2600, None, lambda: None, save, notify=self.guardian.publish)
        await self.guardian.setup()
        self.notifications = []
        self.loop_thread = threading.get_ident()

        def entity_write():
            self.assertEqual(threading.get_ident(), self.loop_thread)
            self.assertIs(asyncio.get_running_loop(), self.loop)
            self.notifications.append(self.guardian.core.data['epoch'])

        self.loop = asyncio.get_running_loop()
        self.guardian.subscribe(entity_write)

    async def dispatch(self, old, new):
        event = SimpleNamespace(data={
            'old_state': None if old is None else SimpleNamespace(state=old),
            'new_state': None if new is None else SimpleNamespace(state=new)})
        # Mimic HA's relevant choice: unmarked sync listeners run in executor.
        if getattr(self.listener, '_hass_callback', False):
            self.listener(event)
        else:
            await asyncio.to_thread(self.listener, event)

    async def test_authority_flap_invalidates_and_publishes_on_event_loop(self):
        initial = self.guardian.core.data['epoch']
        await self.dispatch('on', 'off')
        await self.dispatch('off', 'on')
        self.assertEqual(self.guardian.core.data['epoch'], initial + 2)
        self.assertEqual(self.notifications, [initial + 1, initial + 2])

    async def test_attribute_refresh_does_not_invalidate_but_initial_state_does(self):
        initial = self.guardian.core.data['epoch']
        await self.dispatch('on', 'on')
        self.assertEqual(self.notifications, [])
        await self.dispatch(None, 'on')
        self.assertEqual(self.notifications, [initial + 1])

    async def test_setup_queues_scan_without_early_native_reads(self):
        self.assertTrue(self.guardian.core.data['routine_scan_pending'])
        self.assertFalse(self.guardian.core.blocks_normal)

    async def test_service_preserves_request_reason_and_defaults_to_manual(self):
        self.guardian.reconcile = AsyncMock()
        handler = self.services['reconcile_pump_speeds']
        for reason in ('recovery_heartbeat', 'accounting_rollover', 'grid_policy'):
            await handler(SimpleNamespace(data={'entry_id': 'test', 'reason': reason}))
            self.guardian.reconcile.assert_awaited_with(reason)
        await handler(SimpleNamespace(data={'entry_id': 'test'}))
        self.guardian.reconcile.assert_awaited_with('manual')
