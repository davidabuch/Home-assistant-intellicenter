"""Explicit manual accessory controls, hard-disabled during read-only commissioning."""
from homeassistant.components.switch import SwitchEntity

ACCESSORIES = (
    ("jets_bubbles", "Jets / Bubbles", "C0003"),
    ("water_slide", "Water Slide", "C0004"),
    ("spillway", "Spillway", "FTR01"),
)

class ManualAccessory(SwitchEntity):
    _attr_should_poll = False
    def __init__(self, entry, runtime, key, name, circuit_id):
        self._runtime = runtime
        self._circuit_id = circuit_id
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_manual_{key}"
        self._observation = None
        self._unsubscribe = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsubscribe = self._runtime.observation_fanout.subscribe(self._updated)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe:
            self._unsubscribe()
        await super().async_will_remove_from_hass()

    def _updated(self, observation):
        self._observation = observation
        self.async_write_ha_state()

    @property
    def available(self):
        return self._state() is not None

    def _state(self):
        if self._observation is None or not self._observation.connected:
            return None
        circuit = self._observation.circuit(self._circuit_id)
        return circuit.active if circuit else None

    @property
    def is_on(self):
        return self._state()

    async def async_turn_on(self, **kwargs):
        await self._runtime.transport.set_circuit(self._circuit_id, True)

    async def async_turn_off(self, **kwargs):
        await self._runtime.transport.set_circuit(self._circuit_id, False)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ManualAccessory(entry, entry.runtime_data, *row) for row in ACCESSORIES)
