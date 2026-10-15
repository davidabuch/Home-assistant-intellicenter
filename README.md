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

Outage detection, operator bypass, native command lockouts, Spa/accessory shutdown,
and sanitation protection remain independent safety mechanisms. The old outage
supervisor's request to `number.pool_rpm` is rejected by the bridge: live RPM is
telemetry. It cannot enforce 1500 RPM. The repair artifact removes that rejected
request without replacing the deferred runtime supervisor. Do not claim low-speed
outage circulation is commissioned, or change a persistent Pool preset as a throttle.
The lightweight ledger uses an 08:00-to-08:00 cycle; the duplicate 10 AM reset is
removed in the repair artifact.

Native programs remain Spa/Pool 2600, Sanitation 3200, Heater 3000, Solar 2900,
and Grid Outage 1500 RPM. Their explicit writable configured-number entities
change persistent configuration and are never ordinary-operation speed controls.

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
