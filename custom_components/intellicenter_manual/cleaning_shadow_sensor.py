"""Optional passive diagnostics; never change the commissioned Stage A sensor."""
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event

from .cleaning_observer import Frame
from .cleaning_sensor import POLICY, CONTEXT
from .cleaning_shadow import CleaningShadow


class CleaningShadowSensor(SensorEntity):
    """Default-disabled diagnostic entity; shadow arbitration also defaults OFF.

    Enabling the diagnostic entity permits passive subscriptions only. No HA
    option or service enables arbitration/actuation. No source of dispatch ACK
    or exclusive/manual-intent attestation exists in this adapter.
    """

    _attr_name = 'Pool Cleaning Shadow Evidence'
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry):
        self._runtime = entry.runtime_data
        self._attr_unique_id = f'{entry.entry_id}_pool_cleaning_shadow_evidence'
        self._shadow = CleaningShadow()  # Always OFF, including reload/restart.
        self._observation = None
        self._attributes = {'shadow_enabled': False, 'command_authority': False}
        self._key = None
        self._unsubscribers = []

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        try:
            self._unsubscribers.append(self._runtime.observation_fanout.subscribe(self._updated))
            self._unsubscribers.append(async_track_state_change_event(
                self.hass, tuple(POLICY) + CONTEXT, self._policy_changed))
            self._unsubscribers.append(self.hass.bus.async_listen('call_service', self._service_intent))
        except Exception:
            self._unsubscribe()
            raise

    def _unsubscribe(self):
        for remove in self._unsubscribers:
            remove()
        self._unsubscribers.clear()

    async def async_will_remove_from_hass(self):
        self._unsubscribe()
        await super().async_will_remove_from_hass()

    @callback
    def _service_intent(self, event):
        data = event.data
        if data.get('domain') != 'climate':
            return
        service = data.get('service')
        if service not in ('set_hvac_mode', 'turn_on', 'turn_off'):
            return
        service_data = data.get('service_data') or {}
        targets = service_data.get('entity_id', [])
        targets = [targets] if isinstance(targets, str) else targets
        # Area/device targets cannot be resolved to Pool from this event alone.
        if not isinstance(targets, (list, tuple)) or 'climate.pool_thermostat' not in targets:
            return
        mode = service_data.get('hvac_mode') if service == 'set_hvac_mode' else (
            'heat' if service == 'turn_on' else 'off')
        if mode not in ('heat', 'off'):
            return
        self._shadow.pool_service_intent(active=mode == 'heat', at=datetime.now(timezone.utc))
        if self._observation is not None:
            self._updated(self._observation)

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
        blockers = []
        for key in tuple(POLICY) + CONTEXT:
            state = self.hass.states.get(key)
            context[key] = None if state is None else state.state
        for key, (expected, reason) in POLICY.items():
            if context[key] != expected:
                blockers.append('unknown_policy' if context[key] in (None, 'unknown', 'unavailable') else reason)
        if observation.freeze_active is not False:
            blockers.append('freeze_authority')
        if observation.measurement('system_mode') != 'AUTO':
            blockers.append('service_mode')
        identity = self._runtime.transport.pool_cleaning_circuit_id()
        cleaning = observation.circuit(identity) if identity else None
        pool, spa = observation.body('B1101'), observation.body('B1202')
        frame = Frame(observation.observed_at, identity,
                      None if cleaning is None else cleaning.active,
                      None if pool is None else pool.active, None if spa is None else spa.active,
                      observation.connected, tuple(dict.fromkeys(blockers)))
        decision = self._shadow.observe(frame, now=datetime.now(timezone.utc),
                                        pump_rpm=observation.measurement('pump_rpm'))
        key = (decision, self._shadow.revision, frame.blockers, frame.pool, frame.spa)
        if key == self._key:
            return
        self._key = key
        self._attributes = {**self._shadow.diagnostics(decision),
                            'suppression_reasons': list(frame.blockers),
                            'native_evidence_scope': 'global_model_snapshots',
                            'controller_context_at_decision': context}
        self.async_write_ha_state()

    @property
    def native_value(self):
        return 'disabled'

    @property
    def extra_state_attributes(self):
        return self._attributes
