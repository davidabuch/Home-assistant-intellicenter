# IntelliCenter Manual Bridge — read-only physical commissioning evidence
**Date:** 2026-10-08 (America/Los_Angeles)  
**Repository:** `davidabuch/Home-assistant-intellicenter`  
**Scope:** Independently observe IntelliCenter through the read-only bridge alongside PoolOS. **Not** a controller authority handoff or permission to enable commands, migrate entity IDs, or retire PoolOS.

## Acceptance classification
- **PHYSICALLY COMMISSIONED / HA OBSERVED**: Pool Gas heating ON/OFF; Spa Gas heating ON/OFF; Pool and Spa body ON/OFF; Spillway ON/OFF; Water Slide ON/OFF; Jets/Bubbles ON/OFF; Pool Light ON/OFF and Caribbean→Blue effect observation. The physical stimuli were manually performed in the Pentair app by the operator; Home Assistant recorded transitions.
- **HA OBSERVED**: Solar selected on Pool while active solar heating remained OFF because roof conditions did not permit heating. Operator **accepted/waived** a separate active-Solar physical heating test on 2026-10-08. This is **not** evidence of physically observed active Solar delivery or Solar shutdown.
- **HA OBSERVED parity, not physical command acceptance**: IntelliChlor pool output 40%, Spa output 4%, salt 3950 ppm, and static circuit/pump parity.
- **NOT RUN / NOT AUTHORIZED**: Any command issued by the new bridge, authority handoff, native manual write semantics, HomeKit/automation cutover, registry rename, independent safety interlock actuation through the bridge, or PoolOS retirement.

## Heating observations (approx. 19:15–19:32 PDT)
| Stimulus | Bridge | PoolOS/native observation | Acceptance |
|---|---|---|---|
| Pool ON, Solar selected, roof insufficient | Pool thermostat heat/idle; `select.pool_heat_source=Solar`; `solar_heating_active=off` | Pool active; selected H0002; pump 2600 RPM | HA OBSERVED, selected-but-idle behavior |
| Pool Gas heating | Pool thermostat heat/heating; `pool_heating_active=on`; `gas_heater_active=on`; Solar/Spa heating OFF | Gas H0001, pump 3000 RPM, legacy thermostat heating | PHYSICALLY COMMISSIONED |
| Pool OFF | Pool thermostat OFF; Pool/Gas heating OFF; pump 0 | Legacy Pool thermostat OFF, Pool inactive | PHYSICALLY COMMISSIONED |
| Spa Gas heating | Spa thermostat heat/heating, temp 84°F target 98°F; `spa_heating_active=on`; `gas_heater_active=on` | Legacy Spa thermostat heat/heating, H0001, pump 3000 RPM; Pool heating OFF | PHYSICALLY COMMISSIONED |
| Spa OFF | Spa thermostat OFF, Spa/Gas heating OFF, pump 0 | Legacy Spa thermostat OFF; Spa inactive | PHYSICALLY COMMISSIONED |

**Note:** An earlier proposed Spa setpoint of 102°F was not observed. Both integrations actually reported a 98°F target and 84°F current temperature during the heating test. Do not rewrite this as a 102°F test.

## Coordinated manual feature sequence — recorder evidence (19:37–19:40 PDT)
Operator used Pentair app, and the assistant compared the bridge with PoolOS using HA recorder history and final live state.

