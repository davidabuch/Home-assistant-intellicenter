"""Replay untouched Oct 24 live HA originals; expose handoff gaps, not fixes.

The shared evaluator executes equipment-write intent from HA action JSON.
These are offline simulations, not HA trace or physical commissioning results.
"""
import hashlib
import json
from pathlib import Path
import unittest

from test_lightweight_schedule import Replay, POOL, OWNS, MASTER, COUNT, GOAL, TARGET, ROOF

FIXTURES = Path(__file__).resolve().parents[1] / 'ha_automations/fixtures/cleaning_20261024'
SCHEDULE = json.loads((FIXTURES / 'schedule.original.json').read_text())
HEATING = json.loads((FIXTURES / 'heating.original.json').read_text())
CLEANING = 'binary_sensor.pool_cleaning_active'
MANUAL = 'input_boolean.pool_simple_manual_circulation'
SOURCE = 'select.pool_heat_source'


class CleaningLiveContractTests(unittest.TestCase):
    def replay(self, config=SCHEDULE, **changes):
        r = Replay(config, **{CLEANING: 'off', **changes})
        r.ages[CLEANING] = 20
        return r

    def test_full_originals_match_captured_hash_manifest(self):
        manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        for record in manifest['automations'].values():
            self.assertEqual(hashlib.sha256((FIXTURES / record['file']).read_bytes()).hexdigest(), record['sha256'])
        self.assertEqual(manifest['automations']['schedule']['ha_config_hash'], '59cd45a45d9f6452')

    def test_recorded_idle_failure_is_preserved_as_observation_evidence(self):
        entities = {v['entity_id']: v['states'] for v in json.loads((FIXTURES / 'idle-history.json').read_text())['entities']}
        self.assertEqual([v['state'] for v in entities['switch.pool_cleaning']], ['on', 'off'])
        self.assertEqual([v['state'] for v in entities[POOL]], ['off'])
        self.assertEqual([v['state'] for v in entities['sensor.pump_rpm']], ['0.0'])

    def test_cleaning_on_suppresses_every_schedule_trigger_equipment_write(self):
        for trigger in SCHEDULE['triggers']:
            for pool in ('off', 'heat'):
                r = self.replay(**{CLEANING:'on', POOL:pool})
                self.assertEqual(r.run(trigger['id']), [], (trigger, pool))

    def test_twenty_second_release_guard_remains_effective(self):
        for age in (0, 19):
            r = self.replay(**{COUNT:'480', TARGET:'70'})
            r.ages[CLEANING] = age
            self.assertEqual(r.run('tick'), [])

    def test_live_release_trigger_does_not_bypass_manual_service_grace(self):
        r = self.replay(**{POOL:'heat', OWNS:'off', COUNT:'480'})
        r.ages[POOL] = 30
        self.assertEqual(r.run('cleaning_released'), [])
        self.assertEqual(r.run('tick'), [])
        self.assertEqual(r.states[POOL], 'heat')

    def test_live_release_trigger_missing_shutdown_branch_is_reproduced(self):
        r = self.replay(**{POOL:'heat', OWNS:'off', COUNT:'480', ROOF:'60'})
        self.assertEqual(r.run('cleaning_released'), [])
        self.assertIn((POOL, 'off'), r.run('tick'))

    def test_live_release_trigger_missing_target_branch_is_reproduced(self):
        r = self.replay(**{TARGET:'70'})
        self.assertEqual(r.run('cleaning_released'), [])
        self.assertIn((POOL, 'off'), r.run('tick'))

    def test_live_solar_reacquisition_release_gap_is_reproduced(self):
        r = self.replay(**{POOL:'off', OWNS:'off', ROOF:'120'})
        self.assertEqual(r.run('cleaning_released'), [])
        self.assertIn((POOL, 'heat'), r.run('tick'))

    def test_live_night_filtration_release_gap_is_reproduced(self):
        r = self.replay(**{POOL:'off', OWNS:'off', ROOF:'60', COUNT:'100'})
        self.assertEqual(r.run('cleaning_released', '01:00:00'), [])
        self.assertIn((POOL, 'heat'), r.run('tick', '01:01:00'))

    def test_manual_service_grace_and_master_off_are_not_weakened(self):
        r = self.replay(**{POOL:'heat', OWNS:'off', COUNT:'480', ROOF:'60'})
        r.ages[POOL] = 599
        self.assertEqual(r.run('tick'), [])
        r.ages[POOL] = 600
        self.assertIn((POOL, 'off'), r.run('tick'))
        for trigger in SCHEDULE['triggers']:
            r = self.replay(**{MASTER:'off', POOL:'heat', SOURCE:'Gas'})
            self.assertEqual(r.run(trigger['id']), [])

    def test_cleaning_does_not_stop_valid_filtration_credit_or_rollover(self):
        r = self.replay(**{CLEANING:'on', COUNT:'100'})
        self.assertEqual(r.run('tick'), [])
        self.assertEqual(r.states[COUNT], '101')
        self.assertEqual(r.run('reset', '08:00:00'), [])
        self.assertEqual(r.states[COUNT], '0')
        r = self.replay(**{CLEANING:'on', COUNT:'100', 'sensor.pump_rpm':'0'})
        r.run('tick')
        self.assertEqual(r.states[COUNT], '100')

    def test_pool_preference_pauses_for_cleaning_and_resumes_after_confirmation(self):
        r = self.replay(HEATING, **{CLEANING:'on', 'input_select.pool_heating_preference':'Gas'})
        self.assertFalse(any(e == SOURCE for e, _ in r.run('preference_changed')))
        r.states[CLEANING] = 'off'
        r.ages[CLEANING] = 19
        self.assertFalse(any(e == SOURCE for e, _ in r.run('cleaning_released')))
        r.ages[CLEANING] = 20
        self.assertIn((SOURCE, 'Gas'), r.run('cleaning_released'))


if __name__ == '__main__':
    unittest.main()
