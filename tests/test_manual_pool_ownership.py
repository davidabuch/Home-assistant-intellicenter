"""Manual authority regression: replay shipped HA actions, never live IO.

Gateway delivery tests also live in test_schedule_gateway. This evaluator is
deliberately limited to the sanitation constructs exercised here; it is not HA.
"""
import copy
import json
from pathlib import Path
import unittest

from test_lightweight_schedule import Replay, Halt, SCHEDULE, MASTER, POOL, OWNS, COUNT, GOAL, TARGET, ROOF

ROOT = Path(__file__).resolve().parents[1]
HA = ROOT / 'ha_automations'
HEATING = json.loads((HA / 'heating_preference.json').read_text())
SANITATION = json.loads((HA / 'sanitation_sessions.json').read_text())
FIXTURES = HA / 'fixtures/manual_ownership_20261017'
SOURCE = 'select.pool_heat_source'


class SanitationReplay(Replay):
    def __init__(self, **changes):
        super().__init__(SANITATION, **changes)
        self.states.setdefault('timer.sanitation_session_limit', 'idle')
        self.wait_completed = True
        self.services = []

    def condition(self, c):
        if c.get('condition') == 'template' and c['value_template'] == '{{ not wait.completed }}':
            return not self.wait_completed
        return super().condition(c)

    def sequence(self, actions):
        for a in actions:
            service = a.get('action', '')
            if service.startswith('timer.'):
                self.services.append(service)
                self.states[a['target']['entity_id']] = 'active' if service == 'timer.start' else 'idle'
            elif service.startswith('switch.'):
                self.services.append(service)
                e = a['target']['entity_id']
                v = 'on' if service == 'switch.turn_on' else 'off'
                self.commands.append((e, v))
                self.states[e] = v
            elif service == 'automation.trigger':
                p = Replay(HEATING, **self.states)
                self.commands.extend(p.run('sanitation_cleanup'))
                self.states.update(p.states)
            elif 'wait_template' in a:
                expected = {
                    "{{ is_state('climate.pool_thermostat', 'heat') }}": (POOL, 'heat'),
                    "{{ is_state('select.hot_tub_heat_source', 'Off') }}": ('select.hot_tub_heat_source', 'Off'),
                    "{{ is_state('binary_sensor.spa_active', 'on') }}": ('binary_sensor.spa_active', 'on'),
                }
                e, v = expected[a['wait_template']]
                self.wait_completed = self.states.get(e) == v
            elif 'stop' in a:
                raise Halt()
            else:
                super().sequence([a])


