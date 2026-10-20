"""Read-only native IntelliCenter telemetry.

Names deliberately do not claim ownership of existing PoolOS entity IDs.
Registry migration is a separate, explicit commissioning operation.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from datetime import datetime, timezone

MEASUREMENTS = (
    ("native_observation_age", "Native Observation Age", "s"),
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
    ("intellichlor_pool_output", "IntelliChlor Pool Output", "%"),
    ("intellichlor_spa_output", "IntelliChlor Spa Output", "%"),
    ("intellichlor_salt", "IntelliChlor Salt", "ppm"),
    ("pool_temperature", "Pool Temperature", "°F"),
    ("pool_target_temperature", "Pool Target Temperature", "°F"),
    ("spa_temperature", "Spa Temperature", "°F"),
    ("spa_target_temperature", "Spa Target Temperature", "°F"),
    ("pool_heater_id", "Pool Heater ID", None),
    ("spa_heater_id", "Spa Heater ID", None),
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
        if self._key == "native_observation_age":
            if obs is None or not obs.connected:
                return None
            return max(0, round((datetime.now(timezone.utc) - obs.observed_at).total_seconds(), 1))
        if obs is None or not obs.connected:
            return None
        if self._key.startswith(("pool_", "spa_")):
            body_id = "B1101" if self._key.startswith("pool_") else "B1202"
            body = obs.body(body_id)
            if body is None:
                return None
            if self._key.endswith("_heater_id"):
                return body.heat_source
            if self._key.endswith("_target_temperature"):
                return body.target_temperature
            if self._key.endswith("_temperature"):
                return body.current_temperature
        return obs.measurement(self._key)

    @property
    def available(self):
        return self.native_value is not None

async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(NativeTelemetry(entry, runtime, *item)
                       for item in MEASUREMENTS)
    async_add_entities([GuardianStatus(entry)])

    # Discover by stable native identity, never by current active pump speed.
    # Refresh discovery on each native observation to handle late model arrival.
    created = set()
    def discover(_observation):
        if not runtime.transport.connected:
            return
        programs = list(runtime.transport.model.get_by_type(PMPCIRC_TYPE))
        new_ids = sorted({str(obj.objnam) for obj in programs} - created)
        if not new_ids:
            return
        created.update(new_ids)
        async_add_entities(NativePumpCircuitSpeed(entry, runtime, object_id)
                           for object_id in new_ids)
    unsubscribe = runtime.observation_fanout.subscribe(discover)
    entry.async_on_unload(unsubscribe)


# Native pump-program settings are persistent IntelliCenter configuration, not
# instantaneous motor RPM. Keep these entities read-only during commissioning.
# Protocol attribute identifiers; avoid requiring pyintellicenter at sensor
# module import time (HA supplies the library to the integration runtime).
PMPCIRC_TYPE = "PMPCIRC"
PARENT_ATTR = "PARENT"
CIRCUIT_ATTR = "CIRCUIT"
SELECT_ATTR = "SELECT"
SPEED_ATTR = "SPEED"
GPM_ATTR = "GPM"

class NativePumpCircuitSpeed(SensorEntity):
    """One read-only Pentair PMPCIRC configuration assignment."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, runtime, object_id):
        self._runtime = runtime
        self._object_id = object_id
        self._unsubscribe = None
        self._attr_unique_id = f"{entry.entry_id}_native_pump_program_{object_id}"
        self._attr_name = f"IntelliCenter Pump Program {object_id}"
        self._attr_native_unit_of_measurement = "rpm"

    def _program(self):
        if not self._runtime.transport.connected:
            return None
        matches = [obj for obj in self._runtime.transport.model.get_by_type(PMPCIRC_TYPE)
                   if str(obj.objnam) == self._object_id]
        return matches[0] if len(matches) == 1 else None

    @property
    def native_value(self):
        obj = self._program()
        if obj is None or str(obj.properties.get(SELECT_ATTR) or "").upper() != "RPM":
            return None
        try:
            value = float(obj.properties.get(SPEED_ATTR))
            return int(value) if value.is_integer() and value > 0 else None
        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def available(self):
        return self.native_value is not None

    @property
    def extra_state_attributes(self):
        obj = self._program()
        if obj is None:
            return {}
        model = self._runtime.transport.model
        circuit_id = str(obj.properties.get(CIRCUIT_ATTR) or "")
        parent_id = str(obj.properties.get(PARENT_ATTR) or "")
        circuit = model[circuit_id] if circuit_id else None
        pump = model[parent_id] if parent_id else None
        return {
            "native_pmpcirc_id": self._object_id,
            "circuit_id": circuit_id,
            "circuit_name": None if circuit is None else circuit.sname,
            "pump_id": parent_id,
            "pump_name": None if pump is None else pump.sname,
            "control_mode": obj.properties.get(SELECT_ATTR),
            "configured_rpm": obj.properties.get(SPEED_ATTR),
            "configured_gpm": obj.properties.get(GPM_ATTR),
            "source": "intellicenter_native_configuration",
            "writable": False,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsubscribe = self._runtime.observation_fanout.subscribe(self._updated)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await super().async_will_remove_from_hass()

    def _updated(self, observation):
        if self.hass is not None:
            self.async_write_ha_state()


class GuardianStatus(SensorEntity):
    _attr_name = "IntelliCenter RPM Guardian"
    _attr_should_poll = False

    def __init__(self, entry):
        self._guardian = entry.runtime_data.guardian
        self._attr_unique_id = f"{entry.entry_id}_rpm_guardian_status"
        self._unsubscribe = None

    @property
    def native_value(self):
        data = self._guardian.core.data
        return data['state'] if data['enabled'] or data['restoration_pending'] else 'DISARMED'

    @property
    def extra_state_attributes(self):
        from copy import deepcopy
        data = deepcopy(self._guardian.core.data)
        data['pending_configuration_changes'] = {
            key: value for key, value in data['draft'].items()
            if value != data['applied'][key]}
        data['blocks_normal_control'] = self._guardian.core.blocks_normal
        data['installed_commit'] = self._guardian.revision
        data['runtime_status_scope'] = 'outage_only; not normal Solar verification'
        data['pump_demand'] = self._guardian.demand_diagnostics()
        return data

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsubscribe = self._guardian.subscribe(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe: self._unsubscribe()
        await super().async_will_remove_from_hass()

