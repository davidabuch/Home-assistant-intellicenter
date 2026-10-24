"""Guardian policy/recovery against the actual native preset command gateway.

External protocol IO and telemetry are synthetic. Real identity validation,
allowlist, locked policy/authority checks and fresh configured readback execute.
"""
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_transport_lifecycle_faults import transport_module as native

policy = importlib.import_module(native.__package__ + '.rpm_guardian')
REAL_SLEEP = asyncio.sleep


class GuardianTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sample = policy.Conditions(cleaning_active=False, fresh=True, qualified=False, raw_outage=False,
            restored=True, protection=True, bypass=False, authority=True,
            freeze_off=True, automatic_mode=True, pool=False, spa_off=True,
            sanitation_off=True, heat_off=True, sources_off=True, accessories_off=True,
            settled=True, actual_rpm=0)
        self.t = native.IntelliCenterManualTransport('127.0.0.1')
        self.t._started = self.t._connected = True
        self.native_authority = True
        self.t.set_manual_authority_check(lambda: self.native_authority)
        self.t.arm_manual_thermostats()
        self.rows = {obj: SimpleNamespace(objnam=obj, properties={
            native.PARENT_ATTR:'PMP01', native.SELECT_ATTR:'RPM', native.CIRCUIT_ATTR:circuit,
            native.SPEED_ATTR:str(policy.DEFAULTS[key])})
            for key, (obj, circuit) in policy.BASE_PROGRAMS.items()}
        self.t.model = SimpleNamespace(get_by_type=lambda kind: list(self.rows.values())
            if kind == native.PMPCIRC_TYPE else [])
        self.t.read_observation = lambda: SimpleNamespace(connected=self.sample.fresh)
        self.t.set_outage_command_check(lambda method,args: not self.sample.protected)
        self.writes, self.saved = [], []
        self.mode = 'ok'
        self.before_backend = None

        async def save(data): self.saved.append(deepcopy(data))
        def read(key):
            return int(self.t._verified_pump_program(policy.PROGRAMS[key][0]).properties[native.SPEED_ATTR])
        async def write(obj, value, permit):
            await self.t.set_configured_pump_program_rpm(obj, value, authority=permit)
        self.g = policy.RPMGuardian(read, write, lambda:self.sample, save)
        await self.g.load(None)
        await self.g.enable(True, running_pool_approved=True)
        self.t.set_preset_policy_check(self.g.permitted)
        self.t.set_control_policy_check(self.g.ordinary_command_allowed)

        async def backend(controller, obj, changes):
            self.writes.append((obj, dict(changes)))
            if self.before_backend: self.before_backend()
            if self.mode == 'timeout': raise TimeoutError('native timeout')
            target = int(changes[native.SPEED_ATTR])
            self.rows[obj].properties[native.SPEED_ATTR] = str(target+10 if self.mode=='mismatch' else target)
            asyncio.get_running_loop().call_soon(
                lambda:setattr(self.t, '_observed_at', datetime.now(timezone.utc)))
            if self.mode == 'ack_lost': raise RuntimeError('ACK lost after native acceptance')
        base = native._CommissioningController.__bases__[0]
        p = patch.object(base, 'request_changes', backend, create=True)
        p.start(); self.addCleanup(p.stop)
        async def fast_sleep(_seconds): await REAL_SLEEP(0)
        p = patch.object(native.asyncio, 'sleep', fast_sleep)
        p.start(); self.addCleanup(p.stop)

    def change(self, **values): self.sample = replace(self.sample, **values)
    def drift(self, key, value): self.rows[policy.PROGRAMS[key][0]].properties[native.SPEED_ATTR]=str(value)
    def actual(self, key='pool'): return self.g.read(key)
    def outage(self, **extra):
        self.change(qualified=True, raw_outage=True, restored=False,
                    pool=True, actual_rpm=2600, **extra)
    def restore(self): self.change(qualified=False, raw_outage=False, restored=True, actual_rpm=1500)

    async def run_policy(self, reason='manual'):
        return await self.g.reconcile(reason)

    async def restart(self):
        await REAL_SLEEP(0)
        old = deepcopy(self.g.data)
        self.g = policy.RPMGuardian(self.g.read, self.g.write, lambda:self.sample, self.g.save)
        await self.g.load(old)
        self.t.set_preset_policy_check(self.g.permitted)
        self.t.set_control_policy_check(self.g.ordinary_command_allowed)

    async def test_nonstep_native_readback_holds_all_routine_writes(self):
        self.drift('solar', 2816)
        self.drift('pool', 2560)
        result = await self.run_policy('startup')
        self.assertEqual(result['state'], 'DEGRADED')
        self.assertTrue(result['results']['solar'].startswith('READBACK_DISCREPANCY'))
        self.assertEqual(result['pending_routine'], {})
        self.assertTrue(result['routine_scan_pending'])
        self.assertEqual(self.writes, [])
        again = await self.run_policy('recovery_heartbeat')
        self.assertEqual(again['state'], 'DEGRADED')
        self.assertEqual(self.writes, [])

    async def test_explicit_repair_of_confirmed_nonstep_native_circuit_drift(self):
        self.drift('solar', 2816)
        self.drift('pool', 2560)
        blocked = await self.run_policy('startup')
        self.assertEqual(blocked['state'], 'DEGRADED')
        self.assertEqual(self.writes, [])
        repaired = await self.run_policy('manual_button')
        self.assertEqual(repaired['state'], 'NORMAL')
        self.assertEqual(self.actual('solar'), 2900)
        self.assertEqual(self.actual('pool'), 2600)
        self.assertEqual(repaired['results']['solar'], 'VERIFIED')
        self.assertEqual(repaired['results']['pool'], 'VERIFIED')
        self.assertFalse(self.g.blocks_normal)

    async def test_explicit_nonstep_repair_remains_deferred_during_cleaning(self):
        self.drift('solar', 2816)
        await self.run_policy('startup')
        self.change(cleaning_active=True)
        result = await self.run_policy('manual_button')
        self.assertEqual(result['state'], 'DEGRADED')
        self.assertEqual(self.writes, [])
        self.assertEqual(self.actual('solar'), 2816)

    async def test_cleaning_active_defers_ordinary_preset_correction(self):
        self.drift('pool', 2400)
        self.change(cleaning_active=True)
        result = await self.run_policy('manual_button')
        self.assertFalse(self.writes)
        self.assertEqual(self.actual(), 2400)
        self.assertIn('pool', result['pending_routine'])
        self.change(cleaning_active=False)
        await self.run_policy('cleaning_released')
        self.assertEqual(self.actual(), 2600)

    async def test_cleaning_unknown_fails_closed(self):
        self.drift('solar', 2800)
        self.change(cleaning_active=None)
        await self.run_policy('manual_button')
        self.assertFalse(self.writes)
        self.change(cleaning_active=False)
        await self.run_policy('cleaning_released')
        self.assertEqual(self.actual('solar'), 2900)

    async def test_01_correct_presets_no_writes(self):
        r=await self.run_policy(); self.assertFalse(self.writes)
        self.assertEqual(set(r['results'].values()), {'MATCH'})
    async def test_02_pool_drift(self):
        self.drift('pool',2400); await self.run_policy(); self.assertEqual(self.actual(),2600)
    async def test_03_solar_drift(self):
        self.drift('solar',2800); await self.run_policy(); self.assertEqual(self.actual('solar'),2900)
    async def test_04_multiple_serial_corrections(self):
        for key in ('pool','spa','solar'): self.drift(key,2400)
        await asyncio.gather(self.run_policy(),self.run_policy())
        self.assertEqual(len(self.writes),3)
        self.assertEqual(len({obj for obj,_ in self.writes}),3)
    async def test_05_draft_does_not_apply_on_schedule(self):
        await self.g.edit('pool',2700); await self.run_policy('23:59')
        self.assertFalse(self.writes); self.assertEqual(self.actual(),2600)
    async def test_06_apply(self):
        await self.g.edit('pool',2700); await self.g.apply(); self.assertEqual(self.actual(),2700)
    async def test_07_manual_reconcile(self):
        self.drift('pool',2400); await self.run_policy('manual_button'); self.assertEqual(len(self.writes),1)
    async def test_08_readback_mismatch(self):
        self.drift('pool',2400); self.mode='mismatch'
        real_loop=asyncio.get_running_loop(); clock=iter([0,10,20,30])
        fake=SimpleNamespace(time=lambda:next(clock),call_soon=real_loop.call_soon)
        with patch.object(native.asyncio,'get_running_loop',return_value=fake):
            r=await self.run_policy()
        self.assertIn('FAILED',r['results']['pool']); self.assertEqual(r['failed_writes'],1)
    async def test_09_native_timeout(self):
        self.drift('pool',2400); self.mode='timeout'; r=await self.run_policy()
        self.assertIn('FAILED',r['results']['pool'])
    async def test_10_invalid_speeds(self):
        for value in (0,599,3460,2601,True,float('nan'),float('inf'),'2600'):
            with self.subTest(value=value), self.assertRaises(ValueError): await self.g.edit('pool',value)
        self.assertFalse(self.writes)
    async def test_11_short_outage(self):
        self.change(raw_outage=True,qualified=False,restored=False)
        self.drift('pool',2400); r=await self.run_policy()
        self.assertEqual(r['state'],'OUTAGE_QUALIFYING'); self.assertFalse(self.writes)
    async def test_12_qualified_detector_latch(self):
        self.outage(); await self.run_policy(); self.assertEqual(self.actual(),1500)
    async def test_13_running_pool_outage(self):
        self.outage(); r=await self.run_policy()
        self.assertEqual(r['state'],'OUTAGE_ACTIVE', r.get('failure')); self.assertTrue(r['restoration_pending'])
    async def test_14_pool_off_never_started(self):
        self.outage(); self.change(pool=False,actual_rpm=0); await self.run_policy()
        self.assertFalse(self.writes); self.assertEqual(self.actual(),2600)
    async def test_15_solar_heating_blocks_lower_flow(self):
        self.outage(heat_off=False,sources_off=False); r=await self.run_policy()
        self.assertEqual(r['state'],'DEGRADED'); self.assertFalse(self.writes)
    async def test_16_gas_heating_blocks_lower_flow(self):
        self.outage(heat_off=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_17_spa_priority(self):
        self.outage(spa_off=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_18_sanitation_priority(self):
        self.outage(sanitation_off=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_19_priming(self):
        self.outage(settled=False); r=await self.run_policy()
        self.assertFalse(self.writes); self.assertEqual(r['runtime_status'],'SETTLING')
    async def test_20_higher_request(self):
        self.outage(accessories_off=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_21_protection_disabled(self):
        self.outage(protection=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_22_operator_bypass(self):
        self.outage(bypass=True); await self.run_policy(); self.assertFalse(self.writes)
    async def restore_cycle(self, **after):
        self.outage(); await self.run_policy(); self.restore(); self.change(**after)
        return await self.run_policy()
    async def test_23_restore_then_solar_demand_handoff(self):
        r=await self.restore_cycle(); self.assertEqual(self.actual(),2600)
        self.assertEqual(r['state'],'NORMAL'); self.assertFalse(self.g.blocks_normal)
        # No equipment ON/OFF command is stored or replayed by the coordinator.
        self.assertTrue(all(set(changes)=={native.SPEED_ATTR} for _,changes in self.writes))
    async def test_24_restore_target_satisfied_handoff(self):
        r=await self.restore_cycle(pool=False,actual_rpm=0)
        self.assertEqual(r['state'],'NORMAL'); self.assertFalse(r['restoration_pending'])
    async def test_25_night_filtration_ledger_untouched(self):
        await self.restore_cycle(); self.assertFalse(any('counter' in str(w) for w in self.writes))
    async def test_26_restoration_with_pool_off(self):
        await self.restore_cycle(pool=False,actual_rpm=0); self.assertEqual(self.actual(),2600)
    async def test_27_changed_normal_pool_policy(self):
        self.outage(); await self.run_policy(); await self.g.edit('pool',2700); await self.g.apply()
        self.assertEqual(self.actual(),1500); self.restore(); await self.run_policy(); self.assertEqual(self.actual(),2700)
    async def test_28_restoration_write_failure(self):
        self.outage(); await self.run_policy(); self.restore(); self.mode='timeout'
        r=await self.run_policy(); self.assertTrue(r['restoration_pending']); self.assertTrue(self.g.blocks_normal)
    async def test_29_restoration_fresh_readback(self):
        r=await self.restore_cycle(); self.assertIsNotNone(r['last_verified'].get('pool'))
        self.assertIsNone(r['intent'])
    async def test_30_outage_recurs_during_restore(self):
        self.outage(); await self.run_policy(); self.restore()
        self.before_backend=lambda:self.change(qualified=True,raw_outage=True,restored=False)
        r=await self.run_policy(); self.assertTrue(r['restoration_pending']); self.assertTrue(self.g.blocks_normal)
        self.before_backend=None; await self.run_policy(); self.assertEqual(self.actual(),1500)
    async def test_31_restart_before_outage_write(self):
        self.outage(settled=False); await self.run_policy(); await self.restart()
        self.change(settled=True); await self.run_policy(); self.assertEqual(self.actual(),1500)
    async def test_32_restart_after_accepted_write_ack_lost(self):
        self.outage(); self.mode='ack_lost'; await self.run_policy(); self.assertEqual(self.actual(),1500)
        await self.restart(); self.mode='ok'; self.restore(); await self.run_policy(); self.assertEqual(self.actual(),2600)
    async def test_33_restart_during_outage(self):
        self.outage(); await self.run_policy(); count=len(self.writes); await self.restart(); await self.run_policy()
        self.assertEqual(len(self.writes),count); self.assertTrue(self.g.blocks_normal)
    async def test_34_restart_during_restoration(self):
        self.outage(); await self.run_policy(); self.restore(); self.mode='ack_lost'; await self.run_policy()
        await self.restart(); self.mode='ok'; r=await self.run_policy()
        self.assertEqual(r['state'],'NORMAL'); self.assertFalse(r['restoration_pending'])
    async def test_35_communication_loss(self):
        self.outage(); await self.run_policy(); self.change(fresh=False)
        r=await self.run_policy(); self.assertEqual(r['state'],'RECOVERY_REQUIRED'); self.assertTrue(r['restoration_pending'])
    async def test_36_unknown_ack_never_blindly_retried(self):
        self.outage(); self.mode='ack_lost'; await self.run_policy(); await REAL_SLEEP(0)
        count=len(self.writes); self.mode='ok'; await self.run_policy(); self.assertEqual(len(self.writes),count)
    async def test_37_flapping(self):
        for _ in range(3):
            self.outage(); await self.run_policy(); self.restore(); await self.run_policy()
        self.assertEqual(self.actual(),2600); self.assertEqual(len(self.writes),6)
    async def test_38_manual_reset_cannot_clear_dirty_record(self):
        self.outage(); await self.run_policy()
        with self.assertRaises(RuntimeError): await self.g.reset()
        self.assertTrue(self.g.data['restoration_pending'])
    async def test_39_draft_during_outage_retained(self):
        self.outage(); await self.run_policy(); await self.g.edit('pool',2800); await self.run_policy()
        self.assertEqual(self.actual(),1500); self.assertEqual(self.g.data['draft']['pool'],2800)
        self.assertEqual(self.g.data['applied']['pool'],2600)
    async def test_40_final_authority_conflict(self):
        self.outage(); self.native_authority=False; r=await self.run_policy()
        self.assertFalse(self.writes); self.assertTrue(r['restoration_pending'])
    async def test_41_removed_grid_program_excluded(self):
        self.assertNotIn('p0104',[obj for obj,_ in policy.BASE_PROGRAMS.values()])
        self.assertIn('p0104',[obj for obj,_ in policy.PROGRAMS.values()])
        with self.assertRaises(native.ManualCommandError): await self.t.set_configured_pump_program_rpm('p0104',1500)
        self.assertFalse(self.writes)
    async def test_42_stale_observation(self):
        self.drift('pool',2400); self.change(fresh=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_43_unscoped_native_writer_rejected(self):
        with self.assertRaisesRegex(native.ManualCommandError,'single-writer'):
            await self.t.set_configured_pump_program_rpm('p0102',2700)
        self.assertFalse(self.writes)
    async def test_44_write_ahead_journal(self):
        self.outage()
        def verify():
            last=self.saved[-1]
            self.assertTrue(last['restoration_pending']); self.assertTrue(last['intent']['attempted'])
            self.assertFalse(last['intent']['verified']); self.assertEqual(last['intent']['program'],'p0102')
        self.before_backend=verify; await self.run_policy()
    async def test_45_corrupt_storage_fails_closed(self):
        stored=deepcopy(self.g.data); stored['enabled']='true'
        await self.g.load(stored); self.assertFalse(self.g.loaded); self.assertTrue(self.g.blocks_normal)
        with self.assertRaises(RuntimeError): await self.g.edit('pool',2700)
    async def test_46_identity_mismatch_prevents_all_writes(self):
        self.rows['p0102'].properties[native.CIRCUIT_ATTR]='FTR03'
        self.drift('solar',2800); await self.run_policy(); self.assertFalse(self.writes)
    async def test_47_disarmed_deployment_never_writes(self):
        await self.g.enable(False); self.outage(); await self.run_policy(); self.assertFalse(self.writes)
    async def test_48_apply_below_approved_floor_rejected(self):
        await self.g.edit('heater',2500)
        with self.assertRaises(ValueError): await self.g.apply()
        self.assertEqual(self.g.data['applied']['heater'],3000)
    async def test_49_normal_running_change_deferred(self):
        self.change(pool=True,actual_rpm=2600); self.drift('solar',2800)
        r=await self.run_policy(); self.assertFalse(self.writes); self.assertIn('DEFERRED',r['results']['solar'])
    async def test_50_restoration_blocks_normal_heat_on(self):
        self.outage(); await self.run_policy()
        with self.assertRaisesRegex(native.ManualCommandError,'restoration/authority'):
            await self.t.set_heat_source('B1101','H0002')
    async def test_51_manual_ownership_preserves_native_change(self):
        self.drift('pool',2700); self.change(authority=False); await self.run_policy()
        self.assertFalse(self.writes); self.assertEqual(self.actual(),2700)
    async def test_52_runtime_mismatch_never_rewrites_matching_configuration(self):
        self.outage(); await self.run_policy(); count=len(self.writes)
        self.g.data['runtime_wait_until']='2000-01-01T00:00:00+00:00'
        self.change(actual_rpm=2600); r=await self.run_policy()
        self.assertEqual(len(self.writes),count); self.assertIn('MISMATCH',r['runtime_status'])
    async def test_53_idle_restore_needs_no_running_write_approval(self):
        self.outage(); await self.run_policy(); self.restore(); self.change(pool=False,actual_rpm=0)
        self.g.data['running_pool_approved']=False
        await self.run_policy(); self.assertEqual(self.actual(),2600)
    async def test_54_bypass_retains_recovery_obligation(self):
        self.outage(); await self.run_policy(); self.change(bypass=True)
        r=await self.run_policy(); self.assertTrue(r['restoration_pending'])
        self.assertTrue(self.g.ordinary_command_allowed('request_changes',('B1202',{native.STATUS_ATTR:native.STATUS_ON})))
    async def test_55_freeze_prevents_lowering(self):
        self.outage(freeze_off=False); await self.run_policy(); self.assertFalse(self.writes)
    async def test_56_configured_match_during_priming_never_rewritten(self):
        self.outage(); await self.run_policy(); count=len(self.writes)
        self.change(actual_rpm=3450,settled=False); await self.run_policy(); self.assertEqual(len(self.writes),count)
    async def test_57_config_write_starts_new_settling_window(self):
        self.outage(); r=await self.run_policy()
        self.assertEqual(r['runtime_status'],'SETTLING')
    async def test_58_authority_epoch_changes_while_waiting_for_native_lock(self):
        self.outage(); await self.t._lock.acquire()
        task=asyncio.create_task(self.run_policy())
        await REAL_SLEEP(0)
        self.g.invalidate_authority()  # a complete manual OFF/ON flap, final state unchanged
        self.t._lock.release()
        r=await task
        self.assertFalse(self.writes); self.assertTrue(r['restoration_pending'])
        await self.run_policy(); self.assertEqual(self.actual(),1500)

    async def test_59_disarm_revokes_running_approval_and_persists_revocation(self):
        self.assertTrue(self.g.data['running_pool_approved'])
        await self.g.enable(False, running_pool_approved=False)
        self.assertFalse(self.g.data['enabled'])
        self.assertFalse(self.g.data['running_pool_approved'])
        self.assertFalse(self.saved[-1]['running_pool_approved'])
        await self.g.enable(True)  # Reenabling alone is not renewed running approval.
        self.outage()
        await self.run_policy()
        self.assertFalse(self.writes)
        self.assertEqual(self.actual(),2600)

    async def test_60_verified_outage_clears_resolved_cooldown_warning(self):
        self.outage(settled=False)
        result=await self.run_policy()
        self.assertIsNotNone(result['failure'])
        self.assertFalse(self.writes)
        self.change(settled=True)
        result=await self.run_policy()
        self.assertEqual(self.actual(),1500)
        self.assertEqual(result['state'],'OUTAGE_ACTIVE')
        self.assertEqual(result['runtime_status'],'SETTLING')
        self.assertIsNone(result['failure'])

    async def test_61_cleaning_3000_requires_apply_then_manual_reconcile(self):
        self.assertEqual(self.g.data['floors']['pool_cleaning'], 3000)
        await self.g.edit('pool_cleaning', 3000)
        await self.run_policy('manual_button')
        self.assertFalse(self.g.data['pool_cleaning_commissioned'])
        await self.g.apply()
        self.assertFalse(self.g.data['pool_cleaning_commissioned'])
        self.assertTrue(self.g.data['pool_cleaning_armed'])
        self.assertEqual(self.g.data['applied']['pool_cleaning'], 3000)

if __name__=='__main__': unittest.main()
