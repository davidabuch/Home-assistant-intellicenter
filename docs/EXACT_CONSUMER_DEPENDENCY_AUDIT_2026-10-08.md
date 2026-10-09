# Exact consumer dependency audit — October 8, 2026

**Read-only engineering evidence. No Home Assistant entity renames, automation edits, or equipment commands.**

## Source and completeness

Home Assistant prefix search reports **21 automation configurations** and **2 dashboards**. Direct `ha_config_get_automation` successfully inspected **17** automations; four returned `RESOURCE_NOT_FOUND` despite appearing in the search index: `automation.pool_light_daily_and_holiday_schedule`, `automation.home_lighting_backyard_sync_ownership`, `automation.poolos_pool_light_sam`, and one remaining legacy consumer not yet fetched. This is a **partial exact-reference audit**, not a complete cutover authorization. Dashboard configs were inspected directly; the old Pool OS dashboard has 25 distinct legacy references. The new dashboard also includes two legacy thermostat references (likely a display/config artifact); audit and remove only after confirming card locations.

## Confirmed exact dependencies and classification

| Consumers | Legacy IDs | Migration gate |
|---|---|---|
| Pool light effect buttons (American, Blue, Caribbean, Green, Party, Romance, Sunset, Royal, White, Magenta, Red) | `light.poolos_native_intellicenter_pool_light` | Native bridge light must preserve all effect names, readback, command chronology, and lighting ownership |
| `automation.pool_safety_spillway_and_jets_interlocks` | `binary_sensor.poolos_native_intellicenter_spa_active`, `switch.poolos_native_intellicenter_spillway`, `switch.poolos_native_intellicenter_jets_bubbles` | **Safety-critical**. Require fresh native Spa-active truth, fail-closed interlock behavior and tested manual commands |
| `automation.pool_schedule_seasonal_filtration_commissioning` | `binary_sensor.poolos_native_intellicenter_spa_active`, `climate.poolos_native_intellicenter_pool_thermostat` | Currently **disabled** (`initial_state: false`). Must not activate before independent commissioning |
| `automation.spa_gauge_session_manager` | `climate.poolos_native_intellicenter_hot_tub_thermostat` | Requires `off`/`heat` state semantics, 30-second qualification, startup reconciliation and HLM backyard ownership |
| `automation.spa_gauge_temperature_color` | `climate.poolos_native_intellicenter_hot_tub_thermostat` | Requires `current_temperature`, `temperature`, `hvac_action` and exact session/lighting behavior |
| `automation.hot_tub_ready_notify_once_per_session` | `climate.poolos_native_intellicenter_hot_tub_thermostat` | Wait templates, temperature attributes and once-per-session notification semantics |
| `automation.pool_ready_notify_once_per_session` | `climate.poolos_native_intellicenter_pool_thermostat` | Three-minute stable target verification, 04:00 reset, anti-Spa-temperature-spike logic |
| `automation.poolos_pool_heat_mode_alert` | `select.poolos_native_intellicenter_pool_heat_mode` | **Not a drop-in replacement**: legacy state `Solar Preferred` means gas fallback permitted; new manual bridge select `Solar` has different semantics |
| Pool OS dashboard | 25 distinct `poolos_native_intellicenter_*` IDs | Keep dashboard and old providers intact until approved cutover |

## Additional exact dependencies requiring direct configuration reads

- `automation.home_lighting_backyard_sync_ownership`: search matched; direct automation fetch returned not found. Lighting ownership contract is an independent migration gate.
- `automation.pool_light_daily_and_holiday_schedule`: search matched; direct fetch returned not found. Lighting timing and effect behavior must be preserved.
- `automation.poolos_pool_light_sam`: search matched; direct fetch returned not found.
- Remaining automation search result `automation.poolos_pool_light_sam` was not verifiable; do not assume absence from HA merely because direct retrieval failed.

## Current state and blockers

- IntelliCenter Manual Bridge telemetry is live and independent; physical commands structurally blocked.
- Fix PR #12 eliminated effect-capable light color-mode exception and isolated observation listeners; telemetry parity is restored.
- Do not infer native Spa heating from thermostat `hvac_action` without parity tests.
- Manual bridge lacks verified independent solar/heater/freeze observation and separate Spa RPM controls.
- Before cutover: full exact reference inventory, config-entry/HomeKit consumers, registry unique IDs, backup, reversible one-by-one migration, physical tests and explicit approval.

## Next engineering actions

1. Resolve HA config search-vs-direct-get discrepancies for four automations; inspect their full configs using alternative read-only routes.
2. Inspect HA automation registry/config-entry consumers and HomeKit exposure.
3. Add semantic parity regression tests (Spa Gauge and heat-mode `Solar Preferred` vs `Solar`), without changing HA automations.
4. Plan registry-preserving cutover and rollback only; physical actuation remains blocked.
