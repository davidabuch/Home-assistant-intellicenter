# RPM Guardian and protected-outage Pool preset — commissioning line

Date: October 15, 2026. Governing workflow: user-supplied GitHub + Home
Assistant Autonomous Engineering Workflow v3.2. This assignment explicitly
supersedes the prior prohibition on an outage Pool preset change and the former
six-program architecture. Physical writes/tests still require explicit operator
readiness and authorization. Deployment starts **write-disarmed**.

## Inspected baseline and failure reconstruction

At inspection the actual simulation helper `input_boolean.grid_outage_simulation`
was OFF, real sensor mode ON, `binary_sensor.1_powerwall_grid_status` ON and
qualified outage OFF. Simulation ended at 14:25:15 PDT; qualified outage cleared
at 14:26:33. Pool was ON with target 90 F, water 75 F and observed Solar heating
at 2900 RPM. Spa, sanitation and freeze protection were OFF; native mode AUTO,
communication fresh, protection enabled and bypass OFF. No helper was toggled.

The operator reports that lower-target shutdown, zero pump RPM, released claim,
stable OFF under a hot roof and subsequent target-raised Solar reacquisition
were physically successful after PRs #99/#100. That is an **operator-reported
physical baseline**, distinct from gateway simulation and this task's pending
new physical tests.

The previous low-speed Grid Outage feature was ineffective while Pool's higher
2600-RPM request remained active. This is supported by the operator's simulation
observations, not an assertion that a SPEED write is guaranteed to change the
running motor immediately. Pentair's [native pump/circuit configuration guide](https://www.pentair.com/content/dam/extranet/nam/pentair-pool/residential/automation/intellicenter/manuals---user-docs/intellicenter-web-app-users-guide.pdf)
describes circuit-associated speed configuration; it does not establish the
timing behavior of this particular installation's native SPEED writes.

Five assignments were verified live on PMP01, mode RPM:

| Policy | Program | Circuit | Initial applied RPM |
|---|---|---|---:|
| Pool | p0102 | C0006 | 2600 |
| Spa | p0101 | C0001 | 2600 |
| Sanitation | p0103 | FTR02 | 3200 |
| Heater | p0104 | X0051 | 3000 |
| Solar | p0105 | X0052 | 2900 |

The former p0106 read-only sensor still reports an **unassigned residual record
on X0056**, not FTR03. Its old writable number is unavailable. It is excluded
from policy, allowed writes, number creation and the new dashboard. No feature
or native program is created/deleted by this implementation. A read-only residual
observation is not a request to recreate the operator-deleted feature.

## Architecture and operator contract

HA automations request a single serialized coordinator; the bridge does not
gain a second thermal/filtration engine. `rpm_guardian.py` has no timers, sockets
or equipment ON/OFF commands. It coordinates configuration only. Native writes
still traverse `_verified_pump_program`, `_send`, the live exclusive-authority
check, dispatch lock, safety checks, and NEW native configured readback.

Six **Desired RPM** numbers are durable drafts. Editing persists a draft but
does not change applied policy or native settings. **Apply Configuration
Changes** validates the complete draft, commits the applied policy and reconciles
permitted differences. **Reconcile Pump Speeds**, scheduled jobs and recovery
use applied policy; pending drafts remain visible. This prevents a later timer
from silently applying an unconfirmed edit. During outage, a newly applied normal
Pool RPM is saved for restoration while the outage override remains effective.

Old configured-number IDs remain readback compatibility surfaces; their write
handler directs the operator to Desired RPM plus Apply. They cannot bypass the
coordinator. `number.pool_rpm` remains read-only telemetry compatibility. Only
the coordinator can mint an in-memory, epoch-bound preset permit. It is validated
again inside native dispatch after lock acquisition. Raw/grid/master/bypass
transitions immediately invalidate permits, including an OFF/ON flap with the
same final state.

Initial bounds are the observed pump's 600–3450 RPM, integral steps of 10.
Conservative change floors initially equal each commissioned normal preset and
1500 for the proposed outage override. These are **not manufacturer-certified
minimum flows**. Lower floors require explicit supervised equipment-flow review
through the commissioning configuration action; they are not inferred from pump
RPM. Settings and settling duration can be adjusted without source edits.

