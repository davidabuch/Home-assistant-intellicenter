"""Incident replay and command intent. Synthetic protocol only; no HA or sockets."""
import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_lightweight_schedule import Replay, POOL, OWNS, MASTER, COUNT, GOAL, TARGET, ROOF
import test_schedule_gateway as gateway
import test_rpm_guardian as harness

M = 'input_boolean.pool_simple_manual_circulation'
SOLAR = 'binary_sensor.solar_heating_active'
DELIVERY = 'binary_sensor.solar_delivery_confirmed'
SOURCE = 'select.pool_heat_source'
demand = importlib.import_module(harness.native.__package__ + '.pump_demand')


def rows(pool=2600, heater=False, solar=True):
    return [dict(id=obj,circuit_id=circuit,mode='RPM',rpm=harness.policy.DEFAULTS[key],
        active={'pool':True,'spa':False,'sanitation':False,'heater':heater,'solar':solar}[key])
        for key,(obj,circuit) in harness.policy.PROGRAMS.items()
        if key != 'pool'] + [dict(id='p0102',circuit_id='C0006',mode='RPM',rpm=pool,active=True)]


class DemandDiagnosticsTests(unittest.TestCase):
    def test_confirmed_delivery_needs_native_circuit_and_heating_not_selection(self):
        from datetime import datetime, timezone
        observation=importlib.import_module(harness.native.__package__+'.observation')
        def sample(heating, circuit=True, connected=True):
            return observation.ReadObservation(connected,datetime.now(timezone.utc),(
                observation.BodyObservation('B1101',True,heating,79,90,'H0002'),
                observation.BodyObservation('B1202',False,False,79,97,'00000')),
                () if circuit is None else (observation.CircuitObservation('X0052',circuit),))
        self.assertFalse(sample(False).solar_delivery_confirmed())
        self.assertFalse(sample(True,False).solar_delivery_confirmed())
        self.assertTrue(sample(True).solar_delivery_confirmed())
        self.assertIsNone(sample(True,None).solar_delivery_confirmed())
        self.assertIsNone(sample(True,connected=False).solar_delivery_confirmed())
        self.assertIsNone(sample(None).solar_delivery_confirmed())

    def report(self, programs=None, **kw):
        defaults=dict(fresh=True,solar_delivery=True,actual_rpm=2900,settled=True,
            freeze_off=True,automatic_mode=True,desired_solar=2900)
        defaults.update(kw)
        return demand.explain(rows() if programs is None else programs, **defaults)

    def test_01_manual_start_then_solar_selects_effective_demand(self):
        self.assertEqual(self.report(solar_delivery=False)['status'],'NO_CONFIRMED_SOLAR_DELIVERY')
        self.assertEqual(self.report()['status'],'SOLAR_RPM_VERIFIED')

    def test_02_solar_already_active(self):
        for _ in range(3):
            r=self.report(); self.assertEqual(r['effective_rpm'],2900)
            self.assertFalse(r['runtime_write'])

    def test_03_matching_solar_preset_is_not_runtime_proof(self):
        self.assertEqual(self.report(actual_rpm=3000)['status'],'RUNTIME_MISMATCH_REVIEW_REQUIRED')

    def test_04_high_pool_or_heater_demand_explains_3000(self):
        for programs in [rows(pool=3000),rows(heater=True)]:
            r=self.report(programs,actual_rpm=3000)
            self.assertEqual(r['status'],'HIGHER_PROGRAM_DEMAND')
            self.assertEqual(r['effective_rpm'],3000)

    def test_05_selected_solar_is_not_active_virtual_circuit(self):
        self.assertEqual(self.report(rows(solar=False))['status'],'SOLAR_CIRCUIT_UNCONFIRMED')
        r=rows();next(row for row in r if row['circuit_id']=='X0052')['active']=None
        self.assertEqual(self.report(r)['status'],'INCOMPLETE_NATIVE_DEMAND')

    def test_08_transitions_settling_stale_and_unknown_extra_demands(self):
        self.assertEqual(self.report(settled=False)['status'],'SETTLING')
        self.assertEqual(self.report(solar_delivery=False)['status'],'NO_CONFIRMED_SOLAR_DELIVERY')
        self.assertEqual(self.report(settled=False)['status'],'SETTLING')
        self.assertEqual(self.report()['status'],'SOLAR_RPM_VERIFIED')
        self.assertIsNone(self.report(fresh=False)['effective_rpm'])
        for extra in [dict(id='p0109',active=None,mode='RPM',rpm=3200),
                      dict(id='p0109',active=True,mode='GPM',rpm=None)]:
            self.assertEqual(self.report(rows()+[extra])['status'],'INCOMPLETE_NATIVE_DEMAND')
        self.assertEqual(self.report(freeze_off=False)['status'],'SAFETY_PREEMPTED')

    def test_transport_reports_raw_virtual_circuits_and_all_assignments_without_writes(self):
        native=harness.native
        programs={obj:SimpleNamespace(objnam=obj,properties={
            native.PARENT_ATTR:'PMP01',native.CIRCUIT_ATTR:circuit,
            native.SELECT_ATTR:'RPM',native.SPEED_ATTR:str(harness.policy.DEFAULTS[key])})
            for key,(obj,circuit) in harness.policy.PROGRAMS.items()}
        objects={circuit:SimpleNamespace(properties={native.STATUS_ATTR:'OFF'})
            for obj,circuit in harness.policy.PROGRAMS.values()}
        objects['C0006'].properties[native.STATUS_ATTR]='ON'
        objects['X0052'].properties[native.STATUS_ATTR]='ON'
        class Model:
            def __getitem__(self,key): return objects.get(key)
            def get_by_type(self,kind): return list(programs.values())
        t=native.IntelliCenterManualTransport('127.0.0.1')
        t.model=Model();t.read_observation=lambda:SimpleNamespace(connected=True)
        t._send=AsyncMock(side_effect=AssertionError('Read-only diagnostics actuated'))
        r=t.pump_demand_evidence()
        self.assertEqual(next(row for row in r if row['circuit_id']=='X0052')['active'],True)
        self.assertEqual(next(row for row in r if row['circuit_id']=='X0051')['active'],False)
        objects['X0052'].properties.clear()
        self.assertIsNone(next(row for row in t.pump_demand_evidence() if row['circuit_id']=='X0052')['active'])
        t.read_observation=lambda:SimpleNamespace(connected=False)
        self.assertTrue(all(row['active'] is None for row in t.pump_demand_evidence()))
        t._send.assert_not_called()


class SolarEventGatewayTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=harness.GuardianTests.asyncSetUp
    change=harness.GuardianTests.change
    drift=harness.GuardianTests.drift
    actual=harness.GuardianTests.actual
    run_policy=harness.GuardianTests.run_policy

    async def test_06_07_ordinary_manual_speed_no_heartbeat_discovery_or_repeated_write(self):
        self.change(pool=True,actual_rpm=3000)
        self.drift('pool',3000)
        for _ in range(3): await self.run_policy('recovery_heartbeat')
        self.assertFalse(self.g.data['pending_routine'])
        self.assertFalse(self.writes)
        for _ in range(3): await self.run_policy('solar_delivery_started')
        self.assertEqual(self.g.data['pending_routine'],{'pool':2600})
        self.assertFalse(self.writes) # No ordinary running-write permit.
        self.change(pool=False,actual_rpm=0)
        await self.run_policy('recovery_heartbeat')
        self.assertEqual(self.actual('pool'),2600)
        self.assertEqual(len(self.writes),1)
        await self.run_policy('solar_delivery_started')
        self.assertEqual(len(self.writes),1)

    async def test_matching_presets_wrong_runtime_has_zero_protocol_writes(self):
        self.change(pool=True,actual_rpm=3000,heat_off=False)
        await self.run_policy('solar_delivery_started')
        self.assertFalse(self.writes)
        self.assertEqual(self.actual('solar'),2900)
        self.assertFalse(self.g.blocks_normal)

    async def test_virtual_demand_observation_does_not_expand_actuator_allowlist(self):
        for circuit in ['X0051','X0052']:
            for active in [True,False]:
                with self.assertRaises(ValueError):
                    await self.t.set_circuit(circuit,active)
        self.assertFalse(self.writes)

    async def test_native_timeout_retains_correction_without_claiming_success(self):
        self.drift('solar',2960); self.mode='timeout'
        r=await self.run_policy('solar_delivery_started')
        self.assertEqual(r['failed_writes'],1)
        self.assertEqual(r['pending_routine'],{'solar':2900})
        self.assertEqual(self.actual('solar'),2960)


