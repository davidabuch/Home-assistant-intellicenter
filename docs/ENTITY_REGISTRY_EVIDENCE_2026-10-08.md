# HA entity-registry evidence — 2026-10-08

Read-only snapshot. **Not** an authority or registry migration authorization.

## Identity
Legacy integration `poolos`, entry `01KZFCZGEM54HNEX7652JZFXYA`, common device `7001d4a65bcea3f5fa5dc6a3d547d419`. All 50 registered legacy entities were enabled and visible when queried. New read-only bridge platform `intellicenter_manual`, entry `01M4F1DFGA4AH4F9E9M7MJCR5Q`; six checked counterparts have null device_id, are enabled and visible. Stable unique IDs differ; **do not attempt entity-ID swaps**.

## Six HomeKit control-path identity pairs
| Legacy ID | New ID | Legacy unique_id | New unique_id |
|---|---|---|---|
| `climate.poolos_native_intellicenter_pool_thermostat` | `climate.pool_thermostat` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_thermostat` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_native_intellicenter_pool_thermostat` |
| `climate.poolos_native_intellicenter_hot_tub_thermostat` | `climate.hot_tub_thermostat` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_thermostat` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_native_intellicenter_spa_thermostat` |
| `light.poolos_native_intellicenter_pool_light` | `light.pool_light` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_light` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_manual_pool_light` |
| `switch.poolos_native_intellicenter_spillway` | `switch.spillway` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_waterfall_switch` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_manual_spillway` |
| `switch.poolos_native_intellicenter_jets_bubbles` | `switch.jets_bubbles` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_jets_switch` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_manual_jets_bubbles` |
| `switch.poolos_native_intellicenter_water_slide` | `switch.water_slide` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_slide_switch` | `01M4F1DFGA4AH4F9E9M7MJCR5Q_manual_water_slide` |

## All 50 legacy registered entities
| Entity ID | Unique ID | Enabled | Visibility |
|---|---|---|---|
| `binary_sensor.poolos_native_intellicenter_freeze_protection_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_freeze_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_heater_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_heater_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_jets_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_jets_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_pool_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_pool_command_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_command_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_pool_heating_demand` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_heating_demand_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_pool_light_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_light_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_slide_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_slide_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_solar_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_solar_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_solar_preferred` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_solar_preferred_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_spa_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_spa_command_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_command_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_spa_heating_demand` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_heating_demand_active` | enabled | visible |
| `binary_sensor.poolos_native_intellicenter_waterfall_active` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_waterfall_active` | enabled | visible |
| `climate.poolos_native_intellicenter_hot_tub_thermostat` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_thermostat` | enabled | visible |
| `climate.poolos_native_intellicenter_pool_thermostat` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_thermostat` | enabled | visible |
| `light.poolos_native_intellicenter_pool_light` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_light` | enabled | visible |
| `number.poolos_native_intellicenter_hot_tub_rpm` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_hot_tub_rpm` | enabled | visible |
| `number.poolos_native_intellicenter_intellichlor_pool_output` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellichlor_pool_output` | enabled | visible |
| `number.poolos_native_intellicenter_intellichlor_spa_output` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellichlor_spa_output` | enabled | visible |
| `number.poolos_native_intellicenter_pool_rpm` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_rpm` | enabled | visible |
| `select.poolos_native_intellicenter_hot_tub_heat_mode` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_hot_tub_heat_mode` | enabled | visible |
| `select.poolos_native_intellicenter_pool_heat_mode` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_heat_mode` | enabled | visible |
| `sensor.poolos_native_intellicenter_air_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_air_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_firmware_version` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellicenter_firmware_version` | enabled | visible |
| `sensor.poolos_native_intellicenter_intellichlor_pool_output` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellichlor_pool_output_percent` | enabled | visible |
| `sensor.poolos_native_intellicenter_intellichlor_salt` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellichlor_salt_ppm` | enabled | visible |
| `sensor.poolos_native_intellicenter_intellichlor_spa_output` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellichlor_spa_output_percent` | enabled | visible |
| `sensor.poolos_native_intellicenter_pool_heat_mode_raw` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_raw_htmode` | enabled | visible |
| `sensor.poolos_native_intellicenter_pool_heater_id` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_raw_heater_id` | enabled | visible |
| `sensor.poolos_native_intellicenter_pool_maximum_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_maximum_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_pool_target_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_target_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_pool_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_pump_flow_rate` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pump_gpm` | enabled | visible |
| `sensor.poolos_native_intellicenter_pump_maximum_rpm` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pump_maximum_rpm` | enabled | visible |
| `sensor.poolos_native_intellicenter_pump_minimum_rpm` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pump_minimum_rpm` | enabled | visible |
| `sensor.poolos_native_intellicenter_pump_power` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pump_power` | enabled | visible |
| `sensor.poolos_native_intellicenter_pump_rpm` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pump_rpm` | enabled | visible |
| `sensor.poolos_native_intellicenter_solar_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_solar_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_spa_heat_mode_raw` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_raw_htmode` | enabled | visible |
| `sensor.poolos_native_intellicenter_spa_heater_id` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_raw_heater_id` | enabled | visible |
| `sensor.poolos_native_intellicenter_spa_maximum_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_maximum_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_spa_target_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_target_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_spa_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_spa_temperature` | enabled | visible |
| `sensor.poolos_native_intellicenter_system_mode` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_intellicenter_system_mode` | enabled | visible |
| `sensor.poolos_native_intellicenter_water_temperature` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_water_temperature` | enabled | visible |
| `switch.poolos_native_intellicenter_jets_bubbles` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_jets_switch` | enabled | visible |
| `switch.poolos_native_intellicenter_solar` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_pool_solar_switch` | enabled | visible |
| `switch.poolos_native_intellicenter_spillway` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_waterfall_switch` | enabled | visible |
| `switch.poolos_native_intellicenter_water_slide` | `01KZFCZGEM54HNEX7652JZFXYA_native_intellicenter_slide_switch` | enabled | visible |