Normal drift correction defers all program writes while circulation is active.
It never stops equipment to make a write permissible. The running-Pool exception
is only for Pool outage/restoration, requires separate operator approval, native
AUTO/freeze-OFF truth, no Spa/sanitation/accessory or actual heat delivery, heat
sources OFF, fresh evidence and stabilized pump conditions. Gas cooldown is at
least five minutes; default speed settling is three minutes and configurable
up to fifteen. Native priming is never rewritten, stopped or overridden.

The existing five-minute loss and two-minute restoration detector is preserved
unchanged, including current real/simulation source selection. Before its
qualified latch there are no outage-specific preset writes. Existing independent
two-minute sanitation protection is unchanged. The old supervisor keeps its
effective Spa/accessory/light/heating shutdown, requests the coordinator, and
loses its arbitrary 09:00–17:00 Pool ON/OFF writer. This change is intentional:
the new policy must neither start Pool solely because outage exists nor stop
legitimate circulation solely to force a speed. The coordinator never starts
Pool, including when Pool was already OFF. Existing controller/safety demand
remains the circulation authority.

## Durable transaction and restoration barrier

HA's [Store API](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/storage.py)
owns the per-entry recovery record; no direct `.storage` editing is used.
Before any outage/restoration dispatch, the coordinator awaits persistence of
session ID, authority epoch, p0102, current normal/temporary policy, target,
attempt marker, verification status and restoration obligation. ACK loss is an
unknown outcome; recovery reads native configuration before another write.

States include NORMAL, OUTAGE_QUALIFYING, APPLYING_OUTAGE_SPEED, OUTAGE_ACTIVE,
RESTORING_NORMAL_SPEED, REEVALUATING_DEMAND, DEGRADED and RECOVERY_REQUIRED.
An invalid/unreadable recovery record fails closed and is not replaced by clean
defaults. Restart recovery never assumes an interrupted write failed.

During qualified outage and dirty restoration, normal heating/start commands are
blocked at both the HA controller boundary and native command gateway. Ledger
credit and the 08:00 reset run before the controller's new interlock, so they
remain independent. On qualified restoration, the current applied normal Pool
RPM is restored and verified before clearing recovery. Then an event requests
the existing heating/filtration controllers to reevaluate **current** demand;
no saved ON/OFF/source command is replayed. Operator bypass releases ordinary
equipment lockouts but does not erase the recovery obligation or authorize a
competing preset writer.

If native Pool already matches the restored value, a fresh identity-validated
read can resolve an interrupted restoration without repeating the write. If
restoration fails or communication/authority changes, the journal and prominent
warning remain and conflicting automatic writes stay blocked. Manual recovery
reset refuses to discard a pending transaction.

Configuration verification and runtime verification are separate. A verified
outage write starts a new persisted settling deadline; the old stable 2600-RPM
sample is not immediately called a 1500-RPM failure. Continued native transitions
extend settling. Once stable, physical RPM mismatch is diagnostic only: it does
not trigger repeated SPEED writes or a Pool OFF/ON cycle.

## Trigger and interface inventory

`ha_automations/rpm_guardian_reconciliation.json` requests reconciliation at
23:59, 08:00, HA restart, grid-policy transitions, Spa/session requests and a
bounded one-minute recovery heartbeat. Startup has a 60-second initialization
guard. Spa/sanitation/heat-source entity paths also verify the relevant native
program before dispatch; a program below the approved floor cannot silently
start required flow. They do not force an equipment transition to correct it.

`rpm_guardian_dashboard_view.json` adds an admin RPM Guardian view to the existing
operations dashboard: six editable drafts, read-only native configuration,
applied policy comparison/results, both normal Pool and outage values, physical
RPM/power/circuit/source/grid state, Apply/Reconcile actions, pending edits,
write gate, recovery warning, last verification/correction and failure counts.
The installed commit is read at setup from a pinned deployment marker and exposed
in diagnostics. No release version is minted before physical acceptance.

