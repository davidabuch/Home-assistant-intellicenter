"""Explicit Pool and Spa manual thermostats; never automatically actuate."""
from __future__ import annotations
from typing import Any
from .observation import ReadObservation
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

BODIES = (("pool", "Pool Thermostat", "B1101"), ("hot_tub", "Hot Tub Thermostat", "B1202"))

class ManualBodyThermostat(ClimateEntity):
    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 40
    _attr_max_temp = 104
    _attr_target_temperature_step = 1
    _attr_should_poll = False

    def __init__(self, entry, transport, key, name, body_id):
        self._transport = transport
        self._body_id = body_id
        self._observation: ReadObservation | None = None
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_native_intellicenter_{key}_thermostat"

    def set_observation(self, observation: ReadObservation | None) -> None:
        self._observation = observation
        self.async_write_ha_state()

    def _body(self):
        if self._observation is None or not self._observation.connected:
            return None
        return self._observation.body(self._body_id)

    @property
    def available(self):
        body = self._body()
        return bool(body and body.active is not None and body.current_temperature is not None and body.target_temperature is not None)

    @property
    def hvac_mode(self):
        body = self._body()
        if body is None or body.active is None:
            return None
        return HVACMode.HEAT if body.active else HVACMode.OFF

    @property
    def hvac_action(self):
        body = self._body()
        if body is None or body.active is None:
            return None
        if not body.active:
            return HVACAction.OFF
        if body.heating is None:
            return None
        return HVACAction.HEATING if body.heating else HVACAction.IDLE

    @property
    def current_temperature(self):
        body = self._body()
        return None if body is None else body.current_temperature

    @property
    def target_temperature(self):
        body = self._body()
        return None if body is None else body.target_temperature

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode not in self.hvac_modes:
            raise ValueError("unsupported HVAC mode")
        await self._transport.set_body_active(self._body_id, hvac_mode == HVACMode.HEAT)

    async def async_set_temperature(self, **kwargs: Any):
        await self._transport.set_target(self._body_id, kwargs[ATTR_TEMPERATURE])

async def async_setup_entry(hass, entry, async_add_entities):
    transport = entry.runtime_data
    async_add_entities(
        ManualBodyThermostat(entry, transport, key, name, body_id)
        for key, name, body_id in BODIES
    )