class ManualServiceSessionTests(unittest.TestCase):
    def run_manual(self, **states):
        r=Replay(**{POOL:'heat',OWNS:'off',ROOF:'60',COUNT:'100',**states})
        r.ages[POOL]=600
        return r

    def test_09_12_13_adopt_all_seasons_and_roof_values_without_equipment_command(self):
        for roof in ['60','95','unknown']:
            r=self.run_manual(**{ROOF:roof})
            self.assertEqual(r.run(),[])
            self.assertEqual(r.states[M],'on')
            self.assertEqual(r.states[OWNS],'on')

    def test_10_zero_debt_service_grace_protects_every_ordinary_event(self):
        for trigger in ['tick','thermal_change','reset','midnight','ownership_resumed','solar_down','sanitation_released']:
            r=self.run_manual(**{COUNT:'480',TARGET:'71'})
            r.ages[POOL]=599
            self.assertEqual(r.run(trigger,'08:00:00'),[])
            self.assertEqual(r.states[POOL],'heat')
            self.assertEqual(r.states[OWNS],'off')
        r=self.run_manual(**{COUNT:'480',TARGET:'71'})
        self.assertEqual(r.run(),[(POOL,'off')])
        self.assertEqual(r.states[OWNS],'off')
        self.assertEqual(r.states[M],'off')
        for trigger in ['tick','midnight','solar_up','thermal_change']:
            self.assertEqual(r.run(trigger,'12:00:00'),[])
            self.assertEqual(r.states[POOL],'off')

    def test_11_debt_completion_shutdown_release_and_stable_off(self):
        r=self.run_manual(**{COUNT:'478'})
        self.assertEqual(r.run(),[])
        self.assertEqual(r.states[M],'on')
        self.assertEqual(r.run(),[(POOL,'off')])
        self.assertEqual(r.states[COUNT],'480')
        self.assertEqual(r.states[M],'off')
        self.assertEqual(r.states[OWNS],'off')
        for _ in range(3): self.assertEqual(r.run(),[])

    def test_14_15_actual_solar_promotes_then_original_five_minute_loss(self):
        r=self.run_manual();r.run()
        r.states.update({SOLAR:'on',DELIVERY:'on',SOURCE:'Solar',ROOF:'120'})
        self.assertEqual(r.run('solar_delivery'),[])
        self.assertEqual(r.states[M],'off')
        r.states[COUNT]='480'
        self.assertEqual(r.run(),[]) # Heating can continue after filtration quota.
        r.states.update({SOLAR:'off',ROOF:'89'})
        self.assertEqual(r.run(),[(POOL,'off')]) # Existing quota-complete loss rule.
        r=self.run_manual();r.run();r.states.update({SOLAR:'on',DELIVERY:'on',ROOF:'120'})
        r.run('solar_delivery');r.states.update({SOLAR:'off',ROOF:'89'})
        self.assertEqual(r.run(),[]) # Brief loss with debt remains protected.
        self.assertEqual(r.run('solar_down'),[(POOL,'off')])

    def test_selected_or_legacy_solar_without_x0052_does_not_promote(self):
        r=self.run_manual();r.run()
        r.states.update({SOLAR:'on',SOURCE:'Solar',ROOF:'120',DELIVERY:'off'})
        self.assertEqual(r.run('solar_delivery'),[])
        self.assertEqual(r.states[M],'on')

    def test_16_manual_authority_off_no_takeover_or_stop(self):
        r=self.run_manual(**{MASTER:'off',COUNT:'480'})
        for trigger in ['tick','midnight','reset','solar_down','solar_delivery']:
            self.assertEqual(r.run(trigger),[])
            self.assertEqual(r.states[POOL],'heat')

    def test_17_20_higher_priorities_and_auxiliary_or_unknown_state_block_writes(self):
        for key,value in [('climate.hot_tub_thermostat','heat'),
                ('input_boolean.pool_sanitation_session','on'),('input_boolean.spa_sanitation_session','on'),
                ('switch.sanitation','on'),('binary_sensor.freeze_protection_active','on'),
                ('binary_sensor.freeze_protection_active','unavailable'),('input_boolean.grid_outage_active','on'),
                ('sensor.system_mode','SERVICE'),('switch.water_slide','on'),('switch.spillway','on'),
                ('switch.jets_bubbles','on'),('binary_sensor.rpm_guardian_blocks_normal_control','on'),
                ('sensor.native_observation_age','unavailable'),('sensor.native_observation_age','121')]:
            for goal in ['100','480']:
                r=self.run_manual(**{COUNT:goal,key:value})
                self.assertEqual(r.run(),[],(key,value,goal))
                self.assertEqual(r.states[POOL],'heat')
                self.assertEqual(r.states[OWNS],'off')

    def test_21_restart_adopted_session_and_08_reset_preserve_filtration_intent(self):
        r=self.run_manual(**{TARGET:'71'});r.run()
        self.assertEqual(r.states[M],'on')
        r=Replay(**copy.deepcopy(r.states))
        self.assertEqual(r.run('reset','08:00:00'),[])
        self.assertEqual(r.states[COUNT],'0')
        self.assertEqual(r.run(),[])
        self.assertEqual(r.states[COUNT],'1')
        self.assertEqual(r.states[POOL],'heat')
        self.assertEqual(r.states[M],'on')

    def test_22_manual_off_before_completion_releases_both_markers(self):
        r=self.run_manual();r.run();r.states[POOL]='off'
        self.assertEqual(r.run('pool_off'),[])
        self.assertEqual(r.states[M],'off');self.assertEqual(r.states[OWNS],'off')
        self.assertEqual(r.run(),[])

    def test_23_thermal_shutdown_preserved_after_confirmed_solar_promotion(self):
        r=self.run_manual();r.run();r.states.update({SOLAR:'on',DELIVERY:'on',SOURCE:'Solar',ROOF:'120'})
        r.run('solar_delivery');r.states[TARGET]='71'
        self.assertEqual(r.run('thermal_change'),[(POOL,'off')])

    def test_24_stale_unknown_ledger_never_means_debt_complete(self):
        for e in [COUNT,GOAL]:
            for v in ['unknown','unavailable','nan','inf','-1']:
                r=self.run_manual(**{e:v})
                self.assertEqual(r.run(),[])
                self.assertEqual(r.states[POOL],'heat')
                for trigger in ['midnight','tick','ownership_resumed','sanitation_released']:
                    self.assertEqual(r.run(trigger,'03:00:00'),[])
        r=self.run_manual(**{M:'unavailable',COUNT:'480'})
        self.assertEqual(r.run(),[])
        r=self.run_manual();r.ages[POOL]=0
        for _ in range(3):self.assertEqual(r.run(),[])
        self.assertEqual(r.states[OWNS],'off')


