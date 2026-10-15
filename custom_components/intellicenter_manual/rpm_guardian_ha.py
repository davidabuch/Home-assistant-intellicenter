"""HA adapter: storage, evidence and services for the request-driven Guardian."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from time import monotonic

from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event

from .rpm_guardian import Conditions, PROGRAMS, RPMGuardian, speed

DOMAIN = "intellicenter_manual"


class GuardianHA:
    def __init__(self, hass, entry, transport):
        self.hass, self.entry, self.transport = hass, entry, transport
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.rpm_guardian")
        self.listeners = set()
        self.ready_at = monotonic() + 60
        self.revision = 'development'
        self.core = RPMGuardian(self.read, self.write, self.conditions,
                                self.store.async_save, notify=self.publish)

    def subscribe(self, callback):
        self.listeners.add(callback)
        return lambda: self.listeners.discard(callback)

    def publish(self):
        for callback in tuple(self.listeners): callback()

    def state(self, entity):
        s = self.hass.states.get(entity)
        return None if s is None else s.state

    def boolean(self, entity):
        return {"on": True, "off": False}.get(self.state(entity))

    def seconds(self, entity):
        s = self.hass.states.get(entity)
        if s is None or s.state in {"unknown", "unavailable"}: return 0
        return max(0, (datetime.now(timezone.utc) - s.last_changed).total_seconds())

    def numeric(self, entity):
        try:
            n = float(self.state(entity))
            return n if math.isfinite(n) else None
        except (TypeError, ValueError): return None

    def conditions(self):
        real = self.boolean("input_boolean.grid_outage_use_real_sensor")
        raw_entity = ("binary_sensor.1_powerwall_grid_status" if real is True
                      else "input_boolean.grid_outage_simulation")
        raw = self.boolean(raw_entity) if real is not None else None
        raw_outage = (not raw if real else raw) if raw is not None else None
        qualified = self.boolean("input_boolean.grid_outage_active")
        observation = self.transport.read_observation()
        pool = observation.body('B1101') if observation.connected else None
        spa = observation.body('B1202') if observation.connected else None
        def circuit_off(object_id):
            circuit = observation.circuit(object_id) if observation.connected and object_id else None
            return circuit is not None and circuit.active is False
        settled_seconds = self.core.data["settling_seconds"]
        stable = all(self.seconds(e) >= settled_seconds for e in (
            "sensor.pump_rpm", "climate.pool_thermostat", "binary_sensor.solar_heating_active"))
        # Retain a conservative gas cooldown before lowering running Pool flow.
        stable = stable and self.seconds("binary_sensor.gas_heater_active") >= max(300, settled_seconds)
        minimum, maximum = self.numeric("sensor.pump_minimum_rpm"), self.numeric("sensor.pump_maximum_rpm")
        return Conditions(
            fresh=observation.connected and monotonic() >= self.ready_at,
            qualified=qualified, raw_outage=raw_outage,
            restored=(raw_outage is False and qualified is False and self.seconds(raw_entity) >= 120),
            protection=self.boolean("input_boolean.grid_outage_protection"),
            bypass=self.boolean("input_boolean.grid_outage_operator_bypass_latch"),
            authority=(self.boolean("input_boolean.pool_automatic_ownership") is True),
            freeze_off=observation.connected and observation.freeze_active is False,
            automatic_mode=observation.connected and observation.measurement('system_mode') == 'AUTO',
            pool=None if pool is None else pool.active,
            spa_off=spa is not None and spa.active is False,
            sanitation_off=circuit_off(self.transport.sanitation_circuit_id()) and all(
                self.boolean(e) is False for e in (
                "input_boolean.pool_sanitation_session", "input_boolean.spa_sanitation_session")),
            heat_off=observation.connected and all(observation.heating_source_active(e) is False
                for e in ('H0001', 'H0002')),
            sources_off=(pool is not None and spa is not None
                         and pool.heat_source == '00000' and spa.heat_source == '00000'),
            accessories_off=all(circuit_off(e) for e in ('C0004', 'C0003', 'FTR01')),
            settled=stable, actual_rpm=observation.measurement('pump_rpm') if observation.connected else None,
            minimum=int(minimum) if minimum is not None else 3450,
            maximum=int(maximum) if maximum is not None else 600,
        )

    def read(self, key):
        obj = self.transport._verified_pump_program(PROGRAMS[key][0])
        return speed(float(obj.properties.get("SPEED")))

    async def write(self, object_id, value, permit):
        await self.transport.set_configured_pump_program_rpm(object_id, value, authority=permit)

    async def reconcile(self, reason):
        blocked = self.core.blocks_normal
        result = await self.core.reconcile(reason)
        if blocked and not self.core.blocks_normal:
            # Current demand is reevaluated by the existing HA controller.
            # There is no stored pre-outage ON/OFF command to replay.
            self.hass.bus.async_fire("intellicenter_rpm_guardian_restored")
        return result

    async def preflight(self, key):
        await self.reconcile(f"{key}_requested")
        observed = self.read(key)
        if observed < self.core.data["floors"][key]:
            raise RuntimeError(f"{key} preset below approved flow floor; Apply/reconcile before starting")

    async def setup(self):
        def installed_revision():
            import json
            from pathlib import Path
            path = Path(__file__).with_name('build_revision.json')
            return json.loads(path.read_text()).get('commit', 'unknown') if path.exists() else 'development'
        self.revision = await self.hass.async_add_executor_job(installed_revision)
        try:
            await self.core.load(await self.store.async_load())
        except Exception as exc:
            await self.core.load({'version': 'unreadable'})
            self.core.data['failure'] = f'Durable storage unavailable: {exc}'
        self.transport.set_preset_policy_check(self.core.permitted)
        self.transport.set_control_policy_check(self.core.ordinary_command_allowed)

        def authority_changed(event):
            old, new = event.data.get('old_state'), event.data.get('new_state')
            if old is None or new is None or old.state != new.state:
                self.core.invalidate_authority()
        self.entry.async_on_unload(async_track_state_change_event(self.hass, [
            'input_boolean.pool_automatic_ownership', 'input_boolean.grid_outage_active',
            'input_boolean.grid_outage_protection', 'input_boolean.grid_outage_operator_bypass_latch',
            'input_boolean.grid_outage_use_real_sensor', 'input_boolean.grid_outage_simulation',
            'binary_sensor.1_powerwall_grid_status'], authority_changed))

        def require_entry(call):
            if call.data.get("entry_id") != self.entry.entry_id:
                raise ValueError("Exact config entry ID required")

        async def reconcile(call):
            require_entry(call)
            await self.reconcile(str(call.data.get("reason", "manual")))

        async def apply(call):
            require_entry(call)
            await self.core.apply()

        async def configure(call):
            require_entry(call)
            if call.data.get("confirm") != "AUTHORIZE_RPM_GUARDIAN_COMMISSIONING":
                raise ValueError("Explicit supervised RPM commissioning authorization required")
            sample = self.conditions()
            if not sample.fresh or sample.raw_outage is not False or sample.qualified is not False:
                raise RuntimeError("End simulation/outage and establish fresh normal baseline first")
            async with self.core.lock:
                floors = dict(self.core.data['floors'])
                value = int(call.data.get('settling_seconds', self.core.data['settling_seconds']))
                if not 180 <= value <= 900: raise ValueError("Settling interval must be 180..900 seconds")
                for key, floor in call.data.get('minimums', {}).items():
                    if key not in floors: raise ValueError("Unknown flow floor")
                    floors[key] = speed(floor, sample.minimum, sample.maximum)
                self.core.data['floors'] = floors
                self.core.data['settling_seconds'] = value
                await self.core.persist()
            await self.core.enable(call.data.get("enabled") is True,
                running_pool_approved=call.data.get("approve_running_pool_write") is True)

        for name, handler in (("reconcile_pump_speeds", reconcile),
                              ("apply_rpm_configuration", apply),
                              ("configure_rpm_guardian", configure)):
            self.hass.services.async_register(DOMAIN, name, handler)
            self.entry.async_on_unload(lambda n=name: self.hass.services.async_remove(DOMAIN, n))
