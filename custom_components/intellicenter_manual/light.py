"""Manual IntelliBrite Pool Light; commissioning commands remain blocked."""
from homeassistant.components.light import LightEntity

class ManualPoolLight(LightEntity):
    _attr_should_poll = False
    _attr_name = "Pool Light"
    def __init__(self, entry, runtime):
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_manual_pool_light"
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

    def _state(self):
        if self._observation is None or not self._observation.connected:
            return None
        circuit = self._observation.circuit("C0002")
        return circuit.active if circuit else None

    @property
    def available(self):
        return self._state() is not None

    @property
    def is_on(self):
        return self._state()

    async def async_turn_on(self, **kwargs):
        await self._runtime.transport.set_circuit("C0002", True)

    async def async_turn_off(self, **kwargs):
        await self._runtime.transport.set_circuit("C0002", False)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ManualPoolLight(entry, entry.runtime_data)])