## Verification and known limits

Offline tests execute the **actual native preset gateway** with synthetic
protocol IO and telemetry. They cover matching/no-write behavior, draft/apply,
serial drift correction, native identity, write timeout/readback mismatch, short
and qualified outages, flow/priming/preemption, restoration, all required restart
windows, accepted-write/lost-ACK recovery, flapping, current normal policy changes,
manual reset, raw authority epoch changes and absence of a writable p0106.
The existing target-satisfied, stable-OFF, Solar restart, Spa/sanitation, quota,
night debt, ledger rollover and native interlock suites remain enabled.

The tests do not establish how this installation applies a running SPEED write.
No native controller restart has been performed. The following remain physical
evidence gaps until supervised tests establish them:

| Question | Current evidence / acceptance |
|---|---|
| Configuration write can be verified by gateway | Existing method + gateway tests require a NEW native readback; new physical write NOT RUN |
| SPEED applies immediately to an already running Pool | NOT RUN; running-write commissioning gate remains unapproved |
| Reactivation is required | Unknown; no automatic circuit cycling is implemented |
| SPEED change triggers native priming | Unknown; settling guard allows native transitions |
| Higher active circuit can defeat target | Operator reported previous feature conflict; active higher-flow conditions block lowering; runtime mismatch is visible |
| Config value changes but motor RPM does not | Explicit diagnostic path, no repeat-write loop; physical test pending |
| Setting survives Pentair restart | Not physically verified; do not restart Pentair merely to finish software commissioning |

## Physical sequence — awaiting explicit authorization

Recheck simulation, qualified/raw grid, protection/bypass, master, native
communication, AUTO/freeze, Pool/Spa/sanitation/accessories and all five assignments
immediately before commissioning. The commissioning gate is OFF on first load.
Enable it only for the operator-approved envelope using
`configure_rpm_guardian`, exact entry ID and
`AUTHORIZE_RPM_GUARDIAN_COMMISSIONING`. Running-Pool approval is separate from
enabling idle-only reconciliation. Record approved flow floors and settling time.

1. **A:** Read-only comparison of five programs, applied/draft policy and physical
   RPM. Matching settings must produce zero configuration writes.
2. **B:** With safe idle equipment and permission, edit one draft; prove no native
   change before Apply. Apply, verify NEW native readback, restore and verify.
3. **C:** Create an explicitly authorized mismatch; Reconcile must correct it once,
   show the receipt and then perform no further write on a repeated reconciliation.
4. **D:** With supervised running-write trial approval and verified safe flow,
   start the existing simulation. Prove no premature persistent change before
   qualification; preserve heating shutdown; after cooldown/settling guards, verify
   p0102 becomes the outage value and observe eventual physical RPM. Do not cycle
   Pool to force success. If native RPM does not settle as intended, STOP.
5. **E:** End simulation. Verify qualified restoration, current applied normal Pool
   readback, recovery clearing only after verification, current-demand reevaluation
   and final native state/physical RPM. Repeat target-satisfied OFF/stable-OFF/Solar
   reacquisition regression through the operator's production UI path.
6. **F:** Only within an additional explicitly safe fault/restart envelope, test
   interrupted outage/restoration recovery. Never reset the Pentair controller or
   deliberately strand 1500 RPM to satisfy an offline-test checklist.

STOP on unexpected activation/shutdown, unsafe valve/heating/flow, unverified
write, competing authority, stale/contradictory observations, native communication
failure, unanticipated circulation requirement, restoration failure or operator
cancellation. Preserve journal/trace evidence. No forced ownership, safety bypass,
removed feature recreation or legacy runtime RPM setter is a recovery shortcut.

Status must distinguish CODE TESTED / GATEWAY TESTED / CI GREEN / DEPLOYED /
HA OBSERVED / PHYSICALLY COMMISSIONED. A disarmed deployment is not an enabled
outage controller or physical acceptance. Record exact CI/deployed SHA and the
operator's physical results in the final commissioning ledger.
