"""Passive HA boundary tests with command access rejected, not mocked as success."""
from datetime import datetime, timedelta, timezone
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import test_cleaning_sensor as stage_a

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/intellicenter_manual'


class ReadOnlyBus:
    def __init__(self):
        self.listeners = []

    def async_listen(self, kind, callback):
        if kind != 'call_service':
            raise AssertionError('Unexpected bus subscription')
        self.listeners.append(callback)
        return lambda: self.listeners.remove(callback)

    def __getattr__(self, name):
        raise AssertionError(f'Forbidden HA bus write: {name}')


class ShadowSensorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state_listeners = []
        def track(hass, entities, callback):
            self.state_listeners.append(callback)
            return lambda: self.state_listeners.remove(callback)
        class EntityCategory:
            DIAGNOSTIC = 'diagnostic'
        pkg = types.ModuleType('shadow_sensor_test_pkg')
        pkg.__path__ = [str(ROOT)]
        stubs = {
            pkg.__name__: pkg,
            'homeassistant.components.sensor': types.SimpleNamespace(SensorEntity=stage_a.Entity),
            'homeassistant.core': types.SimpleNamespace(callback=lambda f: f),
            'homeassistant.helpers.entity': types.SimpleNamespace(EntityCategory=EntityCategory),
            'homeassistant.helpers.event': types.SimpleNamespace(async_track_state_change_event=track),
        }
        modules = patch.dict(sys.modules, stubs)
        modules.start()
        self.addCleanup(modules.stop)
        def load(name):
            spec = importlib.util.spec_from_file_location(f'{pkg.__name__}.{name}', ROOT / f'{name}.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        self.obs = load('observation')
        self.module = load('cleaning_shadow_sensor')
        self.now = datetime(2026, 10, 24, tzinfo=timezone.utc)
        self.module.datetime = types.SimpleNamespace(now=lambda tz: self.now)
        self.states = {k: v for k, (v, _) in self.module.POLICY.items()}
        self.fanout = stage_a.Fanout(self.snapshot())
        runtime = types.SimpleNamespace(transport=stage_a.ReadOnlyTransport(), observation_fanout=self.fanout)
        self.entry = types.SimpleNamespace(entry_id='test', runtime_data=runtime,
            options={'pool_cleaning_shadow_enabled': True, 'native_command_authority': True})
        self.bus = ReadOnlyBus()
        self.hass = types.SimpleNamespace(bus=self.bus, services=stage_a.NoCommands(),
            states=types.SimpleNamespace(get=lambda key: None if key not in self.states else types.SimpleNamespace(state=self.states[key])))
        self.entity = self.module.CleaningShadowSensor(self.entry)
        self.entity.hass = self.hass
        await self.entity.async_added_to_hass()
        self.addAsyncCleanup(self.entity.async_will_remove_from_hass)

    def snapshot(self, cleaning=False, pool=False, spa=False, rpm=0, freeze=False, mode='AUTO'):
        m = self.obs
        return m.ReadObservation(True, self.now,
            (m.BodyObservation('B1101', pool, False, 76, 90, 'H0002'),
             m.BodyObservation('B1202', spa, False, 97, 98, 'H0001')),
            (m.CircuitObservation('FTR03', cleaning),),
            (m.TelemetryObservation('pump_rpm', rpm), m.TelemetryObservation('system_mode', mode)), freeze)

    def emit(self, seconds=1, **changes):
        self.now += timedelta(seconds=seconds)
        self.fanout.emit(self.snapshot(**changes))
        return self.entity.extra_state_attributes

    def service(self, mode='heat', entity_id='climate.pool_thermostat', **extra):
        event = types.SimpleNamespace(data={'domain':'climate', 'service':'set_hvac_mode',
            'service_data':{'entity_id':entity_id, 'hvac_mode':mode}, **extra})
        self.bus.listeners[0](event)
        return self.entity.extra_state_attributes

    def assert_observation_only(self, attrs):
        self.assertFalse(attrs['shadow_enabled'])
        self.assertFalse(attrs['command_authority'])
        self.assertFalse(attrs['pool_off_eligible'])
        self.assertFalse(attrs['physical_verification'])
        self.assertEqual(attrs['claim'], 'none')
        self.assertEqual(attrs['commands'], ())
        self.assertEqual(attrs['would_action'], 'none')

    async def test_default_entity_disabled_and_options_do_not_enable_arbitration(self):
        self.assertFalse(self.entity._attr_entity_registry_enabled_default)
        self.assertEqual(self.entity._attr_entity_category, 'diagnostic')
        self.assert_observation_only(self.emit(cleaning=True))
        self.assertEqual(len(self.bus.listeners), 1)
        self.assertEqual(len(self.state_listeners), 1)

    async def test_service_intent_is_not_dispatch_ack_or_native_attribution(self):
        self.emit(cleaning=True)
        attrs = self.service()
        event = attrs['evidence'][-1]
        self.assertEqual(event['kind'], 'ha_pool_service_intent')
        self.assertEqual(event['dispatch_ack'], 'not_observed')
        self.assert_observation_only(attrs)
        attrs = self.emit(cleaning=True, pool=True, rpm=3000)
        self.assertEqual(attrs['evidence'][-1]['kind'], 'motor_running_observed')
        self.assertEqual(attrs['evidence'][-2]['origin'], 'unknown')
        self.assert_observation_only(attrs)

    async def test_no_service_context_or_user_data_is_retained(self):
        self.emit(cleaning=True)
        attrs = self.service(context={'id':'private_context','user_id':'private_user'}, token='private_token')
        self.assertNotIn('private_', str(attrs))

    async def test_unrelated_spa_target_source_and_unresolved_targets_are_not_pool_intent(self):
        self.emit(cleaning=True)
        revision = self.entity._shadow.revision
        self.service(entity_id='climate.hot_tub_thermostat')
        self.service(service='set_temperature')
        self.service(service_data={'device_id':'unresolved', 'hvac_mode':'heat'})
        self.assertEqual(self.entity._shadow.revision, revision)

    async def test_turn_on_turn_off_and_entity_lists_are_read_only(self):
        self.emit(cleaning=True)
        for service in ('turn_on', 'turn_off'):
            attrs = self.service(service=service, service_data={'entity_id':['climate.pool_thermostat']})
            self.assertEqual(attrs['evidence'][-1]['requested_active'], service == 'turn_on')
            self.assert_observation_only(attrs)

    async def test_native_activation_release_and_timer_do_not_issue_commands(self):
        self.assert_observation_only(self.emit(cleaning=True))
        attrs = self.emit(cleaning=False)
        self.assertEqual(attrs['evidence'][-1]['kind'], 'cleaning_off')
        attrs = self.emit(20)
        self.assert_observation_only(attrs)
        self.assertEqual(attrs['evidence'][-1]['kind'], 'settled_release_candidate')

    async def test_policy_callbacks_never_call_services_or_fire_events(self):
        self.emit(cleaning=True)
        for key in self.module.POLICY:
            self.states[key] = 'unavailable'
            self.state_listeners[0](None)
            self.assert_observation_only(self.entity.extra_state_attributes)
            self.assertIn('unknown_policy', self.entity.extra_state_attributes['suppression_reasons'])
            self.states[key] = self.module.POLICY[key][0]

    async def test_freeze_spa_service_and_outage_cannot_enable_any_control(self):
        for changes in ({'freeze':True}, {'freeze':None}, {'spa':True}, {'mode':'SERVICE'}):
            attrs = self.emit(cleaning=True, **changes)
            self.assert_observation_only(attrs)

    async def test_stale_refresh_discards_episode_without_replay(self):
        self.emit(cleaning=True)
        self.now += timedelta(seconds=121)
        self.fanout.emit(self.fanout.observation)
        self.assertIsNone(self.entity.extra_state_attributes['episode_id'])
        self.assert_observation_only(self.emit(cleaning=True))

    async def test_steady_rpm_jitter_and_native_updates_do_not_publish_history(self):
        self.emit(cleaning=True, pool=True, rpm=3000)
        writes = self.entity.writes
        for i in range(10):
            self.emit(cleaning=True, pool=True, rpm=3000+i)
        self.assertEqual(self.entity.writes, writes)
        self.assertLessEqual(len(self.entity.extra_state_attributes['evidence']), 16)

    async def test_unload_removes_all_subscriptions(self):
        await self.entity.async_will_remove_from_hass()
        self.assertEqual(self.fanout.listeners, [])
        self.assertEqual(self.bus.listeners, [])
        self.assertEqual(self.state_listeners, [])

    async def test_partial_registration_failure_rolls_back_observer_subscriptions(self):
        await self.entity.async_will_remove_from_hass()
        broken = self.module.CleaningShadowSensor(self.entry)
        broken.hass = self.hass
        with patch.object(self.bus, 'async_listen', side_effect=RuntimeError('registration failed')):
            with self.assertRaises(RuntimeError):
                await broken.async_added_to_hass()
        self.assertEqual(self.fanout.listeners, [])
        self.assertEqual(self.state_listeners, [])

    async def test_no_command_storage_timer_or_service_registration_in_new_modules(self):
        prohibited = {'async_call', 'async_fire', 'fire', 'async_register', 'set_body_active',
                      'set_pool_cleaning', 'set_pump_rpm', 'set_configured_pump_program_rpm',
                      'async_save', 'async_delay_save', 'async_create_task', 'reconcile'}
        for name in ('cleaning_shadow.py', 'cleaning_shadow_sensor.py'):
            tree = ast.parse((ROOT / name).read_text())
            calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
            self.assertFalse(calls & prohibited, name)
        platform = (ROOT / 'sensor.py').read_text()
        self.assertIn('async_add_entities([CleaningShadowSensor(entry)])', platform)

    async def test_restart_constructs_new_epoch_and_keeps_flag_off(self):
        old_id = self.emit(cleaning=True)['episode_id']
        await self.entity.async_will_remove_from_hass()
        new = self.module.CleaningShadowSensor(self.entry)
        new.hass = self.hass
        await new.async_added_to_hass()
        self.assertNotEqual(new.extra_state_attributes['episode_id'], old_id)
        self.assert_observation_only(new.extra_state_attributes)
        await new.async_will_remove_from_hass()


if __name__ == '__main__':
    unittest.main()
