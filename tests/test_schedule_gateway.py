"""Schedule commands through production dispatch and native confirmation.

Only external protocol IO and incoming telemetry are synthetic. The actual
transport allowlist, live authority/outage checks, protocol write gate, dispatch
lock and body confirmation execute. No Home Assistant or socket is started.
"""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_lightweight_schedule import Replay, Halt, POOL, OWNS, TARGET, MASTER
from test_transport_lifecycle_faults import transport_module as native


def production_outage_check(states):
    """Bind the exact HA safety callback to in-memory states and a noon clock."""
    path = Path(native.__file__).with_name('__init__.py')
    tree = ast.parse(path.read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == '_outage_command_allowed')
    scope = dict(vars(native))
    scope.update(
        hass=SimpleNamespace(states=SimpleNamespace(
            get=lambda key: SimpleNamespace(state=states.get(key, 'unknown')))),
        dt_util=SimpleNamespace(as_local=lambda d: d,
            utcnow=lambda: datetime(2026, 10, 15, 12, tzinfo=timezone.utc)),
    )
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
    return scope['_outage_command_allowed']


class ScheduleGatewayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.replay = Replay(**{TARGET:'71'})
        self.transport = native.IntelliCenterManualTransport('127.0.0.1')
        self.transport._started = self.transport._connected = True
        self.authority = True
        self.transport.set_manual_authority_check(lambda: self.authority)
        self.transport.set_outage_command_check(production_outage_check(self.replay.states))
        self.transport.arm_manual_thermostats()
        self.delivered = []
        self.actual_active = True
        self.actual_source = 'H0002'
        self.pending_source = None
        self.pending = None
        self.old_observed_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.stale = False
        self.hold_old_receipt = False
        self.reads = 0
        self.confirm_after = 1

        async def protocol_request(controller, object_id, changes):
            self.delivered.append((object_id, dict(changes)))
            if native.STATUS_ATTR in changes:
                self.pending = changes[native.STATUS_ATTR] == native.STATUS_ON
            if native.HEATER_ATTR in changes:
                self.pending_source = changes[native.HEATER_ATTR]

        # Retain _CommissioningController.request_changes and its gate. Replace
        # only the external library's protocol backend underneath that method.
        backend = native._CommissioningController.__bases__[0]
        self.backend_patch = patch.object(backend, 'request_changes', protocol_request, create=True)
        self.backend_patch.start()
        self.addCleanup(self.backend_patch.stop)
        self.transport.read_observation = self.observation

    def observation(self):
        if self.pending is not None:
            self.reads += 1
            if self.reads >= self.confirm_after:
                self.actual_active = self.pending
        if self.pending_source is not None:
            self.actual_source = self.pending_source
        observed_at = self.old_observed_at if self.hold_old_receipt else datetime.now(timezone.utc)
        return SimpleNamespace(connected=not self.stale, observed_at=observed_at,
            body=lambda body_id: SimpleNamespace(active=self.actual_active, heat_source=self.actual_source)
                if body_id == 'B1101' else None)

    async def dispatch(self, commands):
        for entity, value in commands:
            if entity == POOL:
                await self.transport.set_body_active('B1101', value == 'heat')
            elif entity == 'select.pool_heat_source':
                await self.transport.set_heat_source('B1101', {'Off':'00000', 'Gas':'H0001', 'Solar':'H0002'}[value])
            else:
                raise AssertionError('Unrepresented equipment path: '+entity)

    async def awaited_sequence(self, actions):
        """Replay HA ordering with native receipt awaited before helper cleanup.

        This is still a config interpreter, not the Home Assistant engine.
        Conditions come from the same strict Replay evaluator; only service
        completion ordering is added for the cleanup-failure assertion.
        """
        for action in actions:
            if 'if' in action:
                await self.awaited_sequence(action.get('then', []) if self.replay.all(action['if'])
                                            else action.get('else', []))
            elif 'choose' in action:
                for branch in action['choose']:
                    if self.replay.all(branch['conditions']):
                        await self.awaited_sequence(branch['sequence'])
                        break
                else:
                    await self.awaited_sequence(action.get('default', []))
            else:
                if action.get('action') == 'climate.set_hvac_mode':
                    await self.dispatch([(action['target']['entity_id'], action['data']['hvac_mode'])])
                elif action.get('action') == 'select.select_option':
                    await self.dispatch([(action['target']['entity_id'], action['data']['option'])])
                self.replay.sequence([action])

    async def awaited_run(self):
        self.replay.trigger, self.replay.time = 'thermal_change', '12:32:00'
        if self.replay.all(self.replay.config.get('conditions', [])):
            try:
                await self.awaited_sequence(self.replay.config['actions'])
            except Halt:
                pass

    async def test_satisfied_shutdown_hot_roof_hold_and_reacquisition(self):
        await self.dispatch(self.replay.run('thermal_change'))
        self.assertFalse(self.actual_active)
        self.assertEqual(self.replay.states[OWNS], 'off')
        off = ('B1101', {native.STATUS_ATTR:native.STATUS_OFF})
        self.assertEqual(self.delivered, [off])
        for _ in range(3):
            await self.dispatch(self.replay.run())
        self.assertEqual(self.delivered, [off])
        self.replay.states[TARGET] = '90'
        await self.dispatch(self.replay.run('thermal_change'))
        self.assertTrue(self.actual_active)
        self.assertEqual(self.delivered[-2:], [
            ('B1101', {native.HEATER_ATTR:'H0002'}),
            ('B1101', {native.STATUS_ATTR:native.STATUS_ON}),
        ])

    async def test_native_off_confirmation_tolerates_delayed_telemetry(self):
        self.confirm_after = 3
        with patch.object(native.asyncio, 'sleep', new=AsyncMock()):
            await self.dispatch(self.replay.run('thermal_change'))
        self.assertEqual(self.reads, 3)
        self.assertFalse(self.actual_active)

    async def test_manual_ownership_blocks_actual_schedule_protocol_delivery(self):
        self.replay.states[MASTER] = 'off'
        for trigger in ['thermal_change','tick','midnight','reset','solar_down','solar_up','ownership_resumed','grid_restored']:
            await self.dispatch(self.replay.run(trigger,'03:57:00'))
        self.assertEqual(self.delivered, [])
        self.assertTrue(self.actual_active)
        # The operator's OFF remains a valid production transport command.
        await self.transport.set_body_active('B1101', False)
        self.assertEqual(self.delivered, [('B1101', {native.STATUS_ATTR:native.STATUS_OFF})])

    async def test_manual_ownership_blocks_actual_preference_protocol_delivery(self):
        import json
        path = Path(native.__file__).resolve().parents[2] / 'ha_automations/heating_preference.json'
        config = json.loads(path.read_text())
        # Suppress only independent Spa preference in this Pool gateway fixture.
        self.replay = Replay(config, **{MASTER:'off','input_boolean.spa_sanitation_session':'on'})
        await self.awaited_run()
        self.assertEqual(self.delivered, [])
        self.replay.states[MASTER] = 'on'
        await self.awaited_run()
        self.assertEqual(self.delivered, [('B1101', {native.HEATER_ATTR:'H0002'})])

    async def test_matching_old_observation_does_not_verify_off(self):
        self.hold_old_receipt = True
        clock = iter([0, 10, 20, 30])
        loop = SimpleNamespace(time=lambda: next(clock))
        with patch.object(native.asyncio, 'get_running_loop', return_value=loop), \
             patch.object(native.asyncio, 'sleep', new=AsyncMock()):
            with self.assertRaisesRegex(native.ManualCommandError, 'confirmation timeout'):
                await self.dispatch(self.replay.run('thermal_change'))
        self.assertFalse(self.actual_active) # matching state without NEW receipt is insufficient

    async def test_exclusive_authority_revoked_after_planning(self):
        commands = self.replay.run('thermal_change')
        self.authority = False
        with self.assertRaisesRegex(native.ManualCommandError, 'authority lost'):
            await self.dispatch(commands)
        self.assertEqual(self.delivered, [])
        self.assertFalse(self.transport.controller.manual_writes_enabled)

    async def test_authority_is_rechecked_after_dispatch_lock_wait(self):
        commands = self.replay.run('thermal_change')
        await self.transport._lock.acquire()
        task = asyncio.create_task(self.dispatch(commands))
        await asyncio.sleep(0)
        self.authority = False
        self.transport._lock.release()
        with self.assertRaisesRegex(native.ManualCommandError, 'authority lost'):
            await task
        self.assertEqual(self.delivered, [])

    async def test_stale_observation_blocks_previously_planned_shutdown(self):
        commands = self.replay.run('thermal_change')
        self.stale = True
        with self.assertRaisesRegex(native.ManualCommandError, 'fresh native'):
            await self.dispatch(commands)
        self.assertEqual(self.delivered, [])

    async def test_outage_preempts_previously_planned_solar_restart(self):
        self.replay.run('thermal_change')
        self.replay.states[TARGET] = '90'
        commands = self.replay.run('thermal_change')
        self.replay.states['input_boolean.grid_outage_active'] = 'on'
        with self.assertRaisesRegex(native.ManualCommandError, 'outage safety lockout'):
            await self.dispatch(commands)
        self.assertEqual(self.delivered, [])

    async def test_protocol_gate_still_rejects_disarmed_controller(self):
        # Exercise the protocol-level gate independently of the transport check.
        self.transport.controller.manual_writes_enabled = False
        with self.assertRaisesRegex(native.ManualCommandError, 'Physical writes disabled'):
            await self.transport.controller.request_changes('B1101', {native.STATUS_ATTR:native.STATUS_OFF})
        self.assertEqual(self.delivered, [])

    async def test_cleanup_claim_retained_until_native_off_receipt_succeeds(self):
        self.hold_old_receipt = True
        clock = iter([0, 10, 20, 30])
        with patch.object(native.asyncio, 'get_running_loop', return_value=SimpleNamespace(time=lambda: next(clock))), \
             patch.object(native.asyncio, 'sleep', new=AsyncMock()):
            with self.assertRaisesRegex(native.ManualCommandError, 'confirmation timeout'):
                await self.awaited_run()
        self.assertEqual(self.replay.states[OWNS], 'on')
        self.hold_old_receipt = False
        await self.awaited_run()
        self.assertEqual(self.replay.states[OWNS], 'off')
        self.assertEqual(self.replay.states[POOL], 'off')


if __name__ == '__main__': unittest.main()
