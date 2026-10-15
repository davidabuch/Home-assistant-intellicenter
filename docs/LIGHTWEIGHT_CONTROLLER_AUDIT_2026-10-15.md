# Lightweight controller regression and PoolOS retirement audit

See the [dated commissioning baseline](LIGHTWEIGHT_COMMISSIONING_BASELINE_2026-10-15.md)
for Workflow v3.2 authorization, exact provenance, gateway test fidelity and
acceptance labels. Physical acceptance remains pending.

Evidence date: October 15, 2026, America/Los_Angeles. The active controller is
Home Assistant automation plus `intellicenter_manual`. PoolOS is retired.

## Failure and root cause

Recorder shows target 90 -> 71 F at 12:31:05 with water 74 F. Native heating
became idle; pump reached 2600 RPM at 12:31:21; Pool remained `heat` (the Pool
circuit ON state, not proof of heating). Target returned to 90 at 12:38:48;
pump reached 2900 at 12:39:04. No setpoint or equipment command was issued to
reproduce this during the audit.

The deployed `automation.pool_simple_solar_and_filtration_commissioning`
(unique ID `1791536051066`, pre-edit config hash `5362eb21b3f506ab`) has:

* No pool temperature/target comparison on Solar start, adoption, reset
  reacquisition, tick restart, or grid-restoration reacquisition.
* No target-satisfied session shutdown branch.
* A quota-stop condition requiring roof <90 F, so a hot roof retains Pool
  even without demand.
* First-match `choose` ordering: the tick's counter increment consumes the
  run while debt remains. The retained 12:41 trace selects branch 3 and only
  increments the ledger; later reconciliation branches are never considered.

The heating-preference automation only selects sources. It neither starts nor
stops Pool, and source selection cannot substitute for observed heat delivery.
The native drop from Solar speed to Pool speed is consistent with heating
ending while the body circuit remains on. The native pump programs are not the
cause of the missing HA shutdown decision.

### Where was the commissioned rule lost?

The exact deletion/change cannot be established from available evidence.
This automation was not versioned in this Git repository before this repair.
The available server snapshot
`automation.1791536051066.20261009_085651.yaml` contains zero references to
`pool_target_temperature` or `pool_temperature`; it already lacks the rule.
Its older quota branch also has no temperature-demand check. The user's prior
commissioning report establishes intended behavior, but no before/after
configuration proving a later deletion was found. Do not attribute this to
PRs #96–98 or claim a specific regression commit without another snapshot.
The new fixture preserves the actual October 15 configuration for future diffs.

## Repair artifacts

These JSON documents are complete HA automation configs for the config API;
they are not automatically loaded by installing the custom integration.

* `ha_automations/pool_simple_solar_and_filtration.json`: native numeric demand
  guards, guarded owned-session shutdown, separate ledger action, live authority
  rechecks at equipment calls, claim only after successful start, stale OFF-event
  protection, and periodic night-debt reconciliation after restart.
* `ha_automations/heating_preference.json`: source selection yields to protected
  outage authority. Sanitation exceptions and body-specific preferences remain.
* `ha_automations/grid_outage_existing.json`: remove the rejected legacy
  `number.pool_rpm` request and duplicate 10 AM reset. All effective existing
  Spa/accessory/heat-source/Pool-window safety actions remain. No replacement
  runtime RPM supervisor is implemented.

Temperature inputs must be finite, plausible values before asserting daytime
demand or satisfaction. Satisfied means actual >= target. A selected source is
never evidence of active heating. A hot roof cannot start satisfied Pool.
The existing 5-minute Solar-loss trigger, 06:00 Solar crossing start, daytime
tick recovery after 08:00, and Eco Heat Solar-loss fallback are retained.
Cold-roof quota shutdown remains; hot-roof quota shutdown requires known
satisfaction or heating preference Off. Unknown temperature is not satisfaction.

Equipment decisions yield to Spa, sanitation helpers and the physical sanitation
switch, freeze protection, service mode, and protected outage authority.
Shutdown also requires Slide, Spillway, and Jets OFF. Unknown safety inputs
block schedule actuation. Automatic Ownership OFF prevents equipment commands;
ON intentionally permits eligible external-session adoption. The session claim
still protects an unclaimed external session from target-satisfied shutdown.

The verified-minute ledger is independent of equipment ownership, so real Pool
circulation during sanitation/outage/manual use is credited with Spa OFF and
pump >500 RPM. Only minute ticks increment; thermal changes cannot double-credit.
Only the lightweight schedule resets it, at 08:00, including during an outage
or external ownership. The dynamic 360/480/540/600/720-minute target helper is
unchanged. A missed reset while HA is down across 08:00 remains a limitation:
this repair does not introduce a persistent calendar rollover manager.

## Verification scope

Baseline: 94 existing integration tests pass. Added strict config replay covers
19 tests, including all 12 requested scenarios and additional numeric validity,
accessory/safety guards, accounting, authority revocation, repeated-tick
idempotency, and a queued stale OFF event. The evaluator rejects unknown
constructs; it executes the shipped config rather than a second decision model.
It demonstrates the original failure and the repaired result.

Simulation is not Home Assistant's runtime, a live reload, or physical
commissioning. Deployment/reload, CI, and post-deployment observation status are
recorded separately in the final commissioning report. No simulator result
proves native physical shutdown, restart, priming or heater cooldown behavior.

