# Home Assistant IntelliCenter Manual Bridge

A minimal, non-autonomous Home Assistant integration for Pentair IntelliCenter.

## Non-negotiable scope
- Manual Pool and Spa thermostat ON/OFF and setpoint control
- Manual heat-source selection; IntelliChlor output, salt, temperatures, pump telemetry and manual RPM if safely supported
- Manual Pool Light with existing IntelliBrite effects, Spillway, Jets/Bubbles, Slide and other commissioned accessories
- Preserve commissioned bridge entity IDs, HomeKit identities, automations and lighting behavior. PoolOS is retired; historical cutover prefixes are not the active control architecture.
- **No** PoolOS autonomy, TOU, opportunistic heating, filtration engine, arbitration, or background equipment decisions
- Outage safety and seasonal schedules belong to **separate Home Assistant automations**, not the manual bridge
- Do not include credentials, addresses, tokens or HA registry backups in this public repository

## Current controller and outage status — October 15, 2026

Home Assistant lightweight automations control scheduling and heating preferences
through the `intellicenter_manual` bridge. PoolOS is retired. The inspected HA
host has no configured PoolOS entry and no `custom_components/poolos` directory.
The October 8 cutover documents below are historical evidence.

See [controller repair and retirement audit](docs/LIGHTWEIGHT_CONTROLLER_AUDIT_2026-10-15.md)
for the target-satisfied shutdown repair, regression coverage, dependency matrix,
and commissioning limits. The checked-in `ha_automations/*.json` files are HA
config-API deployment artifacts; installing this integration does not load them.

The coordinated [RPM Guardian commissioning line](docs/RPM_GUARDIAN_COMMISSIONING_2026-10-15.md)
uses **five** native programs: Spa/Pool 2600, Sanitation 3200, Heater 3000,
and Solar 2900 RPM initially. The operator removed the separate Grid Outage
feature/program; do not recreate it. Its residual unassigned observation is
excluded from writable configuration.

Six persistent Desired RPM values are drafts until **Apply Configuration Changes**.
A single serialized, durable coordinator reconciles only permitted differences.
The new operator-approved outage policy temporarily applies the configurable
outage RPM (initially 1500) to Pool p0102, then verifies restoration to the current
normal applied value before normal demand resumes. This supersedes the earlier
prohibition on that strategy. It remains **write-disarmed pending explicit
supervised commissioning**, including separate running-Pool flow approval.

Normal writes defer during circulation. Native priming, freeze, Spa/sanitation
priority, existing outage qualification/interlocks and the 08:00 ledger remain.
Actual motor RPM is telemetry; a persistent configuration readback is a separate
fact. Runtime mismatch does not cause a repeated-write or forced Pool-cycle loop.
See the dated commissioning protocol for evidence levels and unresolved native
running-speed behavior. No public release is promoted before physical acceptance.

## Cutover gates
1. Read-only inventory of every existing entity, unique ID, integration owner, and HA consumer.
2. Extract minimal native IntelliCenter transport and explicit manual commands from the archived PoolOS source, eliminating all PoolOS package imports and autonomy dependencies.
3. Unit/regression tests and CI green, including read-only/unknown states and duplicate command protection.
4. HA backup and registry-aware one-at-a-time migration preserving exact entity IDs without `_2` duplicates.
5. Physical commissioning of Pool, Spa, heat source, light effects, sanitation, accessories, interlocks and outage/recovery; stop on unexpected actuation.
6. Only then uninstall PoolOS. Never enable its autonomy to facilitate migration.

## Historical cutover evidence

The October 8 read-only deployment and legacy-writer observations describe the
state at that date, not the current architecture. See
[historical deployment status](docs/DEPLOYMENT_STATUS.md) and
[historical physical commissioning evidence](docs/PHYSICAL_COMMISSIONING_2026-10-08.md).
