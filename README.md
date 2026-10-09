# Home Assistant IntelliCenter Manual Bridge

A minimal, non-autonomous Home Assistant integration for Pentair IntelliCenter.

## Non-negotiable scope
- Manual Pool and Spa thermostat ON/OFF and setpoint control
- Manual heat-source selection; IntelliChlor output, salt, temperatures, pump telemetry and manual RPM if safely supported
- Manual Pool Light with existing IntelliBrite effects, Spillway, Jets/Bubbles, Slide and other commissioned accessories
- Preserve existing `poolos_native_intellicenter_*` entity IDs during cutover; preserve existing automations and lighting behavior
- **No** PoolOS autonomy, TOU, opportunistic heating, filtration engine, arbitration, or background equipment decisions
- Outage safety and seasonal schedules belong to **separate Home Assistant automations**, not the manual bridge
- Do not include credentials, addresses, tokens or HA registry backups in this public repository

## Grid outage contract (October 9, 2026)
- Tesla Powerwall gateway grid-status sensors are independent physical evidence. Either sensor continuously OFF for at least five minutes enters outage mode. Unknown/unavailable is not proof of outage. Both sensors ON stably for two minutes clears the mode.
- `input_boolean.grid_outage_protection` is ON by default. An operator may turn it OFF during an outage to release native equipment lockouts; this does not turn equipment ON. Operator bypass is latched through restart for the current outage and automatically rearmed when the grid returns.
- When outage protection is active, grid safety preempts ordinary Pool, Spa, heating, pump, and accessory commands. The native transport refuses noncompliant writes at dispatch, including Spa ON, Slide ON, high RPM, heating, lighting effects, and chlorinator adjustments.
- Pool circulates ONLY 09:00–17:00 local time at 1500 RPM, Pool heat source OFF. Pool OFF outside this window. Spa OFF; Water Slide, Jets/Bubbles, Spillway, Pool Light OFF. Pool may prime at its native equipment-managed speed before settling.
- Filtration credit accrues for observed pump-running minutes toward the existing 600-minute 10:00-to-10:00 ledger; 10 AM resets the counter even during an outage. Normal solar/filtration equipment actions are suppressed while outage protection owns equipment.
- Grid restoration releases outage authority and reevaluates current roof temperature, filtration need, and operator state; never blindly restores old commands or Spa/Slide sessions. Daytime solar reacquisition sets Solar heat source and 2900 RPM when eligible.
- The HA automation entities are `automation.grid_outage_detection_and_rearm`, `automation.grid_outage_pool_safety_supervisor`, and `automation.grid_outage_preserve_operator_bypass`. The native bridge enforces the hard command lockout.
- Physical commissioning evidence: simulated daytime entry changed heat source to OFF and verified pump eventually reached 1500 RPM; a conflicting 2900 RPM request was rejected by the native safety gate; bypass allowed the RPM command; clearing the simulated outage restored Solar and 2900 RPM. Nighttime and real-grid transitions remain untested.

## Cutover gates
1. Read-only inventory of every existing entity, unique ID, integration owner, and HA consumer.
2. Extract minimal native IntelliCenter transport and explicit manual commands from the archived PoolOS source, eliminating all PoolOS package imports and autonomy dependencies.
3. Unit/regression tests and CI green, including read-only/unknown states and duplicate command protection.
4. HA backup and registry-aware one-at-a-time migration preserving exact entity IDs without `_2` duplicates.
5. Physical commissioning of Pool, Spa, heat source, light effects, sanitation, accessories, interlocks and outage/recovery; stop on unexpected actuation.
6. Only then uninstall PoolOS. Never enable its autonomy to facilitate migration.

## Current state — October 8, 2026
The new `intellicenter_manual` integration is installed in Home Assistant and supplies **read-only live observations**, with command delivery disabled. PoolOS remains the sole operational writer and owner of the legacy entity IDs. This is **not** a completed replacement or cutover. See [deployment status](docs/DEPLOYMENT_STATUS.md) and [physical commissioning evidence](docs/PHYSICAL_COMMISSIONING_2026-10-08.md). The commissioning controls were exercised through PoolOS-native entities, not the replacement bridge.
