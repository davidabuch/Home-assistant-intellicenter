# IntelliBrite HomeKit scene-button parity and startup contract — 2026-10-08

**Evidence:** live Home Assistant automation configurations retrieved read-only using `ha_search(include_config=true)`. **No cutover authorization, HA mutations, or physical commands.**

## Twelve existing HomeKit input buttons and exact live legacy actions

| HomeKit input button | Triggering automation entity | Target | Exact `light.turn_on` effect |
|---|---|---|---|
| `input_button.sam_pool` | `automation.poolos_pool_light_sam` | legacy PoolOS pool light | `SAm` |
| `input_button.american_pool` | `automation.american_pool` | legacy PoolOS pool light | `American` |
| `input_button.blue_pool_light` | `automation.blue_pool_light` | legacy PoolOS pool light | `Blue` |
| `input_button.caribbean_pool` | `automation.carribean_pool` | legacy PoolOS pool light | `Caribbean` |
| `input_button.green_pool_light` | `automation.green_pool_light` | legacy PoolOS pool light | `Green` |
| `input_button.magenta_pool_light` | `automation.turn_pool_light_magenta` | legacy PoolOS pool light | `Magenta` |
| `input_button.party_mode_pool` | `automation.party_pool` | legacy PoolOS pool light | `Party Mode` |
| `input_button.red_pool_light` | `automation.turn_pool_light_red` | legacy PoolOS pool light | `Red` |
| `input_button.romance_pool` | `automation.romance_pool` | legacy PoolOS pool light | `Romance` |
| `input_button.royal_pool` | `automation.turn_on_royal_pool` | legacy PoolOS pool light | `Royal` |
| `input_button.sunset_pool` | `automation.sunset_pool` | legacy PoolOS pool light | `Sunset` |
| `input_button.white_pool_light` | `automation.turn_on_white_pool_light` | legacy PoolOS pool light | `White` |

Every action targets `light.poolos_native_intellicenter_pool_light`, not `light.pool_light`. The misspelled automation entity `automation.carribean_pool` is an existing identifier and must not be silently renamed. The scheduling automation uses shorthand `Party` for the input button, while the actual legacy service effect is `Party Mode`.

## Hardware timing is a requirement, not incidental latency

User confirmed **IntelliBrite requires approximately 20 seconds after selecting a light or scene for the controller to register the selection**. Preserve the existing 20-second startup/transition allowance in the Pool Light daily/holiday automation and future parity tests. Do not shorten, remove, or treat this as evidence of a faulty automation. For commissioning, distinguish command acceptance, controller registration after the delay, and verified physical lamp state; effect attribute alone is insufficient evidence of physical ON. Avoid issuing conflicting rapid scene commands during the registration interval.

The existing `automation.pool_light_daily_and_holiday_schedule` turns Pool Light on at sunset and off at **midnight**, delays 20 seconds after circuit activation before selecting an effect, and waits 30 seconds after HA startup before reconciliation. Preserve these exact observed behaviors unless separately authorized to change them.

## Migration and rollback gates

1. Keep all 18 existing HomeKit bridge exposures, all 12 input buttons and their automation identities, legacy PoolOS light target, and Apple Home pairing unchanged.
2. Manual Bridge remains `allow_commands=False` and must never become a second writer alongside PoolOS.
3. Before any approved cutover, obtain HA backup and HomeKit identity evidence; compare exact scene-name semantics and 20-second command/readback chronology on every button.
4. Regression acceptance: all twelve input-button IDs map to their exact existing effect strings; Party Mode is not incorrectly renamed Party; SAm casing is retained; Caribbean spelling is correct in effect even though automation entity is misspelled; light OFF retaining prior effect must not be reported as ON.
5. Independently validate Spa safety interlocks and PoolOS heat-source authority before any actuator migration. Stop for stale telemetry, dual writers, HomeKit identity changes or physical discrepancies.
6. **No physical scene-button tests were performed in this audit.** This document records configuration parity only.
