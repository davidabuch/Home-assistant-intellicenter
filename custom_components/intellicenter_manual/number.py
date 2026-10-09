"""Manual pump speed entity; physical commands blocked until commissioning."""
from homeassistant.components.number import NumberEntity

class ManualPumpRPM(NumberEntity):
    _attr_name = "Pool RPM"
    _attr_native_min_value = 600
    _attr_native_max_value = 3450
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "rpm"
    _attr_should_poll = False

    def __init__(self, entry, runtime):
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_manual_pool_rpm"
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
    def native_value(self):
        if self._observation is None or not self._observation.connected:
            return None
        return self._observation.measurement("pump_rpm")

    @property
    def available(self):
        return self.native_value is not None

    async def async_set_native_value(self, value):
        await self._runtime.transport.set_pump_rpm(value)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ManualPumpRPM(entry, entry.runtime_data)])
