"""Explicit manual heat-source selection; physical writes remain blocked."""
from homeassistant.components.select import SelectEntity

HEAT_SOURCES = {"Off": "00000", "Gas": "H0001", "Solar": "H0002"}

class ManualHeatSource(SelectEntity):
    _attr_options = list(HEAT_SOURCES)
    _attr_should_poll = False

    def __init__(self, entry, runtime, key, name, body_id):
        self._runtime = runtime
        self._body_id = body_id
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_manual_{key}_heat_source"
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
    def current_option(self):
        if self._observation is None or not self._observation.connected:
            return None
        body = self._observation.body(self._body_id)
        if body is None:
            return None
        return next((label for label, native in HEAT_SOURCES.items()
                     if native == body.heat_source), None)

    @property
    def available(self):
        return self.current_option is not None

    async def async_select_option(self, option):
        if option not in HEAT_SOURCES:
            raise ValueError("Unsupported heat source")
        await self._runtime.transport.set_heat_source(self._body_id, HEAT_SOURCES[option])

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        ManualHeatSource(entry, entry.runtime_data, "pool", "Pool Heat Source", "B1101"),
        ManualHeatSource(entry, entry.runtime_data, "spa", "Hot Tub Heat Source", "B1202"),
    ])
