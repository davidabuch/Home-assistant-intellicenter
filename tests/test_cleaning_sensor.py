"""Exercise actual HA entity callbacks with forbidden command/event boundaries."""
import ast
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/intellicenter_manual'


class Entity:
    hass = None

    async def async_added_to_hass(self):
        pass

    async def async_will_remove_from_hass(self):
        pass

    def async_write_ha_state(self):
        self.writes = getattr(self, 'writes', 0) + 1


class ReadOnlyTransport:
    def pool_cleaning_circuit_id(self):
        return 'FTR03'

    def __getattr__(self, name):
        raise AssertionError(f'Observer accessed command-capable transport member {name}')


class NoCommands:
    def __getattr__(self, name):
        raise AssertionError(f'Observer attempted HA command/event access: {name}')


class Fanout:
    def __init__(self, observation):
        self.observation = observation
        self.listeners = []

    def subscribe(self, listener):
        listener(self.observation)
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def emit(self, observation):
        self.observation = observation
        for listener in self.listeners:
            listener(observation)


class CleaningEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state_listeners = []
        def track(hass, entities, listener):
            self.state_listeners.append(listener)
            return lambda: self.state_listeners.remove(listener)
        stubs = {
            'homeassistant.components.sensor': types.SimpleNamespace(SensorEntity=Entity),
            'homeassistant.core': types.SimpleNamespace(callback=lambda fn: fn),
            'homeassistant.helpers.event': types.SimpleNamespace(async_track_state_change_event=track),
        }
        parent = types.ModuleType('cleaning_entity_test_pkg')
        parent.__path__ = [str(COMPONENT)]
        stubs[parent.__name__] = parent
        self.modules = patch.dict(sys.modules, stubs)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        def load(name):
            spec = importlib.util.spec_from_file_location(f'{parent.__name__}.{name}', COMPONENT / f'{name}.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        self.observation = load('observation')
        self.module = load('cleaning_sensor')
        self.now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        self.module.datetime = types.SimpleNamespace(now=lambda tz: self.now)
        self.states = {key: expected for key, (expected, _) in self.module.POLICY.items()}
        self.states.update({
            'input_boolean.pool_simple_schedule_owns_pool': 'off',
            'input_boolean.pool_simple_manual_circulation': 'off',
            'input_select.pool_heating_preference': 'Solar',
            'counter.pool_simple_filtration_minutes': '480',
            'sensor.pool_daily_filtration_target': '480',
        })
        self.fanout = Fanout(self.snapshot())
        runtime = types.SimpleNamespace(transport=ReadOnlyTransport(), observation_fanout=self.fanout)
        self.entity = self.module.CleaningObservationSensor(types.SimpleNamespace(entry_id='test', runtime_data=runtime))
        self.entity.hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda key: None if key not in self.states else types.SimpleNamespace(state=self.states[key])),
            services=NoCommands(), bus=NoCommands())
        await self.entity.async_added_to_hass()
        self.addAsyncCleanup(self.entity.async_will_remove_from_hass)

    def snapshot(self, *, cleaning=False, pool=False, spa=False, freeze=False, mode='AUTO'):
        m = self.observation
        return m.ReadObservation(True, self.now,
            (m.BodyObservation('B1101', pool, False, 76, 90, 'H0002'),
             m.BodyObservation('B1202', spa, False, 97, 98, 'H0001')),
            (m.CircuitObservation('FTR03', cleaning), m.CircuitObservation('X0052', False)),
            (m.TelemetryObservation('system_mode', mode), m.TelemetryObservation('pump_rpm', 0)), freeze)

    def emit(self, seconds=1, **kwargs):
        self.now += timedelta(seconds=seconds)
        self.fanout.emit(self.snapshot(**kwargs))
        return self.entity.extra_state_attributes

    async def test_registered_entity_initial_delivery_and_cleanup(self):
        self.assertEqual(self.entity.native_value, 'idle')
        self.assertEqual(len(self.fanout.listeners), 1)
        self.assertEqual(len(self.state_listeners), 1)
        self.assertFalse(self.entity.extra_state_attributes['command_authority'])
        self.assertEqual(self.entity.extra_state_attributes['stage'], 'A_observation_only')

    async def test_real_entity_proposes_heat_activation_without_dispatch(self):
        attrs = self.emit(cleaning=True)
        self.assertEqual(attrs['action'], 'would_request_pool_on')
        self.assertEqual(attrs['claim'], 'none')
        self.assertEqual(attrs['commands'], ())
        self.assertEqual(attrs['pump_rpm_at_decision'], 0)
        self.assertFalse(attrs['physically_verified'])

    async def test_manual_master_off_cannot_create_command_intent(self):
        self.states['input_boolean.pool_automatic_ownership'] = 'off'
        self.assertEqual(self.emit(cleaning=True)['action'], 'none')
        self.assertEqual(self.states['input_boolean.pool_automatic_ownership'], 'off')

    async def test_all_policy_gates_are_fail_closed_in_entity_callbacks(self):
        for key in self.module.POLICY:
            with self.subTest(key=key):
                self.emit(cleaning=False)
                self.states[key] = 'unavailable'
                attrs = self.emit(cleaning=True)
                self.assertEqual(attrs['action'], 'none')
                self.assertIn('unknown_policy', attrs['suppression_reasons'])
                self.states[key] = self.module.POLICY[key][0]

    async def test_native_freeze_service_and_spa_prevent_start(self):
        for kwargs in ({'freeze': True}, {'freeze': None}, {'mode': 'SERVICE'}, {'spa': True}):
            with self.subTest(kwargs=kwargs):
                self.emit(cleaning=False)
                self.assertEqual(self.emit(cleaning=True, **kwargs)['action'], 'none')

    async def test_guardian_degraded_and_grid_outage_suppress_intent(self):
        for key, value in (('sensor.intellicenter_rpm_guardian', 'RECOVERY_REQUIRED'),
                           ('input_boolean.grid_outage_active', 'on')):
            self.emit(cleaning=False)
            self.states[key] = value
            self.assertEqual(self.emit(cleaning=True)['action'], 'none')
            self.states[key] = self.module.POLICY[key][0]

    async def test_heating_preference_and_target_changes_are_observed_only(self):
        self.emit(cleaning=True)
        self.states['input_select.pool_heating_preference'] = 'Gas'
        self.states['sensor.pool_target_temperature'] = '92'
        self.state_listeners[0](None)
        attrs = self.entity.extra_state_attributes
        self.assertEqual(attrs['controller_context_at_decision']['input_select.pool_heating_preference'], 'Gas')
        self.assertEqual(attrs['controller_context_at_decision']['sensor.pool_target_temperature'], '92')
        self.assertEqual(attrs['commands'], ())

    async def test_release_diagnostics_preserve_current_solar_and_filtration_context(self):
        for solar, credit in (('on', '480'), ('off', '400'), ('off', '480')):
            self.states['binary_sensor.solar_delivery_confirmed'] = solar
            self.states['counter.pool_simple_filtration_minutes'] = credit
            self.emit(cleaning=True, pool=True)
            self.emit(cleaning=False, pool=True)
            attrs = self.emit(20, cleaning=False, pool=True)
            self.assertEqual(attrs['action'], 'would_reconcile_existing_controller')
            self.assertEqual(attrs['controller_context_at_decision']['counter.pool_simple_filtration_minutes'], credit)
            self.assertFalse(attrs['bypass_manual_grace'])
            self.assertEqual(attrs['commands'], ())

    async def test_policy_listener_never_manufactures_native_release(self):
        self.emit(cleaning=True)
        self.emit(cleaning=False)
        self.now += timedelta(seconds=30)
        self.state_listeners[0](None)
        self.assertEqual(self.entity.native_value, 'release_pending')
        self.assertIsNone(self.entity.extra_state_attributes['release_proposal'])

    async def test_periodic_refresh_invalidates_stale_native_state(self):
        self.emit(cleaning=True)
        self.now += timedelta(seconds=121)
        self.fanout.emit(self.fanout.observation)
        self.assertEqual(self.entity.native_value, 'uncertain')
        self.assertEqual(self.entity.extra_state_attributes['action'], 'none')

    async def test_steady_native_updates_do_not_generate_recorder_churn(self):
        self.emit(cleaning=True)
        writes = self.entity.writes
        for _ in range(10):
            self.emit(cleaning=True)
        self.assertEqual(self.entity.writes, writes)

    async def test_sensor_platform_setup_preserves_existing_entities(self):
        spec = importlib.util.spec_from_file_location('cleaning_entity_test_pkg.sensor', COMPONENT / 'sensor.py')
        platform = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(platform)
        created, unload = [], []
        runtime = types.SimpleNamespace(transport=types.SimpleNamespace(connected=False),
            observation_fanout=self.fanout, guardian=object())
        entry = types.SimpleNamespace(entry_id='setup', runtime_data=runtime,
                                      async_on_unload=unload.append)
        await platform.async_setup_entry(self.entity.hass, entry, lambda entities: created.extend(entities))
        self.assertEqual(sum(isinstance(e, platform.NativeTelemetry) for e in created), len(platform.MEASUREMENTS))
        self.assertEqual(sum(isinstance(e, platform.GuardianStatus) for e in created), 1)
        self.assertEqual(sum(isinstance(e, self.module.CleaningObservationSensor) for e in created), 1)
        for unsubscribe in unload:
            unsubscribe()

    async def test_only_read_only_apis_exist_in_new_modules(self):
        forbidden = {'async_call', 'async_fire', 'fire', 'set_body_active', 'set_pool_cleaning',
                     'set_pump_rpm', 'set_pump_circuit_speed', 'reconcile', 'async_delay_save',
                     'async_save', 'async_create_task'}
        for name in ('cleaning_observer.py', 'cleaning_sensor.py'):
            tree = ast.parse((COMPONENT / name).read_text())
            calls = {node.func.attr for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
            self.assertFalse(calls & forbidden)
        setup = (COMPONENT / 'sensor.py').read_text()
        self.assertIn('async_add_entities([CleaningObservationSensor(entry)])', setup)


if __name__ == '__main__':
    unittest.main()