## Exposure and consumers
The HomeKit `HASS Bridge PoolOS:21070` entry `01M0P7VFT1Q7YGK9FCXYMEGRRZ` explicitly includes the six legacy PoolOS control entities plus 12 pool-light effect input buttons. Both legacy thermostats additionally have `conversation.should_expose=true`; Alexa exposure is false. The six new bridge entities inspected have conversation and Alexa exposure false. HomeKit bridge filtering is distinct from voice-assistant exposure.

Configuration search previously found 21 automations and two dashboards referring to legacy prefix. In particular, Pool Light schedules and effect helpers, Hue Backyard Sync/Spa Gauge, and Spillway/Jets safety interlocks depend on legacy semantics or writable control.

## Reversible sequence (design only)
1. Preserve all 50 legacy IDs and unique IDs, 18 HomeKit-exposed entities, and PoolOS control authority; snapshot HA backup and HomeKit bridge options/pairing before future changes.
2. Map all 50 by **function**, not by similar display name. Classify observation-only, command, policy, interlock, lighting ownership, and HomeKit. No forced one-to-one mapping for PoolOS-only policy entities.
3. Run offline consumer regression tests and shadow observation, then obtain explicit approval for separate command commissioning and single-writer handoff.
4. Stage a controlled per-consumer migration with exact rollback to legacy entity IDs and HomeKit bridge. Never have simultaneous writers.
5. Verify physical safety interlocks, Spa Gauge, lighting scenes, notification semantics, native Solar vs Solar Preferred, and HomeKit identity after each approved phase.
6. Stop on stale truth, unknown heat mode, unsafe interlock, lost HomeKit pairing, registry collision, or unexpected actuation.

**No registry changes performed.** This registry snapshot is evidence, not a full backup of HA storage, Apple Home pairing, or external consumer configuration.
