"""Explicit Pool and Spa manual thermostats; never automatically actuate."""
from __future__ import annotations
from typing import Any
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
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_native_intellicenter_{key}_thermostat"

    @property
    def available(self):
        # Never claim availability until live model observation is commissioned.
        return False

    @property
    def hvac_mode(self):
        return None

    @property
    def hvac_action(self):
        return None

    @property
    def current_temperature(self):
        return None

    @property
    def target_temperature(self):
        return None

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
