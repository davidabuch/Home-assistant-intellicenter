"""Replay the shipped HA configuration; no sockets or equipment commands.

This strict evaluator covers only the native HA constructs used by these
fixtures. It is simulation, not a substitute for HA schema/physical tests.
Unknown constructs fail the test instead of silently passing.
"""
import copy
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'ha_automations'
POOL = 'climate.pool_thermostat'
OWNS = 'input_boolean.pool_simple_schedule_owns_pool'
MASTER = 'input_boolean.pool_automatic_ownership'
COUNT = 'counter.pool_simple_filtration_minutes'
TARGET = 'sensor.pool_target_temperature'
ACTUAL = 'sensor.pool_temperature'
ROOF = 'sensor.solar_temperature'
GOAL = 'sensor.pool_daily_filtration_target'
SCHEDULE = json.loads((ROOT / 'pool_simple_solar_and_filtration.json').read_text())
BEFORE = json.loads((ROOT / 'fixtures/pool_simple_before_20261015.json').read_text())


class Halt(Exception):
    pass


class Replay:
    def __init__(self, config=SCHEDULE, **changes):
        self.config = copy.deepcopy(config)
        self.states = {
            POOL:'heat', OWNS:'on', MASTER:'on', COUNT:'196', TARGET:'90',
            ACTUAL:'74', ROOF:'132', GOAL:'480', 'sensor.pump_rpm':'2900',
            'climate.hot_tub_thermostat':'off', 'input_boolean.grid_outage_active':'off',
            'input_boolean.grid_outage_protection':'on', 'input_boolean.grid_outage_operator_bypass_latch':'off',
            'input_boolean.pool_sanitation_session':'off', 'input_boolean.spa_sanitation_session':'off',
            'switch.sanitation':'off', 'switch.water_slide':'off', 'switch.spillway':'off',
            'switch.jets_bubbles':'off', 'binary_sensor.freeze_protection_active':'off',
            'sensor.system_mode':'AUTO', 'input_select.pool_heating_preference':'Solar',
            'select.pool_heat_source':'Solar',
        }
        self.states.update(changes)
        self.commands = []
        self.before_command = None

    def numeric(self, value):
        try:
            n = float(self.states.get(value, value))
            return n if math.isfinite(n) else None
        except (TypeError, ValueError):
            return None

    def condition(self, c):
        t = c['condition']
        if t == 'trigger':
            return self.trigger in (c['id'] if isinstance(c['id'], list) else [c['id']])
        if t == 'state':
            wanted = c['state'] if isinstance(c['state'], list) else [c['state']]
            return self.states.get(c['entity_id']) in wanted
        if t == 'numeric_state':
            v = self.numeric(c['entity_id'])
            if v is None: return False
            for op in ['above','below']:
                if op not in c: continue
                bound = self.numeric(c[op])
                if bound is None or not (v > bound if op == 'above' else v < bound): return False
            return True
        if t in ['and','or','not']:
            results = [self.condition(x) for x in c['conditions']]
            return any(results) if t == 'or' else (not any(results) if t == 'not' else all(results))
        if t == 'time':
            a,b = c.get('after','00:00:00'),c.get('before','23:59:59')
            # HA uses inclusive after / exclusive before.
            return a <= self.time < b if a < b else self.time >= a or self.time < b
        if t == 'template':
            # Only the exact existing ledger comparison expressions are used.
            expr = c['value_template']
            if expr not in {
                "{{ states('counter.pool_simple_filtration_minutes') | int(0) < states('sensor.pool_daily_filtration_target') | int(600) }}",
                "{{ states('counter.pool_simple_filtration_minutes') | int(0) >= states('sensor.pool_daily_filtration_target') | int(600) }}",
            }: raise AssertionError('Unsupported template '+expr)
            left,right = self.numeric(COUNT),self.numeric(GOAL)
            left = 0 if left is None else int(left)
            right = 600 if right is None else int(right)
            return left >= right if '>=' in expr else left < right
        raise AssertionError('Unsupported condition '+t)

    def all(self, conditions):
        if isinstance(conditions, dict): conditions=[conditions]
        return all(self.condition(c) for c in conditions)

    def sequence(self, actions):
        for a in actions:
            if 'condition' in a:
                if not self.condition(a): raise Halt()
            elif 'if' in a:
                self.sequence(a.get('then',[]) if self.all(a['if']) else a.get('else',[]))
            elif 'choose' in a:
                for b in a['choose']:
                    if self.all(b['conditions']):
                        self.sequence(b['sequence'])
                        break
                else: self.sequence(a.get('default',[]))
            elif 'action' in a:
                service,e = a['action'],a['target']['entity_id']
                if service == 'counter.increment': self.states[e]=str(int(self.states[e])+1)
                elif service == 'counter.reset': self.states[e]='0'
                elif service in ['input_boolean.turn_on','input_boolean.turn_off']:
                    self.states[e]='on' if service.endswith('turn_on') else 'off'
                elif service == 'climate.set_hvac_mode':
                    self.commands.append((e,a['data']['hvac_mode']))
                    self.states[e]=a['data']['hvac_mode']
                elif service == 'select.select_option':
                    self.commands.append((e,a['data']['option']))
                    self.states[e]=a['data']['option']
                else: raise AssertionError('Unsupported action '+service)
                if self.before_command: self.before_command(self,a)
            elif 'delay' in a: pass
            else: raise AssertionError('Unsupported action '+str(a))

    def run(self, trigger='tick', time='12:32:00'):
        self.trigger,self.time=trigger,time
        self.commands=[]
        if self.all(self.config.get('conditions',[])):
            try: self.sequence(self.config['actions'])
            except Halt: pass
        return self.commands


