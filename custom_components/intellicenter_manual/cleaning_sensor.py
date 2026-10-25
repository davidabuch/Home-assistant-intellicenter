"""Read-only Stage A cleaning proposals, isolated from all control paths."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from .cleaning_observer import CleaningObserver, Frame

# Conservative observation-only eligibility. These do not replace dispatch-time
# transport guards or the scheduler's own checks. Missing policy is suppression.
POLICY = {
    'input_boolean.pool_automatic_ownership': ('on', 'automatic_ownership_off'),
    'input_boolean.grid_outage_active': ('off', 'grid_authority'),
    'input_boolean.pool_sanitation_session': ('off', 'sanitation_priority'),
    'input_boolean.spa_sanitation_session': ('off', 'sanitation_priority'),
    'switch.sanitation': ('off', 'sanitation_priority'),
    'binary_sensor.rpm_guardian_blocks_normal_control': ('off', 'guardian_interlock'),
    'sensor.intellicenter_rpm_guardian': ('NORMAL', 'guardian_not_normal'),
    'switch.water_slide': ('off', 'auxiliary_demand'),
    'switch.spillway': ('off', 'auxiliary_demand'),
    'switch.jets_bubbles': ('off', 'auxiliary_demand'),
}
CONTEXT = (
    'input_boolean.pool_simple_schedule_owns_pool',
    'input_boolean.pool_simple_manual_circulation',
    'input_select.pool_heating_preference',
    'sensor.pool_temperature', 'sensor.pool_target_temperature',
    'sensor.solar_temperature', 'binary_sensor.solar_delivery_confirmed',
    'counter.pool_simple_filtration_minutes', 'sensor.pool_daily_filtration_target',
)


class CleaningObservationSensor(SensorEntity):
    """No controls, persisted claims or HA event emission."""

    _attr_name = 'Pool Cleaning Observer'
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry):
        self._runtime = entry.runtime_data
        self._attr_unique_id = f'{entry.entry_id}_pool_cleaning_observer'
        self._observer = CleaningObserver()
        self._proposal = None
        self._observation = None
        self._attributes = {'stage': 'A_observation_only', 'command_authority': False}
        self._unsubscribers = []
        self._decision_key = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Subscribe is immediate; initialize every field before registration.
        self._unsubscribers.append(
            self._runtime.observation_fanout.subscribe(self._updated))
        self._unsubscribers.append(async_track_state_change_event(
            self.hass, tuple(POLICY) + CONTEXT, self._policy_changed))

    async def async_will_remove_from_hass(self):
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        await super().async_will_remove_from_hass()

    @callback
    def _policy_changed(self, _event):
        if self._observation is not None:
            self._updated(self._observation)

    @callback
    def _updated(self, observation):
        self._observation = observation
        if self.hass is None:
            return
        context = {}
        for entity_id in tuple(POLICY) + CONTEXT:
            state = self.hass.states.get(entity_id)
            context[entity_id] = None if state is None else state.state
        blockers = []
        for entity_id, (expected, reason) in POLICY.items():
            value = context[entity_id]
            if value != expected:
                blockers.append('unknown_policy' if value in (None, 'unknown', 'unavailable') else reason)
        if observation.freeze_active is not False:
            blockers.append('freeze_authority')
        if observation.measurement('system_mode') != 'AUTO':
            blockers.append('service_mode')
        cleaning_id = self._runtime.transport.pool_cleaning_circuit_id()
        cleaning = observation.circuit(cleaning_id) if cleaning_id else None
        pool, spa = observation.body('B1101'), observation.body('B1202')
        frame = Frame(observation.observed_at, cleaning_id,
                      None if cleaning is None else cleaning.active,
                      None if pool is None else pool.active,
                      None if spa is None else spa.active,
                      observation.connected, tuple(dict.fromkeys(blockers)))
        self._proposal = self._observer.observe(frame, now=datetime.now(timezone.utc))
        # Publish on decision/authority changes, not every native timestamp or
        # motor RPM sample. Existing telemetry entities own continuous telemetry.
        decision_key = (self._proposal, frame.cleaning_id, frame.cleaning, frame.pool,
                        frame.spa, frame.blockers, tuple(context[key] for key in CONTEXT[:3]))
        if decision_key == self._decision_key:
            return
        self._decision_key = decision_key
        self._attributes = {
            **asdict(self._proposal), 'stage': 'A_observation_only',
            'command_authority': False,
            'release_evidence_scope': 'distinct_native_snapshots_not_per_circuit_acknowledgments',
            'native_observed_at': observation.observed_at.isoformat(),
            'native_cleaning_id': cleaning_id, 'cleaning_active': frame.cleaning,
            'pool_active': frame.pool, 'spa_active': frame.spa,
            'pump_rpm_at_decision': observation.measurement('pump_rpm'),
            'confirmed_solar_delivery': observation.solar_delivery_confirmed(),
            'suppression_reasons': list(frame.blockers),
            'controller_context_at_decision': context,
            'handoff_authority': 'existing_HA_solar_filtration_controller',
        }
        self.async_write_ha_state()

    @property
    def native_value(self):
        return 'not_observed' if self._proposal is None else self._proposal.phase

    @property
    def extra_state_attributes(self):
        return self._attributes
