# Pool Light HomeKit button action-chain audit

Date: 2026-10-08. **Read-only inspection**; no HomeKit buttons pressed, no light commands issued.

## Exact 12-button chain
All twelve HomeKit `HASS Bridge PoolOS:21070` input buttons are exposed in `filter.include_entities`. HA configuration search returned all twelve corresponding automations with `partial=false`. Each button state trigger calls `light.turn_on` on **`light.poolos_native_intellicenter_pool_light`** with the indicated effect.

| HomeKit label | Input button | HA automation | Light effect |
|---|---|---|---|
| SAm | `input_button.sam_pool` | `automation.poolos_pool_light_sam` | `SAm` |
| American | `input_button.american_pool` | `automation.american_pool` | `American` |
| Blue | `input_button.blue_pool_light` | `automation.blue_pool_light` | `Blue` |
| Caribbean | `input_button.caribbean_pool` | `automation.carribean_pool` | `Caribbean` |
| Green | `input_button.green_pool_light` | `automation.green_pool_light` | `Green` |
| Magenta | `input_button.magenta_pool_light` | `automation.turn_pool_light_magenta` | `Magenta` |
| Party Mode | `input_button.party_mode_pool` | `automation.party_pool` | `Party Mode` |
| Red | `input_button.red_pool_light` | `automation.turn_pool_light_red` | `Red` |
| Romance | `input_button.romance_pool` | `automation.romance_pool` | `Romance` |
| Royal | `input_button.royal_pool` | `automation.turn_on_royal_pool` | `Royal` |
| Sunset | `input_button.sunset_pool` | `automation.sunset_pool` | `Sunset` |
| White | `input_button.white_pool_light` | `automation.turn_on_white_pool_light` | `White` |

**Important:** The `Party Mode` button commands `effect: Party Mode`; the persistent normal-mode input select stores `Party` (not `Party Mode`). The daily schedule maps `Party` to `input_button.party_mode_pool`. Preserve this translation.

## Persistent selection and scheduling
`automation.pool_light_track_persistent_normal_mode` observes all twelve input-button state changes and saves the trigger ID to `input_select.pool_light_normal_mode` if the previous state is valid and `input_boolean.pool_light_holiday_override_active=off`. The input select's enumerated options are `Unknown, SAm, American, Blue, Caribbean, Green, Magenta, Party, Red, Romance, Royal, Sunset, White`.

`automation.pool_light_daily_and_holiday_schedule` commands Pool Light ON at sunset, waits **20 seconds**, then presses a holiday-specific or saved-normal-mode button. At **midnight** it commands light OFF. At HA startup it waits 30 seconds and reconciles ON only if `sun.sun=below_horizon` and local hour >=12. Holiday override is toggled by the schedule and prevents the normal-mode tracker from recording holiday-generated button selections.

Holiday mappings in the live configuration:
- December 31 / January 1: Party.
- July 4 (or its Friday–Sunday observed weekend depending on weekday): American.
- Memorial Day weekend: American.
- February 14: Romance.
- March 17: Green.

## Critical migration behavior
1. Preserve all twelve existing HomeKit buttons and their automation IDs; they are not optional decorations.
2. Preserve the normal-mode tracker and holiday override helper behavior; do not collapse `Party` and `Party Mode` without an explicit compatibility mapping.
3. Preserve the existing 20-second transition delay; do not infer that selecting an effect immediately after ON is safe.
4. Preserve existing **midnight** OFF policy (not 01:59).
5. Any later bridge actuator migration must prove all 12 effect names and readback match physical behavior, plus HomeKit button action and Apple accessory continuity. Offline regression alone is insufficient.
6. Do not redirect any light service calls to the read-only manual bridge. PoolOS retains authority.

## Verification boundaries
This is a configuration and control-path audit, **not** a fresh live physical test of twelve button presses or Apple Home pairing identity. No HA automations, helpers, HomeKit configuration, or equipment were modified.
