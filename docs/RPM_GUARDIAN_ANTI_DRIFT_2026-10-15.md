# RPM Guardian — event-driven anti-drift and recovery servicing

Date:2026-10-15. Scope authorized: implementation, tests, CI, merge, deployment
and normal HA verification. No physical outage simulation/fault injection.
PoolOS remains retired. Production permissions must remain enabled.

## Diagnosis before repair

Live installed component5d463df (PR106), main d7b28a7 (PR108), both flags true,
no recovery, six prior verified writes/zero failures, native five MATCH, Pool/SpaOFF,
pump0, grid healthy/real sensingON/simulationOFF. Live reconciliation automation
hash1d4a0c944c8936ee called ha_policy_request for every trigger.

RPMGuardian.reconcile ignored reason. Every fresh request read/identity-validated
all five native PMPCIRC records, compared applied policy, and tried every mismatch
in its normal branch. Therefore every minute could discover AND correct ordinary
drift when idle, or repeat deferred normal correction while running. No durable
separate routine obligation existed; only the outage intent/session/restoration
journal was durable. Changing the automation alone would not make reason meaningful
or preserve the requested distinction between deferred routine work and new drift.

The read callback uses the transport's native model/identity validation, under
fresh-observation gating; it is not a newly introduced socket poll per request.
The final writer remains set_configured_pump_program_rpm, private coordinator
permit revalidated inside the transport lock, fresh post-dispatch readback.

## Resulting policy

| Request | Native reads when fresh | Can establish routine work | Can write |
|---|---|---|---|
|08:00 accounting_rollover|All five|Yes|Safe idle routine or guarded safety|
|23:59 before_filtration|All five|Yes|Same|
|HA start/integration setup|After initialization|Yes, durable queued scan|Same|
|Spa session activation|All five|Yes|Same; running normal correction defers|
|Pool/Spa sanitation activation|All five|Yes|Same; active sanitation defers normal correction|
|Manual/default service, Reconcile button|All five|Yes|Same|
|Apply Configuration Changes|All five after draft validation/commit|Yes, current applied policy|Same|
|Existing Spa/sanitation/Gas/Solar native start preflights|All five|Yes|Same; approved floors still checked before start|
|Minute recovery_heartbeat|All five for safety/diagnostics|No new ordinary work; can finish an already queued event scan|Existing pending routine or safety only|
|Grid-policy / qualified_outage_safety / unknown legacy reason|All five|No new ordinary work|Existing pending routine or safety only|

The automation keeps the identical triggers/times/entities/queue mode and passes
trigger.id in service data, with manual fallback for an explicit trigger action.
Only its description/reason routing change. Jinja data expression was evaluated
by HA, including missing-trigger-id fallback. No Solar/filtration schedule,
native value, dashboard layout, independent supervisor or writer changed.

Named routine reasons include compatibility08:00/23:59 aliases. Unknown or old
ha_policy_request reasons are recovery-only; callers omitting reason retain
explicit manual behavior. The separate qualified-outage safety automation still
calls qualified_outage_safety and requires no edit.

## Durable ordinary work versus safety recovery

routine_scan_pending records an authorized event not yet successfully read.
pending_routine maps only detected mismatched program keys to current applied
targets. Both use the existing HA Store, backward-compatible defaults for version1
records. Invalid new metadata fails closed. Apply atomically supersedes old
routine work with a new approved policy and queued scan.

A routine scan persists before reads, survives stale startup/communication failure,
and persists detected work before native dispatch. Pending normal writes retain
all original idle, authority, freeze/AUTO, flow, outage/bypass and native gates.
Normal permits additionally require that exact pending target. Heartbeats retry
that obligation when safe, reread before retry, and clear it on verified/matching
native configuration. It does not block ordinary demand like dirty safety recovery.

Example:2960 Solar is observed diagnostically by a clean heartbeat but remains2960.
08:00 may establish solar->2900; if running, it defers. A14:00 safely idle heartbeat
may then complete that saved obligation. After it clears, a later new2960 manual
change waits for a new eligible routine event. Draft dashboard edits are not applied
authority; physical RPM and native configured RPM remain separate observations.

Safety journal/session/epoch logic remains separate and unchanged. Heartbeats
still discover a stranded native Pool1500 even with clean/missing journal, qualify
outage/restore, honor running-Pool approval, preserve unknown-write recovery,
and verify2600 restoration before current-demand handoff. Manual temporary presets
do not excuse a stranded outage value, dirty recovery, or existing flow preflight.

## Regression evidence

Baseline new tests fail on the original coordinator; the primary reproduction is
the heartbeat immediately undoing2960 Solar while safely idle. Before-fix output
retains failures and expected absent-field/API errors for newly introduced state.
After repair:236 passing tests =214 original +20 new native-gateway policy cases
+2 adapter startup/reason tests. No existing test was weakened.

Coverage includes all requested17 acceptance areas: clean heartbeat/no initiation;
2960 persistence;08:00/23:59; Spa/Pool and Spa sanitation; initialized startup;
manual/apply; durable deferred idle completion; pending restoration; real policy
1500/2600; restricted running privilege; last-durable-record restart; no circuit
commands; all existing Solar/filtration/accounting/sanitation/freeze/ownership tests.
Additional cases cover ACK loss, identity/readback/currentness, old/new records,
unknown reasons, superseded Apply targets, external match clearing obligations,
and queued request serialization. All native writes in these tests traverse the
real guarded transport; only external telemetry/protocol IO are synthetic.

## Acceptance levels

Code tests and CI are distinct from HA deployment/readback and physical proof.
Live deployment verification will append exact revision, automation hash, flags,
pending/recovery/readback, automatic reason trace and no-unexpected-write result.
Do not physically create a2960 mismatch solely to demonstrate this change.
No new physical outage or hazardous experiment is authorized; earlier B–E evidence
covers the unchanged writer/qualification path, with offline new heartbeat coverage.

