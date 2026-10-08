# Existing native IntelliCenter entity IDs (read-only inventory)

Captured from live HA entity search on 2026-10-08. Preserve exact IDs through registry-aware migration; these are not proof of unique-ID equivalence.

- `binary_sensor.poolos_native_intellicenter_freeze_protection_active`
- `binary_sensor.poolos_native_intellicenter_heater_active`
- `binary_sensor.poolos_native_intellicenter_jets_active`
- `binary_sensor.poolos_native_intellicenter_pool_active`
- `binary_sensor.poolos_native_intellicenter_pool_command_active`
- `binary_sensor.poolos_native_intellicenter_pool_heating_demand`
- `binary_sensor.poolos_native_intellicenter_pool_light_active`
- `binary_sensor.poolos_native_intellicenter_slide_active`
- `binary_sensor.poolos_native_intellicenter_solar_active`
- `binary_sensor.poolos_native_intellicenter_solar_preferred`
- `binary_sensor.poolos_native_intellicenter_spa_active`
- `binary_sensor.poolos_native_intellicenter_spa_command_active`
- `binary_sensor.poolos_native_intellicenter_spa_heating_demand`
- `binary_sensor.poolos_native_intellicenter_waterfall_active`
- `climate.poolos_native_intellicenter_hot_tub_thermostat`
- `climate.poolos_native_intellicenter_pool_thermostat`
- `light.poolos_native_intellicenter_pool_light`
- `number.poolos_native_intellicenter_hot_tub_rpm`
- `number.poolos_native_intellicenter_intellichlor_pool_output`
- `number.poolos_native_intellicenter_intellichlor_spa_output`
- `number.poolos_native_intellicenter_pool_rpm`
- `select.poolos_native_intellicenter_hot_tub_heat_mode`
- `select.poolos_native_intellicenter_pool_heat_mode`
- `sensor.poolos_native_intellicenter_air_temperature`
- `sensor.poolos_native_intellicenter_firmware_version`
- `sensor.poolos_native_intellicenter_intellichlor_pool_output`
- `sensor.poolos_native_intellicenter_intellichlor_salt`
- `sensor.poolos_native_intellicenter_intellichlor_spa_output`
- `sensor.poolos_native_intellicenter_pool_heat_mode_raw`
- `sensor.poolos_native_intellicenter_pool_heater_id`
- `sensor.poolos_native_intellicenter_pool_maximum_temperature`
- `sensor.poolos_native_intellicenter_pool_target_temperature`
- `sensor.poolos_native_intellicenter_pool_temperature`
- `sensor.poolos_native_intellicenter_pump_flow_rate`
- `sensor.poolos_native_intellicenter_pump_maximum_rpm`
- `sensor.poolos_native_intellicenter_pump_minimum_rpm`
- `sensor.poolos_native_intellicenter_pump_power`
- `sensor.poolos_native_intellicenter_pump_rpm`
- `sensor.poolos_native_intellicenter_solar_temperature`
- `sensor.poolos_native_intellicenter_spa_heat_mode_raw`
- `sensor.poolos_native_intellicenter_spa_heater_id`
- `sensor.poolos_native_intellicenter_spa_maximum_temperature`
- `sensor.poolos_native_intellicenter_spa_target_temperature`
- `sensor.poolos_native_intellicenter_spa_temperature`
- `sensor.poolos_native_intellicenter_system_mode`
- `sensor.poolos_native_intellicenter_water_temperature`
- `switch.poolos_native_intellicenter_jets_bubbles`
- `switch.poolos_native_intellicenter_solar`
- `switch.poolos_native_intellicenter_spillway`
- `switch.poolos_native_intellicenter_water_slide`

Excluded: PoolOS Control Center autonomy/diagnostic entities. Consumers of those excluded entities require separate review before removal.
