# IntelliCenter entity migration readiness — 2026-10-08

**Audit only. No registry renames, command enablement, automation edits, or PoolOS removal authorized.**

## Scope and evidence

- Home Assistant registry search found **50** `poolos_native_intellicenter_*` entities.
- Configuration search found **21 automations** and **one dashboard** matching the legacy prefix. This is a prefix-level inventory, **not** a proven exhaustive per-entity dependency graph; HomeKit exposure, config-entry helpers, YAML dashboards and external consumers require separate review.
- New bridge currently has command delivery disabled. Candidate entity matches below do not establish identical native behavior, physical safety, or interchangeable automation semantics.
- New dashboard: `intellicenter-operations` (Overview / Manual Controls / Diagnostics), additive and read-only commissioning.

## Legacy to bridge candidate matrix

| Legacy PoolOS entity | Candidate bridge entity | Status |
|---|---|---|
| `binary_sensor.poolos_native_intellicenter_freeze_protection_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_heater_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_jets_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_pool_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_pool_command_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_pool_heating_demand` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_pool_light_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_slide_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_solar_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_solar_preferred` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_spa_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_spa_command_active` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_spa_heating_demand` | — | Gap / PoolOS-specific; retain |
| `binary_sensor.poolos_native_intellicenter_waterfall_active` | — | Gap / PoolOS-specific; retain |
| `climate.poolos_native_intellicenter_hot_tub_thermostat` | `climate.hot_tub_thermostat` | Candidate: parity and semantics to verify |
| `climate.poolos_native_intellicenter_pool_thermostat` | `climate.pool_thermostat` | Candidate: parity and semantics to verify |
| `light.poolos_native_intellicenter_pool_light` | `light.pool_light` | Candidate: parity and semantics to verify |
| `number.poolos_native_intellicenter_hot_tub_rpm` | — | Gap / PoolOS-specific; retain |
| `number.poolos_native_intellicenter_intellichlor_pool_output` | `number.intellichlor_pool_output` | Candidate: parity and semantics to verify |
| `number.poolos_native_intellicenter_intellichlor_spa_output` | `number.intellichlor_spa_output` | Candidate: parity and semantics to verify |
| `number.poolos_native_intellicenter_pool_rpm` | `number.pool_rpm` | Candidate: parity and semantics to verify |
| `select.poolos_native_intellicenter_hot_tub_heat_mode` | `select.hot_tub_heat_source` | Candidate: parity and semantics to verify |
| `select.poolos_native_intellicenter_pool_heat_mode` | `select.pool_heat_source` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_air_temperature` | `sensor.air_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_firmware_version` | `sensor.firmware_version` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_intellichlor_pool_output` | `sensor.intellichlor_pool_output` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_intellichlor_salt` | `sensor.intellichlor_salt` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_intellichlor_spa_output` | `sensor.intellichlor_spa_output` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pool_heat_mode_raw` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_pool_heater_id` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_pool_maximum_temperature` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_pool_target_temperature` | `sensor.pool_target_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pool_temperature` | `sensor.pool_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pump_flow_rate` | `sensor.pump_flow_rate` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pump_maximum_rpm` | `sensor.pump_maximum_rpm` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pump_minimum_rpm` | `sensor.pump_minimum_rpm` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pump_power` | `sensor.pump_power` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_pump_rpm` | `sensor.pump_rpm` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_solar_temperature` | `sensor.solar_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_spa_heat_mode_raw` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_spa_heater_id` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_spa_maximum_temperature` | — | Gap / PoolOS-specific; retain |
| `sensor.poolos_native_intellicenter_spa_target_temperature` | `sensor.spa_target_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_spa_temperature` | `sensor.spa_temperature` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_system_mode` | `sensor.system_mode` | Candidate: parity and semantics to verify |
| `sensor.poolos_native_intellicenter_water_temperature` | `sensor.water_temperature` | Candidate: parity and semantics to verify |
| `switch.poolos_native_intellicenter_jets_bubbles` | `switch.jets_bubbles` | Candidate: parity and semantics to verify |
| `switch.poolos_native_intellicenter_solar` | — | Gap / PoolOS-specific; retain |
| `switch.poolos_native_intellicenter_spillway` | `switch.spillway` | Candidate: parity and semantics to verify |
| `switch.poolos_native_intellicenter_water_slide` | `switch.water_slide` | Candidate: parity and semantics to verify |

## Blocking gaps / semantic mismatches

1. PoolOS ownership and autonomy concepts (solar-preferred, pool/spa command active, heating demand, freeze protection) cannot simply be replaced by an unowned manual bridge. Determine whether each remains needed after PoolOS retirement.
2. Separate Hot Tub RPM control is not implemented; one global pump RPM number is **not** a drop-in equivalent. Native pump command `PMP01` requires topology validation before any physical enablement.
3. Solar active and heater active observations, heater IDs, raw heat modes, maximum body temperatures, and PoolOS-specific feature state are not all independently represented.
4. IntelliBrite effect list is present but effect readback is not independently observed; no physical effect test has occurred.
5. Existing automation and dashboard references must be enumerated by exact entity ID before any rename. PoolOS remains the operational fallback; retain original registry IDs until rollback is fully designed.

## Config consumers found by HA prefix search

- Pool-light effect automations (American, Blue, Caribbean, Green, Party, Romance, Sunset, Royal, White, Magenta, Red, SAm) and the Pool Light daily/holiday schedule.
- Backyard Hue Sync ownership, Spa Gauge session/color, Pool/Spa ready notifications, safety interlocks, seasonal filtration commissioning, heat-mode alert.
- Existing `pool-os` dashboard.

## Next gates

1. Capture per-entity exact-ID references in automation/script/scene/helper/dashboard configuration, and review HomeKit/config-entry consumers separately.
2. Add missing observational entities with fail-closed tests, native provenance, and live parity checks.
3. Validate manual command protocol semantics without sending physical commands; establish explicit user-approved commissioning sequence.
4. Stage reversible entity registry mapping, preserve original IDs and backups, test one consumer class at a time.
5. Only after approved physical commissioning, enable commands under a reviewed authority/cutover plan.