| Function | Bridge state chronology | PoolOS/native corroboration | Acceptance |
|---|---|---|---|
| Pool body | ON around 19:37:26; OFF around 19:37:56 | `binary_sensor.poolos_native_intellicenter_pool_active` ON 19:37:26.166; OFF 19:37:56.066 | PHYSICALLY COMMISSIONED observation |
| Spillway | ON 19:37:34.170; OFF 19:37:50.751 | ON 19:37:34.253; OFF 19:37:50.760 | PHYSICALLY COMMISSIONED observation |
| Water Slide | ON 19:37:40.953; OFF 19:37:46.945 | ON 19:37:41.041; OFF 19:37:47.052 | PHYSICALLY COMMISSIONED observation |
| Spa body | Spa thermostat heat around 19:38:03.969; OFF 19:38:25.981 | Spa active ON 19:38:04.074; OFF 19:38:26.122 | PHYSICALLY COMMISSIONED observation |
| Jets/Bubbles | ON 19:38:14.169; OFF 19:38:21.020 | ON 19:38:14.258; OFF 19:38:21.054 | PHYSICALLY COMMISSIONED observation |
| Pool Light | OFF 19:38:32.939; ON 19:38:42.943; final effect Blue | OFF 19:38:33.032; temporarily unavailable 19:38:42.292–19:39:02.296; unavailable 19:39:09.194–19:39:29.199; recovered ON, effect code BLUER | PHYSICALLY COMMISSIONED observation, with transition caveat |
| Pump | 0→2600 RPM at 19:37:42.047; 2600→0 at 19:37:55.980 | PoolOS RPM parity observed; final 0 | HA OBSERVED |

The bridge's light effect changed from Caribbean to Blue and PoolOS independently read `BLUER` / Blue. **Return to Caribbean was not observed** and is not a pass criterion. The two ~20-second legacy PoolOS light-unavailable intervals match its configured transition lockout, but root cause and behavior under longer/repeated scene changes remain unproven. Bridge continued showing the light ON; both ended on Blue. No IntelliCenter-matching structured system-log errors were found at final check.

**Final observed state:** Pool OFF, Spa OFF, Spillway OFF, Water Slide OFF, Jets/Bubbles OFF, pump 0 RPM; Pool Light ON in Blue effect. Both bridges' light entities ON / Blue.

## Live configuration and non-actuation safeguards
- Bridge config entry `01M4F1DFGA4AH4F9E9M7MJCR5Q` (`intellicenter_manual`, 192.168.1.136) was `loaded` on 2026-10-08.
- Bridge is intentionally read-only; `allow_commands=False` and commissioning controller rejects mutations. **No bridge-issued physical command was tested or authorized.**
- PoolOS remains the existing operational controller; legacy entity IDs and automations remain untouched.
- Current-state parity also observed for chlorinator values, pool light, pump and water features. Do not extrapolate to autonomous behavior, write protocol or long-run reliability.

## Remaining cutover-readiness gates — still blocking any authority migration
1. Resolve the incomplete exact consumer audit in `docs/EXACT_CONSUMER_DEPENDENCY_AUDIT_2026-10-08.md`, including HA search vs direct automation retrieval failures, config-entry helpers, HomeKit exposure, external consumers, and HLM lighting ownership.
2. Preserve PoolOS-only safety/ownership entities and distinguish PoolOS **Solar Preferred** semantics from the bridge's native **Solar** selection.
3. Close observational/functional gaps where required (freeze/heater/solar provenance, separate Spa RPM behavior, and lighting transition behavior); test fail-closed handling and freshness.
4. Stage backups, stable unique-ID mapping, exact dependency migration, physical safety checks and rollback per `docs/REVERSIBLE_CUTOVER_ROLLBACK_CONTRACT.md`. That contract explicitly remains **design only / not authorized for execution**.
5. Obtain separate explicit authorization before enabling any command-delivery, replacing existing PoolOS consumers, or attempting a controller handoff.

## Decision
**ACCEPTED:** Read-only manual observation commissioning for the specific tested functions, with active Solar physical heating explicitly waived by the operator.  
**NOT ACCEPTED / NOT AUTHORIZED:** Full functional replacement, command actuation, unattended autonomy, registry cutover, or PoolOS retirement.

Evidence provenance: Home Assistant recorder history and live state queried during the October 8, 2026 commissioning conversation; operator's Pentair app stimuli and Solar waiver. This document is a dated evidence baseline, not a timeless design contract.
