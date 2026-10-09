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

## Outage contract
- Confirm real grid outage from independently observed Tesla Powerwall grid status for at least five minutes; unknown/unavailable is not proof of outage.
- On qualified outage, stop Pool and Spa, turn Pool Light OFF and Water Slide OFF. Protect Spa/Spillway and Spa/Jets interlocks.
- After grid restoration, re-evaluate the current seasonal Pool schedule and Spa priority. Never automatically restart Spa or Slide.
- Restore Pool Light only when previously on and the normal HA lighting policy still authorizes it; do not bypass holiday/manual precedence.
- Restart-safe, idempotent state machine; physical command verification and stale/unknown observation handling required.

## Cutover gates
1. Read-only inventory of every existing entity, unique ID, integration owner, and HA consumer.
2. Extract minimal native IntelliCenter transport and explicit manual commands from the archived PoolOS source, eliminating all PoolOS package imports and autonomy dependencies.
3. Unit/regression tests and CI green, including read-only/unknown states and duplicate command protection.
4. HA backup and registry-aware one-at-a-time migration preserving exact entity IDs without `_2` duplicates.
5. Physical commissioning of Pool, Spa, heat source, light effects, sanitation, accessories, interlocks and outage/recovery; stop on unexpected actuation.
6. Only then uninstall PoolOS. Never enable its autonomy to facilitate migration.

## Current state — October 8, 2026
The new `intellicenter_manual` integration is installed in Home Assistant and supplies **read-only live observations**, with command delivery disabled. PoolOS remains the sole operational writer and owner of the legacy entity IDs. This is **not** a completed replacement or cutover. See [deployment status](docs/DEPLOYMENT_STATUS.md) and [physical commissioning evidence](docs/PHYSICAL_COMMISSIONING_2026-10-08.md). The commissioning controls were exercised through PoolOS-native entities, not the replacement bridge.