## Dependency and conflict matrix

| Component | Current owner | Classification / dependency status | Disposition / required remediation |
|---|---|---|---|
| Pool/Spa climates, temperature and target sensors | `intellicenter_manual` registry | Active independent control | Preserve stable IDs; checked live registry |
| Lightweight Solar/filtration automation | HA | Active conflict: roof-only starts/retention and missing satisfied stop | Repaired config plus replay tests |
| Heating-preference controller | HA | Active conflict: source writes attempted under outage authority | Add protected-outage guard; preserve sanitation behavior |
| Seasonal filtration commissioning automation | HA, state OFF | Obsolete but harmless duplicate schedule | Keep disabled; never enable alongside lightweight schedule |
| Outage detection/rearm and bypass latch | HA, state ON | Active independent safety | Preserve; do not remove because of historical terminology |
| Existing outage safety supervisor | HA, state ON | Active conflict: rejected runtime RPM call and duplicate 10 AM ledger reset | Remove dead RPM request and reset; preserve other effective safety actions |
| 1500-RPM outage operation | Future native feature handoff | Uncertain/unimplemented; existing supervisor cannot enforce it | Separate supervised design/commissioning; no persistent Pool preset throttling |
| Sanitation sessions and two-stage outage shutdown | HA + native `FTR02` switch | Active independent safety/session control | Preserve helpers, timer, master-ownership handoff and two-stage shutdown |
| Freeze/service-mode observations and interlocks | Manual bridge/native controller | Active independent safety | Preserve; schedule now explicitly yields |
| Filtration counter and temperature-dependent target | HA counter + UI template helper | Active independent dependency | Keep both; exclusive 08:00 reset, no 10 AM reset |
| Automatic Ownership / Simple Schedule Owns Pool | HA helpers | Active independent authority | Keep; legacy Pool Manager owner helpers are not authority |
| Old Pool Manager ownership/diagnostic helpers | Restored HA entities, many unavailable | Obsolete but harmless unless a consumer is found | Do not substitute them for current authority or bulk-delete them |
| Bridge legacy exclusion checks | `intellicenter_manual.__init__` | Safety exclusion, not a PoolOS dependency | Keep: absent/disabled PoolOS entry permits bridge; loaded legacy entry requires explicit exclusion |
| `custom_components/poolos` and PoolOS config entry | Already absent on inspected host | No installed integration dependency found | No deletion performed; this audit verifies an existing retirement |
| Standalone Pool & Spa application | Repo app -> HA bridge entities | Active independent application | No runtime PoolOS imports or service dependency found |
| Native pump-program sensors/numbers | Manual bridge + IntelliCenter | Active independent configuration | All six values observed as commissioned; preserve validation, gates and readback |
| Legacy `number.pool_rpm` | Bridge compatibility number, read-only setter | Obsolete control surface; telemetry only | Remove runtime writer; replace misleading dashboard numeric controls with read-only telemetry |
| PoolOS light SAm automation ID / HomeKit package name | HA, action targets `light.pool_light` | Obsolete but harmless naming | Preserve IDs and pairing; no cosmetic identity migration |
| PoolOS notify-health / temporary ownership shim entities | Restored unavailable entities | Obsolete remnants | Not active writers in config search; preserve until separate cleanup |
| PoolOS commissioning Boolean helpers / constant grid template | HA helpers | Obsolete but harmless | No current control consumer found; unrelated to deleting integration files |
| HLM shadow package legacy pool-light reference | Other HA package | Uncertain observation dependency | Inspect enabled shadow consumers; migrate separately if active; do not remove safety/control package wholesale |
| Historical cutover docs/backups and recorder references | Documentation / diagnostics | Obsolete but harmless historical evidence | Retain with dated status; not a reason to reinstall PoolOS |

Config searches for Pool, PoolOS, Pool thermostat, legacy RPM, grid outage and
pump-program strings were paginated where needed and returned `partial=false`.
All ten named storage dashboards were inspected. Repository source and active
HA root/package YAML were searched separately because UI search does not cover
every file or external integration setting. No full HA registry/config dump or
credentials are committed to this public repository.

## Retirement verdict and remaining gates

The manual bridge, lightweight controller, heating preferences, sanitation,
filtration ledger and standalone app do not require the PoolOS custom
integration. HA reports no PoolOS config entry and the server reports no
`/config/custom_components/poolos` directory. There is nothing to delete at that
path on this inspected host. This is not authorization to delete anything else.

Do not equate integration retirement with deleting shared helpers, automations,
HomeKit packages, safety interlocks, old backups or diagnostic history. Retain
them unless a separate consumer audit proves removal safe. Resolve the HLM
shadow reference, verify HomeKit pairing/light effects after any migration,
and obtain any missing historical commissioning snapshot if an exact loss
point is required. Prove HA reload/startup behavior and controlled physical
target lowering/raising before declaring this repair physically commissioned.

The largest remaining safety limitation is the pre-existing outage RPM gap.
Removing an already rejected request does not establish a working low-speed
outage policy. Keep the native write lockout and other safety controls; do not
alter a permanent preset to hide the gap. The future RPM reconciliation manager
and Grid Outage runtime supervisor remain outside this assignment.