class LightweightScheduleTests(unittest.TestCase):
    def test_01_eligible_heating_starts(self):
        r=Replay(**{POOL:'off',OWNS:'off'})
        self.assertIn((POOL,'heat'),r.run('solar_up'))
        self.assertEqual(r.states[OWNS],'on')

    def test_02_reproduce_original_failure_and_repair(self):
        old=Replay(BEFORE,**{TARGET:'71'})
        self.assertEqual(old.run(),[])
        self.assertEqual(old.states[POOL],'heat')
        r=Replay(**{TARGET:'71'})
        self.assertIn((POOL,'off'),r.run('thermal_change'))
        self.assertEqual(r.states[OWNS],'off')

    def test_03_hot_roof_cannot_restart_satisfied_pool(self):
        r=Replay(**{TARGET:'71',POOL:'off',OWNS:'off'})
        for trigger in ['solar_up','tick','thermal_change','grid_restored','reset']:
            with self.subTest(trigger=trigger):
                self.assertNotIn((POOL,'heat'),r.run(trigger))
        for _ in range(5): self.assertEqual(r.run(),[])

    def test_04_raise_target_without_new_roof_crossing(self):
        r=Replay(**{TARGET:'71'})
        r.run('thermal_change')
        r.states[TARGET]='90'
        self.assertIn((POOL,'heat'),r.run('thermal_change'))
        self.assertEqual(r.run(),[]) # no repeat native start/source commands

    def test_05_solar_interruption_and_recovery(self):
        for config in [BEFORE,SCHEDULE]:
            r=Replay(config,**{ROOF:'89'})
            self.assertEqual(r.run(),[]) # brief interruption/debt remains
            self.assertEqual(r.states[POOL],'heat')
            self.assertIn((POOL,'off'),r.run('solar_down')) # five-minute trigger
            r.states[ROOF]='110'
            self.assertIn((POOL,'heat'),r.run())
            eco=Replay(config,**{ROOF:'89','input_select.pool_heating_preference':'Eco Heat'})
            self.assertEqual(eco.run('solar_down'),[]) # gas fallback retained

    def test_06_midnight_debt_and_target_satisfied(self):
        for running in ['heat','off']:
            r=Replay(**{TARGET:'71',POOL:running,OWNS:'off'})
            commands=r.run('midnight','00:00:00')
            self.assertEqual(r.states[POOL],'heat')
            self.assertEqual(r.states[OWNS],'on')
            self.assertEqual((POOL,'heat') in commands,running=='off')
            self.assertNotIn((POOL,'off'),r.run('tick','01:00:00'))

    def test_07_quota_stops_unneeded_circulation_preserves_heating(self):
        for target,roof,pref,stop in [('71','132','Solar',True),('90','132','Solar',False),('90','89','Solar',True),('90','132','Off',True)]:
            with self.subTest(target=target,roof=roof,pref=pref):
                r=Replay(**{COUNT:'480',TARGET:target,ROOF:roof,'input_select.pool_heating_preference':pref})
                self.assertEqual((POOL,'off') in r.run(),stop)
        r=Replay(**{COUNT:'479',TARGET:'71'})
        self.assertIn((POOL,'off'),r.run('tick','01:00:00'))
        self.assertEqual(r.states[COUNT],'480')

    def test_08_spa_priority(self):
        for pool in ['heat','off']:
            r=Replay(**{'climate.hot_tub_thermostat':'heat',TARGET:'71',POOL:pool})
            for trigger in ['tick','thermal_change','midnight','solar_up','reset','ownership_resumed']:
                self.assertEqual(r.run(trigger),[])

    def test_09_sanitation_independent_of_master(self):
        for flag in ['input_boolean.pool_sanitation_session','input_boolean.spa_sanitation_session','switch.sanitation']:
            for trigger in ['tick','thermal_change','ownership_resumed','reset','midnight','solar_down']:
                r=Replay(**{flag:'on',TARGET:'71'})
                self.assertEqual(r.run(trigger),[])

    def test_10_outage_authority_and_ledger(self):
        r=Replay(**{'input_boolean.grid_outage_active':'on',TARGET:'71',MASTER:'off'})
        self.assertEqual(r.run(),[])
        self.assertEqual(r.states[COUNT],'197')
        for trigger in ['solar_up','thermal_change','ownership_resumed','reset']:
            self.assertEqual(r.run(trigger),[])
        self.assertEqual(r.states[COUNT],'0') # reset even under outage/external authority

    def test_11_manual_and_external_ownership(self):
        r=Replay(**{MASTER:'off',TARGET:'71'})
        for trigger in ['tick','thermal_change','solar_up','reset','midnight']:
            self.assertEqual(r.run(trigger),[])
        r=Replay(**{OWNS:'off',TARGET:'71'})
        self.assertEqual(r.run(),[]) # do not cancel unclaimed external session
        self.assertEqual(r.states[OWNS],'off')
        # Automatic Ownership ON intentionally re-adopts external eligible heat.
        r.states[TARGET]='90'
        r.run()
        self.assertEqual(r.states[OWNS],'on')

    def test_12_restart_reconciles_without_blind_replay(self):
        for target,master,start in [('71','on',False),('90','off',False),('90','on',True)]:
            r=Replay(**{TARGET:target,MASTER:master,POOL:'off',OWNS:'off'})
            # Restored current state, first periodic tick after reload/start.
            self.assertEqual((POOL,'heat') in r.run(),start)
        r=Replay(**{TARGET:'71',ROOF:'unknown'})
        self.assertIn((POOL,'off'),r.run()) # known demand satisfied; roof irrelevant
        r=Replay(**{TARGET:'71',ROOF:'60',POOL:'off',OWNS:'off'})
        self.assertIn((POOL,'heat'),r.run('tick','03:00:00'))
        self.assertEqual(r.states[OWNS],'on')
        self.assertEqual(r.run('ownership_resumed','03:01:00'),[])

    def test_08_rollover_is_separate_from_equipment(self):
        r=Replay(**{COUNT:'479',TARGET:'71'})
        r.run('reset','08:00:00')
        self.assertEqual(r.states[COUNT],'0')
        self.assertIn((POOL,'off'),r.run('tick','08:01:00'))

    def test_unknown_temperature_never_starts_or_claims_satisfaction(self):
        for entity in [TARGET,ACTUAL]:
            for invalid in ['unknown','unavailable','nan','inf','None','0']:
                for pool in ['off','heat']:
                    r=Replay(**{entity:invalid,POOL:pool,OWNS:'off' if pool=='off' else 'on'})
                    self.assertEqual(r.run('thermal_change'),[])
                r=Replay(**{entity:invalid,COUNT:'480'})
                self.assertEqual(r.run(),[]) # hot roof with unknown demand

    def test_hot_roof_gas_demand_is_not_quota_shutdown(self):
        r=Replay(**{COUNT:'480','input_select.pool_heating_preference':'Gas'})
        self.assertEqual(r.run(),[])

    def test_safety_and_other_circulation_guards(self):
        for e,v in [('binary_sensor.freeze_protection_active','on'),('binary_sensor.freeze_protection_active','unavailable'),('sensor.system_mode','SERVICE'),('switch.water_slide','on'),('switch.spillway','on'),('switch.jets_bubbles','on')]:
            r=Replay(**{e:v,TARGET:'71'})
            self.assertEqual(r.run(),[])

    def test_authority_revoked_while_queued_or_after_source_selection(self):
        r=Replay(**{POOL:'off',OWNS:'off'})
        def revoke(replay, action):
            if action.get('action')=='select.select_option': replay.states[MASTER]='off'
        r.before_command=revoke
        self.assertNotIn((POOL,'heat'),r.run())
        self.assertEqual(r.states[OWNS],'off')
        r.states[MASTER]='on'
        r.before_command=None
        r.run()
        self.assertEqual(r.states[OWNS],'on')
        self.assertEqual(r.run('pool_off'),[]) # stale queued off event
        self.assertEqual(r.states[OWNS],'on')

    def test_accounting_requires_observed_circulation_and_only_ticks(self):
        for rpm,pool,spa,credit in [('0','heat','off',False),('2600','heat','off',True),('2600','off','off',False),('2600','heat','heat',False)]:
            r=Replay(**{'sensor.pump_rpm':rpm,POOL:pool,'climate.hot_tub_thermostat':spa})
            r.run()
            self.assertEqual(r.states[COUNT],'197' if credit else '196')
            r.run('thermal_change')
            self.assertEqual(r.states[COUNT],'197' if credit else '196')

    def test_no_rpm_writes_or_poolos_dependencies(self):
        text=json.dumps(SCHEDULE)
        self.assertNotIn('number.',text)
        self.assertNotIn('PMPCIRC',text)
        self.assertNotIn('poolos',text.lower())
        pref=json.loads((ROOT/'heating_preference.json').read_text())
        self.assertEqual(pref['conditions'][0]['condition'],'not')
        grid=json.loads((ROOT/'grid_outage_existing.json').read_text())
        self.assertNotIn('counter.reset',json.dumps(grid))
        self.assertNotIn('accounting_reset',json.dumps(grid))
        self.assertNotIn('number.pool_rpm',json.dumps(grid['actions']))
        self.assertIn('climate.hot_tub_thermostat',json.dumps(grid['actions']))
        self.assertIn('select.pool_heat_source',json.dumps(grid['actions']))


if __name__ == '__main__': unittest.main()
