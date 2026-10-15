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

## Initial HA deployment and adapter correction

PR #101 merged as ea7a29b626fb3706a928f0f475598d67e64b833a, with green
post-merge CI run 38815109151. The HA-host component was backed up outside
custom_components, installed from that exact commit and compared byte for byte
(20 files). HA restart loaded the matching installed_commit diagnostic. Guardian
reported DISARMED, enabled=false, running_pool_approved=false and no interlock.

Manual read-only Reconcile observed all five expected native settings as MATCH,
with corrected=0 and failed_writes=0. This satisfies the read-only configuration
comparison portion of Test A; it does not commission persistent writes or
running-speed behavior. No simulation or new Pentair SPEED write was initiated.

Startup log inspection exposed an HA adapter defect missed by the pure gateway
suite: the synchronous authority listener lacked Home Assistant's callback
decorator, so HA dispatched it in an executor and rejected entity publication.
The fix marks this nonblocking listener for immediate event-loop execution,
preserving immediate permit invalidation. Two adapter tests now exercise the
actual listener registration/invalidation/publication through HA's documented
callback-versus-executor dispatch contract, including an authority flap and an
attribute-only update. The complete offline suite now passes 185 tests.
Reference: https://developers.home-assistant.io/docs/asyncio_thread_safety/

Automatic approval review held the new minute reconciliation automation until
this adapter correction is deployed and verified. Existing controller updates
and the RPM dashboard were installed with the Guardian write-disarmed.

## Final write-disarmed verification

The callback correction merged in PR #102 as
795c7a15bf23580552abc7430b7012716b85d6ee; post-merge run 38816103337 passed.
HA was backed up again, all 20 installed files were compared to the pinned
commit, and a normal HA deployment restart loaded that exact diagnostic revision.
Startup authority changes advanced the epoch; log inspection found no new
Guardian thread-safety error after correction. The earlier 15:13 error remains
historical evidence. Native communication recovered and Solar remained at 2900.

The reconciliation automation was then created as
automation.intellicenter_rpm_guardian_reconciliation (HA-generated unique ID
1792102863523). Its 15:22 trace 5719a88db1bc18dee2b7e0f349375b57 finished
successfully through the registered coordinator service. Subsequent minute
reconciliations reported five MATCH results, zero corrections and zero failed
writes. No persistent SPEED write was made.

HA draft test: Pool draft 2600 -> 2610 persisted a pending edit while applied
normal policy and native p0102 both remained 2600. Manual Reconcile preserved
that separation. Draft was restored to 2600, then Apply was exercised with
unchanged policy; native settings remained unchanged. This is an HA interface
test, not physical acceptance B or C.

All four deployed controller/reconciliation configs match repository artifacts
semantically (excluding HA-assigned ID for the new automation). The detector
hash remains c9d9786ed8e95e57. HA configuration check is valid and explicit
automation reload succeeded. The 15:22 schedule trace
bbd69a36e42ed778bb0b3721f8aca91e credited one observed circulation minute,
passed the new interlock, found actual 76 F below target 90 F, and emitted no
equipment command. Ledger continued to 349/480 minutes.

PR #103 fixed Markdown comparison row spacing; post-merge run 38816307375
passed. Visual verification showed all five live MATCH rows and the six draft
controls. A final blank line separates the outage-policy paragraph from the table.
The other operations views were preserved.

At this handoff Guardian is DISARMED, running-Pool approval=false, normal-control
interlock OFF, restoration_pending=false and no pending draft edits. Simulation
OFF, real grid ON, qualified outage OFF, Pool Solar 2900 RPM, Spa/sanitation/freeze
OFF and native AUTO. Tests B-F remain NOT RUN pending explicit operator readiness
and authorization. The previous target-satisfied shutdown/Solar restart physical
sequence remains operator-reported baseline, not a newly repeated physical test.

## Supervised physical Tests B–E, later October 15

The operator explicitly authorized B, C, D and E sequentially, was physically
present, and directed autonomous connected-tool execution. Test F was expressly
excluded. Fresh baseline: normal real grid, simulation OFF, all five native
identities/presets correct, Pool Solar 2900 RPM, water 76 F / target 90 F,
Spa/sanitation/freeze/accessories OFF, AUTO and fresh observations.

Scheduled Guardian requests were paused during manual commissioning; existing
outage safety stayed active. Pool flow floor was temporarily changed to 2500
through the commissioning service for the idle tests, then restored to 2600.

| Test | Result and native evidence |
|---|---|
| B | PASS: target-satisfied shutdown to 0 RPM, guarded Apply p0102 2500 verified 15:39:32, restore 2600 verified 15:39:49; pump stayed OFF |
| C | PASS: guarded idle Apply 2500, legitimate Solar restart/3450 priming, Apply normal policy 2600 while running correctly deferred; Solar settled 2900; target-satisfied OFF/0 followed by manual Reconcile restored 2600 at 15:41:49 |
| D | PASS: simulation ON 15:42:30.573; qualified latch ON 15:47:30.576; no early preset writes; heating OFF, Pool retained; cooldown/settling deferred lowering; native p0102 1500 verified 15:52:44.969, physical telemetry 1500 at 15:53:00.958, runtime VERIFIED at 15:56:23 |
| E | PASS: simulation OFF 15:56:29.875; latch cleared 15:58:29.879; manual supervised reconciliation restored p0102 2600 before journal/interlock clearing; current-demand event resumed Solar at 15:58:44, physical telemetry 2900 at 15:59:00.960 |

C's mismatch was applied-policy/native divergence created through guarded Apply
and its running deferral, rather than a separate external native writer.
Heating preference was briefly paused to isolate the manual C correction, then
restored before D. No native program other than p0102 was written. Total six
verified SPEED writes: B two, C two, D one, E one; failed writes zero.

The running outage SPEED change took effect without Pool circuit reactivation:
physical telemetry reached 1500 about 16 seconds after configured verification.
Pool stayed ON throughout D/E. No renewed 3450-RPM priming was observed for the
running preset change. Power fell from about 1095 W at 2600 to 213–215 W at 1500.
This proves behavior for this supervised trial, not universal timing or
manufacturer-certified flow suitability. Pentair restart persistence and
interrupted physical recovery remain untested; Test F was not performed.

All five native presets restored to Pool/Spa 2600, Sanitation 3200, Heater 3000,
Solar 2900; target 90 restored; real-grid mode ON, simulation and qualified outage
OFF; ordinary automations restored; recovery session/intent cleared only after
verified restoration. The RPM write gate was explicitly disabled after E.

Final cleanup identified two small defects: explicit running-write approval=false
did not revoke its prior true value, although enabled=false correctly blocked all
writes; and a resolved cooldown warning remained displayed after verified outage
operation. Two tests reproduce both failures on the prior build. Revocation now
persists false and reenabling alone cannot restore it; successful, non-conflicting
outage reconciliation clears the resolved warning. All 187 tests pass. These
changes affect authorization revocation/status cleanup and do not repeat a
physical RPM write or perform restart/fault-injection acceptance Test F.
