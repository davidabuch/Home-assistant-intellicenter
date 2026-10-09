# Read-only dependency follow-up and registry-preserving migration gates

Date: 2026-10-08. Status: design and evidence only. No authorization to activate commands, migrate entities, or retire PoolOS.

## Confirmed consumer dependencies
HA config-body search for the legacy `poolos_native_intellicenter_` prefix returned 21 automations and two dashboards without a partial-search warning. This is not a complete external-consumer inventory.

Three automations whose direct configuration retrieval failed were recovered using read-only HA configuration search:
- `automation.pool_light_daily_and_holiday_schedule`: sunset ON, **midnight OFF**, 20-second effect delay, holiday effect override, HA restart reconciliation; actuates the PoolOS Pool Light.
- `automation.home_lighting_backyard_sync_ownership`: Hue Sync has priority; when released, restores Spa Gauge if active or reevaluates backyard lighting; reads the PoolOS Spa thermostat.
- `automation.poolos_pool_light_sam`: HomeKit SAm input button invokes the legacy PoolOS light's SAm effect.

The direct-get issue is an API retrieval discrepancy, not evidence that these automations are absent. Earlier documentation mentioned a fourth unresolved automation without establishing its identity; do not invent one.

## HomeKit exposure
The loaded HomeKit config entry `01M0P7VFT1Q7YGK9FCXYMEGRRZ` (`HASS Bridge PoolOS:21070`) explicitly includes:
- PoolOS Pool and Hot Tub thermostats;
- PoolOS Pool Light;
- PoolOS Jets/Bubbles, Water Slide and Spillway switches;
- twelve effect buttons: SAm, American, Blue, Caribbean, Green, Magenta, Party, Red, Romance, Royal, Sunset and White.

This is **18 exposed entities**. The separate HomeKit thermostat bridge exposes Living Room and Master Bedroom thermostats, not the pool thermostats. Preserve HomeKit accessory identity, pairing and helper action chains before any proposed migration.

## Safety-critical contracts
`automation.pool_safety_spillway_and_jets_interlocks` actively turns OFF the PoolOS Spillway when Spa is active, and turns OFF PoolOS Jets/Bubbles when Spa is inactive. A read-only bridge entity cannot substitute for these actuator targets.

PoolOS `Solar Preferred` is a policy with gas fallback; bridge `Solar` is native source selection. They are not drop-in equivalents.

Physical commissioning on October 8 verified observation parity for Pool/Spa, gas heating, water features and light effects. Active Solar heating was not physically observed and was explicitly waived for read-only commissioning. No bridge-issued command, interlock enforcement, or HomeKit migration was tested.

## Registry-preserving migration plan — NOT AUTHORIZED TO EXECUTE
1. Export full HA registry mappings for each affected entity: entity_id, unique_id, platform, config_entry_id, device_id, name, aliases, icon, area, exposure, and disabled/hidden flags. Capture existing HomeKit bridge options and pairing identity, automations, dashboards, helper and HLM references. Current connector inspection does **not** constitute a complete registry export.
2. Classify each consumer as observation-only, actuator, safety-critical, policy-semantic, HomeKit accessory or lighting ownership. Do not map legacy Solar Preferred to native Solar.
3. Add offline non-actuating regression coverage for Spa Gauge state/temperature/hvac_action, ready notifications, unavailable/stale telemetry, 20-second Pool Light transition lockout and policy-vs-native heat-source semantics. Simulated command requests must never reach equipment.
4. Verify bridge read-only lockout and telemetry freshness; stage HA backup and tested recovery, rollback checkpoints, and a single-writer ownership handoff. No simultaneous PoolOS and bridge commands.
5. Propose a per-entity migration with old/new unique IDs and exact dependent configurations. Retain legacy PoolOS control targets until a separate approved physical commissioning plan verifies safety interlocks, lighting ownership, HomeKit behavior and rollback.
6. STOP on stale/unavailable truth, entity collision, HomeKit accessory identity change, failed interlock, unrecognized heat mode, unexpected equipment actuation, or dual authority.

**Current decision:** maintain PoolOS authority and the bridge's hard read-only guard. No entity renames or HomeKit changes. Follow `docs/REVERSIBLE_CUTOVER_ROLLBACK_CONTRACT.md` before any authorized cutover.
