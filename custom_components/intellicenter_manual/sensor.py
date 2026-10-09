"""Read-only native IntelliCenter telemetry.

Names deliberately do not claim ownership of existing PoolOS entity IDs.
Registry migration is a separate, explicit commissioning operation.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

MEASUREMENTS = (
    ("air_temperature", "Air Temperature", "°F"),
    ("solar_temperature", "Solar Temperature", "°F"),
    ("water_temperature", "Water Temperature", "°F"),
    ("pump_rpm", "Pump RPM", "rpm"),
    ("pump_flow_rate", "Pump Flow Rate", "gal/min"),
    ("pump_power", "Pump Power", "W"),
    ("pump_minimum_rpm", "Pump Minimum RPM", "rpm"),
    ("pump_maximum_rpm", "Pump Maximum RPM", "rpm"),
    ("firmware_version", "Firmware Version", None),
    ("system_mode", "System Mode", None),
    ("pool_temperature", "Pool Temperature", "°F"),
    ("pool_target_temperature", "Pool Target Temperature", "°F"),
    ("spa_temperature", "Spa Temperature", "°F"),
    ("spa_target_temperature", "Spa Target Temperature", "°F"),
)

class NativeTelemetry(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, runtime, key, name, unit):
        self._runtime = runtime
        self._key = key
        self._observation = None
        self._unsubscribe = None
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_native_intellicenter_{key}"
        self._attr_native_unit_of_measurement = unit

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsubscribe = self._runtime.observation_fanout.subscribe(self._updated)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await super().async_will_remove_from_hass()

    def _updated(self, observation):
        self._observation = observation
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def native_value(self):
        obs = self._observation
        if obs is None or not obs.connected:
            return None
        if self._key.startswith(("pool_", "spa_")):
            body_id = "B1101" if self._key.startswith("pool_") else "B1202"
            body = obs.body(body_id)
            if body is None:
                return None
            if self._key.endswith("_target_temperature"):
                return body.target_temperature
            if self._key.endswith("_temperature"):
                return body.current_temperature
        return obs.measurement(self._key)

    @property
    def available(self):
        return self.native_value is not None

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(NativeTelemetry(entry, entry.runtime_data, *item)
                       for item in MEASUREMENTS)
