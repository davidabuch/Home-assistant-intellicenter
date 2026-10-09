"""Read-only native IntelliCenter circuit and body status entities."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

DESCRIPTIONS = (
    ("native_observation_fresh", "Native Observation Fresh", "health", "native"),
    ("pool_active", "Pool Active", "body", "B1101"),
    ("freeze_protection_active", "Freeze Protection Active", "freeze", "_FEA2"),
    ("spa_active", "Spa Active", "body", "B1202"),
    ("pool_heating_active", "Pool Heating Active", "body_heating", "B1101"),
    ("spa_heating_active", "Spa Heating Active", "body_heating", "B1202"),
    ("gas_heater_active", "Gas Heater Active", "heat_source", "H0001"),
    ("solar_heating_active", "Solar Heating Active", "heat_source", "H0002"),
    ("pool_light_active", "Pool Light Active", "circuit", "C0002"),
    ("jets_active", "Jets Active", "circuit", "C0003"),
    ("slide_active", "Slide Active", "circuit", "C0004"),
    ("waterfall_active", "Waterfall Active", "circuit", "FTR01"),
)

class NativeStatus(BinarySensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, runtime, key, name, kind, native_id):
        self._runtime = runtime
        self._kind = kind
        self._native_id = native_id
        self._observation = None
        self._unsubscribe = None
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_native_intellicenter_{key}"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsubscribe = self._runtime.observation_fanout.subscribe(self._updated)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        await super().async_will_remove_from_hass()

    def _updated(self, observation):
        self._observation = observation
        if self.hass is not None:
            self.async_write_ha_state()

    def _value(self):
        if self._observation is None:
            return None
        if self._kind == "health":
            return self._observation.connected
        if not self._observation.connected:
            return None
        if self._kind == "freeze":
            return self._observation.freeze_active
        if self._kind == "heat_source":
            return self._observation.heating_source_active(self._native_id)
        item = (self._observation.body(self._native_id)
                if self._kind in {"body", "body_heating"}
                else self._observation.circuit(self._native_id))
        if item is None:
            return None
        return item.heating if self._kind == "body_heating" else item.active

    @property
    def available(self):
        return self._value() is not None

    @property
    def is_on(self):
        return self._value()

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(NativeStatus(entry, entry.runtime_data, *description)
                       for description in DESCRIPTIONS)
