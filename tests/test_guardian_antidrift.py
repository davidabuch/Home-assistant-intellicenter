"""Event discovery versus durable servicing through the actual native gateway.

Only protocol IO/telemetry are synthetic. Native identity, dispatch lock,
authorization and fresh readback remain real. No live hardware is used.
"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import unittest

import test_rpm_guardian as harness
import test_guardian_final_recovery as recovery

policy, native = harness.policy, harness.native


class AntiDriftTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = harness.GuardianTests.asyncSetUp
    change = harness.GuardianTests.change
    drift = harness.GuardianTests.drift
    actual = harness.GuardianTests.actual
    outage = harness.GuardianTests.outage
    restore = harness.GuardianTests.restore
    run_policy = harness.GuardianTests.run_policy
    boot = recovery.FinalRecoveryTests.boot

    async def heartbeat(self):
        return await self.run_policy('recovery_heartbeat')

    async def test_heartbeat_reads_but_does_not_establish_new_drift(self):
        self.drift('solar', 2960)
        for _ in range(3): r = await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2960)
        self.assertEqual(r['last_observed']['solar'], 2960)
        self.assertEqual(r['results']['solar'], 'DRIFT: awaiting routine event')
        self.assertEqual(r['pending_routine'], {})
        self.assertFalse(self.writes)
        self.assertFalse(self.g.blocks_normal)

    async def test_scheduled_session_startup_and_explicit_events_correct(self):
        for reason in ('accounting_rollover', 'before_filtration', 'startup',
                       'spa_session', 'sanitation_request', 'manual', 'manual_button',
                       'spa_requested', 'sanitation_requested', 'heater_requested',
                       'solar_requested'):
            with self.subTest(reason=reason):
                self.drift('solar', 2960)
                await self.heartbeat()
                self.assertEqual(self.actual('solar'), 2960)
                await self.run_policy(reason)
                self.assertEqual(self.actual('solar'), 2900)
                self.assertEqual(self.g.data['pending_routine'], {})
        self.assertEqual(len(self.writes), 11)

    async def test_draft_is_not_authority_but_apply_is(self):
        await self.g.edit('solar', 3000)
        self.drift('solar', 2960)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2960)
        await self.run_policy('manual_button')
        self.assertEqual(self.actual('solar'), 2900)
        await self.g.apply()
        self.assertEqual(self.actual('solar'), 3000)

    async def test_running_drift_not_discovered_by_heartbeat_after_idle(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.heartbeat()
        self.change(pool=False, actual_rpm=0)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2960)
        self.assertFalse(self.writes)

    async def test_deferred_event_obligation_completes_when_idle(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.run_policy('accounting_rollover')
        self.assertEqual(self.saved[-1]['pending_routine'], {'solar': 2900})
        self.assertFalse(self.g.blocks_normal)
        await self.heartbeat()
        self.assertFalse(self.writes)
        self.change(pool=False, actual_rpm=0)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2900)
        self.assertEqual(self.g.data['pending_routine'], {})
        self.assertEqual(len(self.writes), 1)

    async def test_deferred_obligation_survives_last_durable_record_boot(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.run_policy('before_filtration')
        await self.boot()
        await self.heartbeat()
        self.assertFalse(self.writes)
        self.change(pool=False, actual_rpm=0)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2900)

    async def test_startup_initialization_defers_discovery_durably(self):
        self.change(fresh=False)
        self.drift('solar', 2960)
        await self.g.queue_startup_scan()
        await self.heartbeat()
        self.assertTrue(self.saved[-1]['routine_scan_pending'])
        await self.boot()
        self.change(fresh=True)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2900)
        self.assertFalse(self.g.data['routine_scan_pending'])

    async def test_stale_routine_event_survives_until_native_read_ready(self):
        self.change(fresh=False)
        self.drift('solar', 2960)
        await self.run_policy('accounting_rollover')
        await self.boot()
        self.change(fresh=True)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2900)

    async def test_outage_and_restoration_are_not_routine_obligations(self):
        self.drift('solar', 2960)
        self.outage()
        await self.heartbeat()
        self.assertEqual(self.actual(), 1500)
        self.assertTrue(self.g.data['restoration_pending'])
        self.assertEqual(self.g.data['pending_routine'], {})
        await self.boot()
        self.restore()
        await self.heartbeat()
        self.assertEqual(self.actual(), 2600)
        self.assertEqual(self.actual('solar'), 2960)
        self.assertFalse(self.g.data['restoration_pending'])
        self.assertFalse(self.g.blocks_normal)

    async def test_heartbeat_discovers_stranded_outage_value(self):
        self.drift('pool', 1500)
        self.change(authority=False)
        await self.heartbeat()
        self.assertTrue(self.g.data['restoration_pending'])
        self.assertTrue(self.g.blocks_normal)
        self.assertFalse(self.writes)
        self.change(authority=True)
        await self.heartbeat()
        self.assertEqual(self.actual(), 2600)
        self.assertFalse(self.g.blocks_normal)

    async def test_running_approval_not_permission_for_normal_pending(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.run_policy('spa_session')
        await self.heartbeat()
        self.assertTrue(self.g.data['running_pool_approved'])
        self.assertFalse(self.writes)
        self.outage()
        self.g.data['running_pool_approved'] = False
        await self.heartbeat()
        self.assertEqual(self.actual(), 2600)
        self.assertFalse(self.writes)

    async def test_pending_work_still_obeys_all_safety_and_ownership_gates(self):
        self.drift('solar', 2960)
        self.change(pool=True, actual_rpm=2900)
        await self.run_policy('sanitation_request')
        self.change(pool=False, actual_rpm=0)
        for gate in ('authority', 'freeze_off', 'automatic_mode', 'sanitation_off',
                     'spa_off', 'heat_off', 'accessories_off'):
            self.change(**{gate: False})
            await self.heartbeat()
            self.assertFalse(self.writes, gate)
            self.change(**{gate: True})
        self.change(bypass=True)
        await self.heartbeat()
        self.assertFalse(self.writes)
        self.change(bypass=False)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2900)

    async def test_obligation_clears_on_matching_read_not_new_drift(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.run_policy('before_filtration')
        self.drift('solar', 2900)
        await self.heartbeat()
        self.drift('solar', 2960)
        self.change(pool=False, actual_rpm=0)
        await self.heartbeat()
        self.assertFalse(self.writes)
        self.assertEqual(self.g.data['pending_routine'], {})

    async def test_uncertain_normal_write_reads_before_retry_after_boot(self):
        self.drift('solar', 2960)
        self.mode = 'ack_lost'
        await self.run_policy('manual_button')
        self.assertEqual(self.actual('solar'), 2900)
        self.assertEqual(self.saved[-1]['pending_routine'], {'solar': 2900})
        await self.boot()
        self.mode = 'ok'
        await self.heartbeat()
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.g.data['pending_routine'], {})

    async def test_apply_supersedes_pending_target_atomically(self):
        self.change(pool=True, actual_rpm=2900)
        self.drift('solar', 2960)
        await self.run_policy('manual_button')
        await self.g.edit('solar', 3000)
        await self.g.apply()
        self.assertEqual(self.saved[-1]['pending_routine'], {'solar': 3000})
        await self.boot()
        self.change(pool=False, actual_rpm=0)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 3000)

    async def test_legacy_store_migrates_without_unrequested_scan(self):
        record = deepcopy(self.saved[-1])
        record.pop('pending_routine'); record.pop('routine_scan_pending')
        await self.boot(record)
        self.drift('solar', 2960)
        await self.heartbeat()
        self.assertEqual(self.actual('solar'), 2960)
        self.assertTrue(self.g.data['enabled'])
        self.assertTrue(self.g.data['running_pool_approved'])

    async def test_invalid_pending_record_fails_closed(self):
        record = deepcopy(self.saved[-1])
        record['pending_routine'] = {'solar': 1500}
        await self.boot(record)
        await self.g.queue_startup_scan()
        await self.heartbeat()
        self.assertFalse(self.g.loaded)
        self.assertTrue(self.g.blocks_normal)
        self.assertFalse(self.writes)

    async def test_grid_and_unknown_reasons_do_not_discover_routine_drift(self):
        self.drift('solar', 2960)
        for reason in ('grid_policy', 'ha_policy_request', 'unrecognized'):
            await self.run_policy(reason)
        self.assertEqual(self.actual('solar'), 2960)
        self.assertFalse(self.writes)

    async def test_queued_requests_serialize_and_never_cycle_equipment(self):
        self.drift('solar', 2960)
        await asyncio.gather(self.run_policy('manual_button'),
                             *(self.heartbeat() for _ in range(5)))
        self.assertEqual(self.actual('solar'), 2900)
        self.assertEqual(self.writes, [('p0104', {native.SPEED_ATTR: '2900'})])

    def test_automation_preserves_triggers_and_routes_request_reason(self):
        config = json.loads((Path(__file__).parents[1] /
            'ha_automations/rpm_guardian_reconciliation.json').read_text())
        triggers = {t['id']: t for t in config['triggers']}
        self.assertEqual(triggers['accounting_rollover']['at'], '08:00:00')
        self.assertEqual(triggers['before_filtration']['at'], '23:59:00')
        self.assertEqual(triggers['recovery_heartbeat']['minutes'], '/1')
        self.assertEqual(triggers['startup']['event'], 'start')
        self.assertEqual(triggers['spa_session']['to'], 'heat')
        self.assertEqual(triggers['sanitation_request']['entity_id'],
            ['input_boolean.pool_sanitation_session', 'input_boolean.spa_sanitation_session'])
        self.assertEqual(config['actions'][0]['data']['reason'],
            "{{ trigger.id | default('manual', true) }}")