class ManualPoolOwnershipTests(unittest.TestCase):
    def test_sanitation_live_cleanup_and_release_events_preserved(self):
        live = json.loads((HA / 'fixtures/solar_session_20261020/sanitation.json').read_text())
        self.assertEqual(SANITATION, live['config'])
        self.assert_no_master_writes(SANITATION['actions'])

    def assert_no_master_writes(self, node):
        if isinstance(node, list):
            for child in node: self.assert_no_master_writes(child)
        elif isinstance(node, dict):
            if node.get('action') in ['input_boolean.turn_on','input_boolean.turn_off']:
                self.assertNotEqual(node.get('target', {}).get('entity_id'), MASTER)
            for child in node.values(): self.assert_no_master_writes(child)

    def test_preference_rechecks_authority_after_branch_selection(self):
        class RevokingReplay(Replay):
            def condition(self, c):
                result = super().condition(c)
                if c.get('entity_id') == 'input_select.pool_heating_preference':
                    self.states[MASTER] = 'off'
                return result
        r = RevokingReplay(HEATING)
        self.assertFalse(any(e == SOURCE for e, _ in r.run('roof_change')))

    def test_baseline_preference_defect_reproduces_actual_source_action(self):
        old = json.loads((FIXTURES / 'heating_preference.json').read_text())
        r = Replay(old, **{MASTER:'off', SOURCE:'Gas', ROOF:'120'})
        self.assertIn((SOURCE,'Solar'), r.run('roof_change'))
        r = Replay(HEATING, **{MASTER:'off', SOURCE:'Gas', ROOF:'120'})
        self.assertNotIn(SOURCE, [e for e, _ in r.run('roof_change')])
        self.assertEqual(r.states[SOURCE], 'Gas')

    def test_manual_all_preferences_and_triggers_block_pool_writes_but_allow_spa(self):
        for authority in ['off', 'unknown', 'unavailable']:
            for preference in ['Off','Gas','Solar','Eco Heat']:
                for trigger in ['pool_start','roof_change','preference_change','grid_restored','startup','ownership_resumed']:
                    with self.subTest(authority=authority, preference=preference, trigger=trigger):
                        r = Replay(HEATING, **{MASTER:authority, SOURCE:'Gas', 'input_select.pool_heating_preference':preference,
                            'input_select.hot_tub_heating_preference':'Gas'})
                        commands = r.run(trigger)
                        self.assertFalse(any(e == SOURCE for e, _ in commands))
                        self.assertEqual(r.states[SOURCE], 'Gas')
                        if trigger != 'ownership_resumed':
                            self.assertIn(('select.hot_tub_heat_source','Gas'), commands)

    def test_manual_overnight_rollover_restart_target_and_off(self):
        r = Replay(**{MASTER:'off', SOURCE:'Gas', ROOF:'60', COUNT:'100'})
        for trigger, clock in [('ownership_released','23:58:00'),('midnight','00:00:00'),
                ('tick','00:01:00'),('tick','03:20:00'),('thermal_change','03:57:00'),
                ('solar_down','04:00:00'),('reset','08:00:00'),('tick','08:01:00')]:
            with self.subTest(trigger=trigger, clock=clock):
                self.assertEqual(r.run(trigger, clock), [])
                self.assertEqual(r.states[POOL], 'heat')
                self.assertEqual(r.states[OWNS], 'off')
                self.assertEqual(r.states[SOURCE], 'Gas')
        self.assertEqual(r.states[COUNT], '1')
        # Restart/reload reconstructs from restored helper states; no authority claim.
        r = Replay(**r.states)
        r.states[TARGET] = '95'
        self.assertEqual(r.run('thermal_change'), [])
        r.states[POOL] = 'off'
        for trigger in ['pool_off','tick','solar_up','grid_restored']:
            self.assertEqual(r.run(trigger), [])
            self.assertEqual(r.states[POOL], 'off')

    def test_manual_every_schedule_trigger_no_equipment_writes(self):
        for t in SCHEDULE['triggers']:
            for clock in ['00:00:00','03:57:00','08:00:00','12:00:00']:
                for running in ['heat','off']:
                    r = Replay(**{MASTER:'off',POOL:running,COUNT:'480',TARGET:'71'})
                    self.assertEqual(r.run(t['id'], clock), [])

    def test_delayed_claim_cannot_reclaim_revoked_master(self):
        r = Replay(**{POOL:'off',OWNS:'off'})
        def revoke(replay, action):
            if action.get('action') == 'climate.set_hvac_mode':
                replay.states[MASTER] = 'off'
        r.before_command = revoke
        r.run('solar_up')
        self.assertEqual(r.states[OWNS], 'off')

    def test_automatic_mapping_and_pool_only_resume(self):
        for preference, roof, result in [('Off','120','Off'),('Gas','120','Gas'),
                ('Solar','60','Solar'),('Eco Heat','89','Gas'),('Eco Heat','90','Solar')]:
            r = Replay(HEATING, **{'input_select.pool_heating_preference':preference,ROOF:roof})
            self.assertIn((SOURCE,result),r.run('ownership_resumed'))
            self.assertFalse(any(e == 'select.hot_tub_heat_source' for e, _ in r.commands))
        r = Replay(**{MASTER:'off',POOL:'off',OWNS:'off'})
        self.assertEqual(r.run(), [])
        r.states[MASTER] = 'on'
        # The resumption event itself need not start equipment; subsequent safe
        # minute reconciliation uses current demand, and emits no duplicate start.
        r.run('ownership_resumed')
        self.assertIn((POOL,'heat'),r.run())
        self.assertEqual(r.run(), [])

    def test_overnight_history_reproduces_automatic_adoption_and_debt_completion(self):
        r = Replay(**{MASTER:'on',POOL:'heat',OWNS:'off',ROOF:'60',COUNT:'480',GOAL:'540',
            'input_select.pool_heating_preference':'Eco Heat',SOURCE:'Gas',TARGET:'90'})
        self.assertEqual(r.run('tick','03:20:00'), [])
        self.assertEqual(r.states[OWNS], 'on')
        self.assertEqual(r.states[COUNT], '481')
        r.states[GOAL] = '480'
        self.assertIn((POOL,'off'),r.run('thermal_change','03:20:05'))
        # Identical stimulus in manual mode has no equipment-write action.
        r = Replay(**{MASTER:'off',POOL:'heat',OWNS:'off',ROOF:'60',COUNT:'480',GOAL:'540'})
        r.run('tick','03:20:00'); r.states[GOAL] = '480'
        self.assertEqual(r.run('thermal_change','03:20:05'), [])

    def test_sanitation_never_changes_operator_master_and_keeps_priority(self):
        self.assert_no_master_writes(SANITATION['actions'])
        for master in ['on','off']:
            r = SanitationReplay(**{MASTER:master,'input_boolean.pool_sanitation_session':'on'})
            self.assertIn(('switch.sanitation','on'),r.run('pool_start'))
            self.assertEqual(r.states[SOURCE], 'Off')
            self.assertEqual(r.states[MASTER], master)
            schedule = Replay(**r.states)
            self.assertEqual(schedule.run(), [])
            preference = Replay(HEATING, **r.states)
            self.assertFalse(any(e == SOURCE for e, _ in preference.run('roof_change')))
            r.states['input_boolean.pool_sanitation_session'] = 'off'
            self.assertIn(('switch.sanitation','off'),r.run('pool_stop'))
            self.assertEqual(r.states[MASTER], master)
            if master == 'off': self.assertEqual(r.states[SOURCE], 'Off')

    def test_restart_without_sanitation_does_not_stop_manual_spa_or_reclaim_pool(self):
        for master in ['off','on']:
            r = SanitationReplay(**{MASTER:master,'climate.hot_tub_thermostat':'heat',SOURCE:'Gas'})
            self.assertEqual(r.run('restart'), [])
            self.assertEqual(r.states['climate.hot_tub_thermostat'],'heat')
            self.assertEqual(r.states[MASTER],master)
            self.assertEqual(r.states[SOURCE],'Gas')

    def test_real_sanitation_obligation_still_cleans_up_on_restart_outage_timeout(self):
        for trigger in ['restart','outage','timeout']:
            for entity, value in [('input_boolean.pool_sanitation_session','on'),
                    ('input_boolean.spa_sanitation_session','on'),('switch.sanitation','on'),
                    ('timer.sanitation_session_limit','active'),('timer.sanitation_session_limit','paused')]:
                r = SanitationReplay(**{MASTER:'off',entity:value,'climate.hot_tub_thermostat':'heat'})
                commands = r.run(trigger)
                self.assertIn(('switch.sanitation','off'),commands)
                self.assertIn(('climate.hot_tub_thermostat','off'),commands)
                self.assertIn('timer.cancel',r.services)
                self.assertEqual(r.states[MASTER],'off')

    def test_safety_guard_still_blocks_pool_preference(self):
        for states in [{'input_boolean.grid_outage_active':'on'},
                {'binary_sensor.rpm_guardian_blocks_normal_control':'on'},
                {'binary_sensor.rpm_guardian_blocks_normal_control':'unavailable'}]:
            r = Replay(HEATING, **states)
            self.assertEqual(r.run('roof_change'), [])


if __name__ == '__main__':
    unittest.main()
