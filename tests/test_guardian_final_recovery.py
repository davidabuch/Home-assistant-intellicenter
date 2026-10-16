"""Test F: durable restart cut points against native configuration and gateway.

No live socket or hardware. Only external protocol IO/telemetry are synthetic.
Boots use the last successfully persisted record, never an in-memory checkpoint.
"""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import test_rpm_guardian as harness
import test_lightweight_schedule as schedule

policy, native, REAL_SLEEP = harness.policy, harness.native, harness.REAL_SLEEP


class FinalRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = harness.GuardianTests.asyncSetUp
    change = harness.GuardianTests.change
    drift = harness.GuardianTests.drift
    actual = harness.GuardianTests.actual
    outage = harness.GuardianTests.outage
    restore = harness.GuardianTests.restore
    run_policy = harness.GuardianTests.run_policy

    async def boot(self, record=Ellipsis):
        record = deepcopy(self.saved[-1] if record is Ellipsis else record)
        self.g = policy.RPMGuardian(self.g.read, self.g.write,
                                   lambda: self.sample, self.g.save)
        await self.g.load(record)
        self.t.set_preset_policy_check(self.g.permitted)
        self.t.set_control_policy_check(self.g.ordinary_command_allowed)

    def assert_held(self, value=1500):
        self.assertEqual(self.actual(), value)
        self.assertTrue(self.g.data['restoration_pending'])
        self.assertTrue(self.g.blocks_normal)
        self.assertFalse(self.g.ordinary_command_allowed(
            'request_changes', ('B1101', {native.STATUS_ATTR: native.STATUS_ON})))

    def assert_restored(self, value=2600):
        self.assertEqual(self.actual(), value)
        self.assertFalse(self.g.data['restoration_pending'])
        self.assertIsNone(self.g.data['intent'])
        self.assertIsNone(self.g.data['session'])
        self.assertFalse(self.g.blocks_normal)

    async def test_f01_restart_before_outage_dispatch_uses_durable_intent(self):
        self.outage()
        save = self.g.save
        async def cut(data):
            await save(data)
            if data.get('intent') and data['intent']['phase'] == 'outage':
                raise asyncio.CancelledError()
        self.g.save = cut
        with self.assertRaises(asyncio.CancelledError): await self.run_policy()
        self.g.save = save
        self.assertEqual(self.actual(),2600)
        self.assertFalse(self.writes)
        await self.boot()
        self.restore()
        await self.run_policy()
        self.assert_restored()
        self.assertFalse(self.writes)

    async def test_f02_restart_after_acceptance_before_ack(self):
        self.outage(); self.mode='ack_lost'
        await self.run_policy()
        self.assert_held()
        await self.boot(); self.mode='ok'; self.restore()
        await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),2)

    async def test_f03_restart_after_gateway_success_before_core_verification(self):
        self.outage()
        write = self.g.write
        async def cut(*args):
            await write(*args)
            raise asyncio.CancelledError()
        self.g.write = cut
        with self.assertRaises(asyncio.CancelledError): await self.run_policy()
        self.g.write = write
        self.assertEqual(self.actual(),1500)
        self.assertFalse(self.saved[-1]['intent']['verified'])
        await self.boot(); self.restore()
        await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),2)

    async def test_f04_restart_active_outage_does_not_rewrite_native_match(self):
        self.outage(); await self.run_policy()
        await self.boot(); await self.run_policy()
        self.assert_held()
        self.assertEqual(len(self.writes),1)

    async def test_f05_restart_during_restoration_after_native_acceptance(self):
        self.outage(); await self.run_policy(); self.restore()
        self.mode='ack_lost'; await self.run_policy()
        self.assert_held(2600)
        await self.boot(); self.mode='ok'
        await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),2)

    async def test_f06_grid_returns_while_outage_write_waits_for_native_lock(self):
        self.outage()
        await self.t._lock.acquire()
        task=asyncio.create_task(self.run_policy())
        await REAL_SLEEP(0)
        self.restore(); self.g.invalidate_authority()
        self.t._lock.release()
        await task
        self.assert_held(2600)
        self.assertFalse(self.writes)
        await self.run_policy()
        self.assert_restored()
        self.assertFalse(self.writes)

    async def test_f07_outage_recurs_during_restoration(self):
        self.outage(); await self.run_policy(); self.restore()
        self.before_backend=lambda:self.change(qualified=True,raw_outage=True,restored=False)
        await self.run_policy()
        self.assert_held(2600)
        self.before_backend=None
        await self.run_policy()
        self.assert_held()
        self.restore(); await self.run_policy()
        self.assert_restored()

    async def test_f08_write_timeout_preserves_native_and_recovery(self):
        self.outage(); self.mode='timeout'
        await self.run_policy()
        self.assert_held(2600)
        self.assertEqual(self.g.data['failed_writes'],1)
        self.mode='ok'; self.restore(); await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),1)

    async def test_f09_communication_loss_survives_durable_restart(self):
        self.outage(); await self.run_policy(); self.change(fresh=False)
        await self.run_policy(); await self.boot()
        await self.run_policy(); self.assert_held()
        self.assertEqual(len(self.writes),1)
        self.change(fresh=True); self.restore(); await self.run_policy()
        self.assert_restored()

    async def test_f10_stale_native_confirmation_does_not_clear_journal(self):
        self.outage()
        # Real transport confirmation loop must time out even if SPEED changed,
        # because the observation generation did not advance.
        ticks=iter([0,10,20,30])
        fake_loop=SimpleNamespace(time=lambda:next(ticks),call_soon=lambda callback:None)
        with patch.object(native.asyncio,'get_running_loop',return_value=fake_loop):
            await self.run_policy()
        self.assert_held()
        self.assertEqual(self.g.data['failed_writes'],1)
        self.restore(); await self.run_policy()
        self.assert_restored()

    async def test_f11_external_native_change_during_outage_respects_manual_authority(self):
        self.outage(); await self.run_policy()
        self.drift('pool',2800); self.change(authority=False)
        await self.run_policy(); self.assert_held(2800)
        self.assertEqual(len(self.writes),1)
        self.change(authority=True); await self.run_policy(); self.assert_held()
        self.restore(); await self.run_policy(); self.assert_restored()

    async def test_f12_changed_applied_normal_policy_restores_current_value(self):
        self.outage(); await self.run_policy()
        await self.g.edit('pool',2700); await self.g.apply()
        await self.boot(); self.assert_held()
        self.restore(); await self.run_policy(); self.assert_restored(2700)

    async def test_f13_manual_reconciliation_during_outage_is_idempotent(self):
        self.outage(); await self.run_policy()
        for _ in range(3): await self.run_policy('manual_button')
        self.assert_held()
        self.assertEqual(len(self.writes),1)

    async def test_f14_disabled_guardian_keeps_recovery_and_native_preset(self):
        self.outage(); await self.run_policy()
        await self.g.enable(False); self.restore()
        await self.boot(); await self.run_policy()
        self.assert_held()
        self.assertEqual(len(self.writes),1)
        await self.g.enable(True)
        self.change(pool=False,actual_rpm=0)
        await self.run_policy(); self.assert_restored()

    async def test_f15_revoked_running_approval_defers_restore_until_safe_idle(self):
        self.outage(); await self.run_policy()
        await self.g.enable(True,running_pool_approved=False)
        self.restore(); await self.boot(); await self.run_policy()
        self.assert_held()
        self.assertEqual(len(self.writes),1)
        self.change(pool=False,actual_rpm=0)
        await self.run_policy(); self.assert_restored()

    async def test_f16_repeated_grid_flapping_has_one_write_per_real_transition(self):
        for _ in range(4):
            self.outage(); await self.run_policy(); await self.run_policy()
            self.restore(); await self.run_policy(); await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),8)

    async def test_f17_inconsistent_program_journal_fails_closed(self):
        record=deepcopy(self.saved[-1])
        record['intent']={'program':'p0105','epoch':0}
        record['restoration_pending']=True
        await self.boot(record); await self.run_policy()
        self.assert_held(2600)
        self.assertFalse(self.g.loaded)
        self.assertFalse(self.writes)

    async def test_f18_journal_outage_but_native_normal_clears_without_rewrite(self):
        self.outage(); await self.run_policy()
        self.drift('pool',2600)
        await self.boot(); self.restore(); await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),1)

    async def test_f19_clean_record_native_outage_speed_blocks_until_restored(self):
        self.change(pool=True,actual_rpm=1500)
        self.drift('pool',1500)
        await self.boot()
        await self.g.enable(False)
        await self.run_policy()
        self.assert_held()
        self.assertFalse(self.writes)
        self.assertIn('Recovery pending',self.g.data['failure'])
        await self.g.enable(True,running_pool_approved=True)
        await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),1)

    async def test_f20_restart_after_restoration_before_cleanup_save(self):
        self.outage(); await self.run_policy(); self.restore()
        save=self.g.save
        async def cut(data):
            if data['state']=='REEVALUATING_DEMAND':
                raise asyncio.CancelledError()
            await save(data)
        self.g.save=cut
        with self.assertRaises(asyncio.CancelledError): await self.run_policy()
        self.g.save=save
        self.assert_held(2600)
        await self.boot(); await self.run_policy()
        self.assert_restored()
        self.assertEqual(len(self.writes),2)

    async def test_f21_multiple_queued_requests_do_not_duplicate_write(self):
        self.outage()
        await asyncio.gather(*(self.run_policy('queued') for _ in range(12)))
        self.assert_held()
        self.assertEqual(len(self.writes),1)
        self.restore()
        await asyncio.gather(*(self.run_policy('queued') for _ in range(12)))
        self.assert_restored()
        self.assertEqual(len(self.writes),2)

    async def test_f22_restart_with_warning_requires_native_restoration(self):
        self.outage(); await self.run_policy(); self.restore()
        self.mode='timeout'; await self.run_policy()
        await self.boot()
        self.assert_held()
        self.assertIsNotNone(self.g.data['failure'])
        self.mode='ok'; await self.run_policy(); self.assert_restored()
        self.assertIsNone(self.g.data['failure'])

    async def test_f23_equal_normal_and_outage_policy_is_not_false_recovery(self):
        self.g.data['applied']['pool']=1500
        self.g.data['floors']['pool']=1500
        self.drift('pool',1500)
        self.change(pool=True,actual_rpm=1500)
        await self.run_policy()
        self.assertEqual(self.actual(),1500)
        self.assertFalse(self.g.data['restoration_pending'])
        self.assertFalse(self.g.blocks_normal)
        self.assertFalse(self.writes)

    async def test_f24_unjournaled_outage_value_respects_manual_authority(self):
        self.drift('pool',1500)
        self.change(pool=True,actual_rpm=1500,authority=False)
        await self.run_policy()
        self.assert_held()
        self.assertFalse(self.writes)
        self.change(authority=True)
        await self.run_policy()
        self.assert_restored()

    async def test_f25_boot_without_journal_still_detects_native_outage_value(self):
        self.drift('pool',1500)
        self.change(pool=True,actual_rpm=1500)
        await self.boot(None)
        await self.g.enable(False)
        await self.run_policy()
        self.assert_held()
        self.assertFalse(self.writes)

    async def test_f26_recovery_barrier_then_night_debt_completion_and_rollover(self):
        self.drift('pool',1500)
        await self.g.enable(False)
        await self.run_policy()
        self.assert_held()
        replay=schedule.Replay(**{
            schedule.POOL:'off',schedule.OWNS:'off',schedule.COUNT:'475',
            schedule.GOAL:'480',schedule.ROOF:'85','sensor.pump_rpm':'0',
            'binary_sensor.rpm_guardian_blocks_normal_control':'on'})
        self.assertEqual(replay.run('midnight','00:00:00'),[])
        self.assertEqual(replay.states[schedule.COUNT],'475')
        await self.g.enable(True)
        await self.run_policy()
        self.assert_restored()
        replay.states['binary_sensor.rpm_guardian_blocks_normal_control']='off'
        self.assertIn((schedule.POOL,'heat'),replay.run('midnight','00:00:00'))
        replay.states['sensor.pump_rpm']='2600'
        for minute in range(1,6): replay.run('tick',f'00:0{minute}:00')
        self.assertEqual(replay.states[schedule.COUNT],'480')
        self.assertEqual(replay.states[schedule.POOL],'off')
        self.assertNotIn((schedule.POOL,'heat'),replay.run('tick','00:06:00'))
        replay.run('reset','08:00:00')
        self.assertEqual(replay.states[schedule.COUNT],'0')
        self.assertEqual(self.actual(),2600)

    async def test_f27_restore_releases_current_solar_demand_then_target_shutdown(self):
        self.outage(); await self.run_policy(); self.assert_held()
        replay=schedule.Replay(**{schedule.COUNT:'480',schedule.ROOF:'120',
            'binary_sensor.rpm_guardian_blocks_normal_control':'on'})
        self.assertEqual(replay.run('tick'),[])
        self.assertEqual(replay.states[schedule.COUNT],'480')
        self.restore(); await self.run_policy(); self.assert_restored()
        replay.states['binary_sensor.rpm_guardian_blocks_normal_control']='off'
        self.assertNotIn((schedule.POOL,'off'),replay.run('grid_restored'))
        replay.states[schedule.TARGET]='71'
        self.assertIn((schedule.POOL,'off'),replay.run('thermal_change'))
        replay.states[schedule.TARGET]='90'
        self.assertIn((schedule.POOL,'heat'),replay.run('thermal_change'))
        replay.states[schedule.ROOF]='89'
        self.assertIn((schedule.POOL,'off'),replay.run('solar_down'))
        self.assertEqual(self.actual(),2600)
