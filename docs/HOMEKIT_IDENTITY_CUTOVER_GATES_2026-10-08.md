# HomeKit identity and consumer-compatibility cutover gates

Date: 2026-10-08. **Read-only engineering plan. NOT authorization to cut over.**

## Exact current HomeKit configuration (observed live)
Home Assistant config entry `01M0P7VFT1Q7YGK9FCXYMEGRRZ`: domain `homekit`, title `HASS Bridge PoolOS:21070`, source `import`, state `loaded`, options `mode=bridge`, and **18 exact `filter.include_entities` entries**. The `entity_config` options provide names and accessory metadata, so changing the filter alone is not an identity-preserving migration.

| Existing HomeKit name | Current entity |
|---|---|
| Pool | `climate.poolos_native_intellicenter_pool_thermostat` |
| Hot Tub | `climate.poolos_native_intellicenter_hot_tub_thermostat` |
| Pool Light | `light.poolos_native_intellicenter_pool_light` |
| Jets | `switch.poolos_native_intellicenter_jets_bubbles` |
| Spillway | `switch.poolos_native_intellicenter_spillway` |
| Water Slide | `switch.poolos_native_intellicenter_water_slide` |
| SAm Pool | `input_button.sam_pool` |
| American Pool | `input_button.american_pool` |
| Blue Pool Light | `input_button.blue_pool_light` |
| Caribbean Pool | `input_button.caribbean_pool` |
| Green Pool Light | `input_button.green_pool_light` |
| Magenta Pool Light | `input_button.magenta_pool_light` |
| Party Mode Pool | `input_button.party_mode_pool` |
| Red Pool Light | `input_button.red_pool_light` |
| Romance Pool | `input_button.romance_pool` |
| Royal Pool | `input_button.royal_pool` |
| Sunset Pool | `input_button.sunset_pool` |
| White Pool Light | `input_button.white_pool_light` |

Existing `entity_config` for six PoolOS device entities includes `manufacturer=PoolOS`, `model=PoolOS Requested Heat Mode`, `sw_version=0.11.92`, and `platform=poolos`; names Pool, Hot Tub, Pool Light, Jets, Spillway, Water Slide. Buttons are platform Input Button. `exclude_*` filters empty. The HomeKit config-entry metadata alone **does not establish stable Apple accessory instance IDs or guarantee pairing continuity**. Obtain HomeKit storage/backup and physical Home app verification before a change.

## Contract-level migration gates
1. **Freeze the current HomeKit bridge** and all 18 exposed entity IDs. Preserve button IDs, action automations, scene names and ownership.
2. Preserve all six legacy PoolOS actuators; the manual bridge is read-only and cannot currently satisfy HomeKit control. No dual writers.
3. Document HomeKit accessory pairing/identity preservation and verify an HA backup can restore HomeKit bridge configuration. Do not assume the UI entity ID is the Apple Home accessory identity.
4. Create an exact per-button matrix: HomeKit input_button -> HA automation -> `light.poolos_native_intellicenter_pool_light` effect. Test every effect readback and 20-second transition handling before any later authorized change.
5. For thermostats, test PoolOS requested-heat-mode policy and native bridge heat-source semantics separately. `Solar Preferred` is **not** native `Solar`. Verify Spa Gauge, Ready notifications, and automation traces.
6. For Spillway/Jets, prove protective OFF behavior when Spa state changes and on stale/unavailable truth. These interlocks are required to function before and after any eventual authority transfer.
7. Run the offline test suite, snapshot all HA registry unique IDs and affected configs, obtain a full HA backup, agree rollback and single-writer handoff; **separate user approval** required for physical actuation or registry migration.
8. STOP if HomeKit pairing changes, commands fail, entity IDs collide, an interlock fails, telemetry is stale, or PoolOS and bridge can both write.

## What has actually been tested
Read-only bridge observation parity was physically commissioned for Pool/Spa, gas heat, Spillway, Water Slide, Jets and Pool Light, with active Solar heat test waived. Offline regressions cover telemetry semantics and fail-closed handling. **Neither HomeKit pairing continuity nor bridge-originated commands nor full effect-button coverage have been physically commissioned.**

## Documentation reconciliation
The original `EXACT_CONSUMER_DEPENDENCY_AUDIT_2026-10-08.md` and `REVERSIBLE_CUTOVER_ROLLBACK_CONTRACT.md` describe three automation configs as inaccessible through the direct API. Later HA `ha_search(include_config=true)` recovered all three named configurations, as documented in `REGISTRY_CUTOVER_READINESS_2026-10-08.md`. This resolves the named config-content gap but **not** the broader external-consumer or HomeKit identity audit. Do not use older status wording to claim they remain unreadable.

No Home Assistant or physical device mutations occurred in preparing this document.