class ManualSessionPhysicalIntentTests(unittest.IsolatedAsyncioTestCase):
    """Real dispatch and acknowledgment order; no live native IO."""
    setUp = gateway.ScheduleGatewayTests.setUp
    observation = gateway.ScheduleGatewayTests.observation
    dispatch = gateway.ScheduleGatewayTests.dispatch
    awaited_sequence = gateway.ScheduleGatewayTests.awaited_sequence
    awaited_run = gateway.ScheduleGatewayTests.awaited_run
    async def test_25_off_waits_for_actual_native_receipt_before_releasing_mode(self):
        self.replay.states.update({M:'on',COUNT:'480',ROOF:'60'})
        self.confirm_after=3
        await self.awaited_run()
        self.assertFalse(self.actual_active)
        self.assertEqual(self.delivered,[('B1101',
            {harness.native.STATUS_ATTR:harness.native.STATUS_OFF})])
        self.assertEqual(self.replay.states[M],'off')
        self.assertEqual(self.replay.states[OWNS],'off')

    async def test_failed_off_keeps_adoption_markers_for_recovery(self):
        self.replay.states.update({M:'on',COUNT:'480',ROOF:'60'})
        self.hold_old_receipt=True
        from datetime import datetime
        clock=iter([0,10,20,30])
        with patch.object(harness.native.asyncio,'get_running_loop',return_value=SimpleNamespace(time=lambda:next(clock))), \
             patch.object(harness.native.asyncio,'sleep',new=AsyncMock()):
            with self.assertRaisesRegex(harness.native.ManualCommandError,'confirmation timeout'):
                await self.awaited_run()
        self.assertEqual(self.replay.states[M],'on')
        self.assertEqual(self.replay.states[OWNS],'on')
