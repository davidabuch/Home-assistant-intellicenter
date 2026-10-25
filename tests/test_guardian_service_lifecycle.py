"""Actual adapter lifecycle with Core-shaped registry/entry boundaries, no IO.

Core 2026.10.2 removes entry callbacks LIFO, marks reload unavailable, awaits
unload, then setup under the same entry lock. The registry raises ServiceNotFound
for an absent handler. Those external APIs alone are substituted here.
"""
import ast
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/intellicenter_manual'
NAMES = ('reconcile_pump_speeds', 'inspect_native_rpm_readback',
         'apply_rpm_configuration', 'configure_rpm_guardian')
DOMAIN = 'intellicenter_manual'


class ServiceNotFound(Exception):
    pass


class ServiceValidationError(Exception):
    pass


class Registry:
    def __init__(self):
        self.handlers = {}
        self.registrations = []
        self.removals = []

    def async_register(self, domain, name, handler):
        self.handlers[domain, name] = handler
        self.registrations.append((domain, name))

    def async_remove(self, domain, name):
        self.handlers.pop((domain, name), None)
        self.removals.append((domain, name))

    async def call(self, name, **data):
        try:
            fn = self.handlers[DOMAIN, name]
        except KeyError:
            raise ServiceNotFound(f'Action {DOMAIN}.{name} not found') from None
        await fn(types.SimpleNamespace(data=data))


class Entry:
    def __init__(self, entry_id='pool', domain=DOMAIN):
        self.entry_id, self.domain = entry_id, domain
        self.state = 'setup_in_progress'
        self.callbacks = []

    def async_on_unload(self, callback):
        self.callbacks.append(callback)

    def cleanup(self):
        while self.callbacks:
            self.callbacks.pop()()


class GuardianServiceLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = Registry()
        self.entries = {}
        self.listener_count = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        self.fail_revision = False
        self.fail_save = False
        self.saved = []
        self.native_calls = []

        def track(hass, entities, listener):
            self.listener_count += 1
            def remove(): self.listener_count -= 1
            return remove

        def get_entry(hass, domain, entry_id):
            entry = self.entries.get(entry_id)
            if entry is None or entry.domain != domain or entry.state != 'loaded':
                raise ServiceValidationError(f'Config entry {entry_id} is not loaded for {domain}')
            return entry

        modules = {n: types.ModuleType(n) for n in (
            'homeassistant', 'homeassistant.core', 'homeassistant.exceptions',
            'homeassistant.helpers', 'homeassistant.helpers.storage',
            'homeassistant.helpers.event', 'homeassistant.helpers.service')}
        modules['homeassistant.core'].callback = lambda fn: fn
        modules['homeassistant.exceptions'].ServiceValidationError = ServiceValidationError
        modules['homeassistant.helpers.storage'].Store = object
        modules['homeassistant.helpers.event'].async_track_state_change_event = track
        modules['homeassistant.helpers.service'].async_get_config_entry = get_entry
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        pkg = types.ModuleType('guardian_service_lifecycle_pkg')
        pkg.__path__ = [str(ROOT)]
        sys.modules[pkg.__name__] = pkg
        self.pkg = pkg.__name__
        spec = importlib.util.spec_from_file_location(f'{self.pkg}.rpm_guardian_ha', ROOT/'rpm_guardian_ha.py')
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        self.hass = types.SimpleNamespace(services=self.registry,
            config_entries=types.SimpleNamespace(async_get_entry=self.entries.get),
            async_add_executor_job=self.executor)
        self.entry = Entry()
        self.entries['pool'] = self.entry
        await self.component_setup()

    async def executor(self, fn):
        self.entered.set()
        await self.release.wait()
        if self.fail_revision: raise RuntimeError('revision read failed')
        return 'test-build'

    async def component_setup(self):
        # Execute the actual component hook body without importing unrelated
        # pyintellicenter/HA platform dependencies into the offline harness.
        tree = ast.parse((ROOT/'__init__.py').read_text())
        hooks = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'async_setup']
        if not hooks:
            return  # Pre-fix baseline has no component-lifetime registration.
        scope = {'__package__': self.pkg, 'HomeAssistant': object}
        exec(compile(ast.Module(body=hooks, type_ignores=[]), str(ROOT/'__init__.py'), 'exec'), scope)
        await scope['async_setup'](self.hass, {})

    def guardian(self, entry=None):
        entry = entry or self.entry
        g = self.module.GuardianHA.__new__(self.module.GuardianHA)
        g.hass, g.entry = self.hass, entry
        g.listeners = set()
        g.transport = types.SimpleNamespace(set_preset_policy_check=lambda fn: None,
                                            set_control_policy_check=lambda fn: None)
        async def load(): return None
        async def save(data):
            if self.fail_save: raise RuntimeError('storage write failed')
            self.saved.append(dict(data))
        policy = sys.modules[f'{self.pkg}.rpm_guardian']
        def no_native(*args):
            self.native_calls.append(args)
            raise AssertionError('Unexpected native IO')
        g.core = policy.RPMGuardian(no_native, no_native, no_native, save, notify=g.publish)
        g.store = types.SimpleNamespace(async_load=load)
        g.reconcile = AsyncMock()
        return g

    async def setup_entry(self, guardian):
        guardian.entry.state = 'setup_in_progress'
        try:
            await guardian.setup()
        except BaseException:
            guardian.entry.cleanup()  # Core also cleans up failed entry setup.
            guardian.entry.state = 'setup_error'
            raise
        guardian.entry.runtime_data = types.SimpleNamespace(guardian=guardian)
        guardian.entry.state = 'loaded'

    def unload(self, entry=None):
        entry = entry or self.entry
        entry.state = 'unload_in_progress'
        entry.cleanup()
        if hasattr(entry, 'runtime_data'): del entry.runtime_data
        entry.state = 'not_loaded'

    async def call(self, **data):
        await self.registry.call('reconcile_pump_speeds', entry_id='pool', **data)

    async def test_component_service_exists_before_entry_setup(self):
        self.assertIn((DOMAIN, NAMES[0]), self.registry.handlers)
        with self.assertRaises(ServiceValidationError):
            await self.call(reason='startup')
        self.assertEqual(self.native_calls, [])

    async def test_reload_gap_service_remains_registered_during_initialization(self):
        old = self.guardian()
        await self.setup_entry(old)
        await self.call(reason='recovery_heartbeat')
        old.reconcile.assert_awaited_once_with('recovery_heartbeat')
        self.unload()
        new = self.guardian()
        self.entered.clear()
        self.release.clear()
        task = asyncio.create_task(self.setup_entry(new))
        await self.entered.wait()  # Real setup is suspended before registration.
        try:
            self.assertIn((DOMAIN, NAMES[0]), self.registry.handlers)
            with self.assertRaises(ServiceValidationError):
                await self.call(reason='recovery_heartbeat')
            new.reconcile.assert_not_awaited()
        finally:
            self.release.set()
            await task
        await self.call(reason='recovery_heartbeat')
        new.reconcile.assert_awaited_once_with('recovery_heartbeat')
        self.assertEqual(self.native_calls, [])

    async def test_successful_setup_and_service_reason_and_default(self):
        g = self.guardian()
        await self.setup_entry(g)
        await self.call(reason='solar_delivery_started')
        g.reconcile.assert_awaited_with('solar_delivery_started')
        await self.call()
        g.reconcile.assert_awaited_with('manual')
        self.assertTrue(g.core.data['routine_scan_pending'])

    async def test_unloaded_entry_is_unavailable_not_unknown_action(self):
        await self.setup_entry(self.guardian())
        self.unload()
        for name in NAMES:
            self.assertIn((DOMAIN, name), self.registry.handlers)
            with self.assertRaises(ServiceValidationError):
                await self.registry.call(name, entry_id='pool')
        self.assertEqual(self.listener_count, 0)
        self.assertEqual(self.registry.removals, [])

    async def test_repeated_reloads_do_not_register_or_remove_entry_services(self):
        handlers = dict(self.registry.handlers)
        for _ in range(5):
            await self.setup_entry(self.guardian())
            await self.call(reason='recovery_heartbeat')
            self.unload()
        self.assertEqual(self.registry.handlers, handlers)
        self.assertEqual(len(self.registry.registrations), 4)
        self.assertEqual(self.registry.removals, [])
        self.assertEqual(self.listener_count, 0)

    async def test_setup_failure_before_registration_recovers_without_unknown_action(self):
        self.fail_revision = True
        with self.assertRaisesRegex(RuntimeError, 'revision read failed'):
            await self.setup_entry(self.guardian())
        with self.assertRaises(ServiceValidationError):
            await self.call(reason='startup')
        self.fail_revision = False
        g = self.guardian()
        await self.setup_entry(g)
        await self.call(reason='recovery_heartbeat')
        g.reconcile.assert_awaited_once()

    async def test_storage_setup_failure_does_not_remove_component_service(self):
        self.fail_save = True
        with self.assertRaisesRegex(RuntimeError, 'storage write failed'):
            await self.setup_entry(self.guardian())
        self.assertIn((DOMAIN, NAMES[0]), self.registry.handlers)
        self.assertEqual(self.listener_count, 0)
        with self.assertRaises(ServiceValidationError): await self.call()
        self.fail_save = False
        await self.setup_entry(self.guardian())
        await self.call(reason='startup')

    async def test_old_entry_cleanup_cannot_remove_or_route_new_entry_services(self):
        old = self.guardian()
        await self.setup_entry(old)
        old_cleanup = list(self.entry.callbacks)
        self.unload()
        new = self.guardian()
        await self.setup_entry(new)
        # Core serializes same-entry reloads; this additionally challenges stale
        # callbacks after a new instance exists. None may own domain services.
        # Avoid replaying the listener remover; service-removal callbacks alone
        # were the pre-fix competing ownership concern.
        for fn in old_cleanup:
            if 'async_remove' in fn.__code__.co_names:
                fn()
        await self.call(reason='grid_policy')
        new.reconcile.assert_awaited_once_with('grid_policy')
        old.reconcile.assert_not_awaited()
        self.assertEqual(self.registry.removals, [])

    async def test_two_entries_route_exactly_and_unload_is_isolated(self):
        other = Entry('other')
        self.entries['other'] = other
        a, b = self.guardian(), self.guardian(other)
        await self.setup_entry(a)
        await self.setup_entry(b)
        await self.call(reason='before_filtration')
        a.reconcile.assert_awaited_once_with('before_filtration')
        b.reconcile.assert_not_awaited()
        self.unload()
        await self.registry.call(NAMES[0], entry_id='other', reason='startup')
        b.reconcile.assert_awaited_once_with('startup')

    async def test_missing_wrong_domain_unknown_and_not_ready_entry_never_dispatch(self):
        g = self.guardian()
        await self.setup_entry(g)
        other = Entry('foreign', 'another_domain')
        other.state = 'loaded'
        self.entries['foreign'] = other
        for entry_id in (None, '', 'missing', 'foreign'):
            with self.assertRaises(ServiceValidationError):
                await self.registry.call(NAMES[0], entry_id=entry_id)
        g.reconcile.assert_not_awaited()

    async def test_missing_guardian_runtime_fails_explicitly(self):
        self.entry.state = 'loaded'
        self.entry.runtime_data = types.SimpleNamespace(guardian=None)
        with self.assertRaises(ServiceValidationError): await self.call()

    async def test_guardian_failure_propagates_without_success_or_retry_masking(self):
        g = self.guardian()
        await self.setup_entry(g)
        g.reconcile.side_effect = RuntimeError('verified readback failed')
        with self.assertRaisesRegex(RuntimeError, 'verified readback failed'):
            await self.call(reason='recovery_heartbeat')
        self.assertEqual(g.reconcile.await_count, 1)

    async def test_loaded_runtime_services_keep_apply_inspect_and_configure_guards(self):
        g = self.guardian()
        await self.setup_entry(g)
        g.core.apply = AsyncMock()
        g.core.persist = AsyncMock()
        g.core.enable = AsyncMock()
        g.refresh_native_speed_diagnostics = AsyncMock(return_value={'pool': {'matches_expected': True}})
        g.hass.bus = types.SimpleNamespace(async_fire=Mock())
        g.conditions = lambda: types.SimpleNamespace(fresh=True, raw_outage=False,
            qualified=False, minimum=600, maximum=3450)
        await self.registry.call('apply_rpm_configuration', entry_id='pool')
        g.core.apply.assert_awaited_once_with()
        await self.registry.call('inspect_native_rpm_readback', entry_id='pool')
        g.hass.bus.async_fire.assert_called_once_with('intellicenter_native_rpm_readback_diagnostic',
            {'programs': {'pool': {'matches_expected': True}}})
        with self.assertRaisesRegex(ValueError, 'Explicit supervised'):
            await self.registry.call('configure_rpm_guardian', entry_id='pool', enabled=True)
        g.core.enable.assert_not_awaited()
        await self.registry.call('configure_rpm_guardian', entry_id='pool',
            confirm='AUTHORIZE_RPM_GUARDIAN_COMMISSIONING', enabled=True,
            approve_running_pool_write=True, settling_seconds=300)
        g.core.enable.assert_awaited_once_with(True, running_pool_approved=True)
        g.conditions = lambda: types.SimpleNamespace(fresh=False)
        with self.assertRaisesRegex(RuntimeError, 'Fresh native observation'):
            await self.registry.call('inspect_native_rpm_readback', entry_id='pool')
        self.assertEqual(self.native_calls, [])

    async def test_unload_in_progress_and_failed_unload_do_not_resolve_old_runtime(self):
        g = self.guardian()
        await self.setup_entry(g)
        for state in ('unload_in_progress', 'failed_unload', 'setup_in_progress', 'setup_error'):
            self.entry.state = state
            with self.assertRaises(ServiceValidationError): await self.call()
        g.reconcile.assert_not_awaited()
        self.entry.state = 'loaded'
        await self.call(reason='recovery_heartbeat')
        g.reconcile.assert_awaited_once_with('recovery_heartbeat')

    async def test_blocked_startup_calls_do_not_run_against_partially_loaded_guardian(self):
        self.entered.clear()
        self.release.clear()
        g = self.guardian()
        task = asyncio.create_task(self.setup_entry(g))
        await self.entered.wait()
        try:
            for reason in ('startup', 'grid_policy', 'recovery_heartbeat'):
                with self.assertRaises(ServiceValidationError): await self.call(reason=reason)
            g.reconcile.assert_not_awaited()
        finally:
            self.release.set()
            await task
        self.assertTrue(g.core.data['routine_scan_pending'])
        g.reconcile.assert_not_awaited()
        await self.call(reason='recovery_heartbeat')
        g.reconcile.assert_awaited_once_with('recovery_heartbeat')

    async def test_close_calls_keep_original_reason_and_do_not_queue_stale_replay(self):
        g = self.guardian()
        await self.setup_entry(g)
        reasons = ['recovery_heartbeat', 'grid_policy', 'startup']
        await asyncio.gather(*(self.call(reason=reason) for reason in reasons))
        self.assertEqual([c.args[0] for c in g.reconcile.await_args_list], reasons)
        self.unload()
        with self.assertRaises(ServiceValidationError): await self.call(reason='startup')
        next_g = self.guardian()
        await self.setup_entry(next_g)
        next_g.reconcile.assert_not_awaited()
        await self.call(reason='recovery_heartbeat')
        next_g.reconcile.assert_awaited_once_with('recovery_heartbeat')


if __name__ == '__main__':
    unittest.main()
