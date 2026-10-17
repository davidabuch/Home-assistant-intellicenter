# Manual Pool ownership / overnight Gas heating

Status: engineering candidate; merge, live deployment, restart and physical tests
require operator approval. No equipment commands or HA configuration writes were
issued during development. PoolOS remains retired.

## Evidence and diagnosis

Read-only inspection on October 17, 2026 (America/Los_Angeles):

* GitHub main: `5dbb2f10c229c9ffba6c3536ccbbdac86e1a7bd3`.
* Starting local branch: `fix/family-photographic-lawn`, head `8c3698d`;
  no tracked changes, only generated untracked Python caches. The dedicated
  `fix/manual-pool-ownership` branch starts at exact main.
* Live schedule and heating-preference JSON exactly matched main. Sanitation
  was live-only and is now captured verbatim as a recovery fixture.
* Automatic Ownership was ON throughout the investigated overnight window.
  The Pool source stayed Gas; target was 90 F and actual water 80–81 F.
* HA logbook attributes both OFF transitions directly to
  `automation.pool_simple_solar_and_filtration_commissioning`, triggered by
  `sensor.pool_temperature`. This establishes the writer, rather than merely
  correlating the schedule marker with shutdown.

| Local timestamp | Observed transition |
|---|---|
|03:19:53.736|Daily filtration target 480 → 540 minutes|
|03:20:00.111|Credited minutes 480 → 481|
|03:20:00.117|Schedule ownership OFF → ON|
|03:20:05.738|Daily target 540 → 480|
|03:20:06.729|Pool OFF, logbook attributed to schedule / Pool temperature trigger|
|03:50:12.744|Pool manually restarted; logbook records climate service/user context|
|03:51:26–03:52:00|Outage bypass briefly ON, then OFF; outage latch remained OFF|
|03:56:55.942|Daily target 480 → 540 after earlier temperature oscillation|
|03:57:00.110|Credited minutes 481 → 482|
|03:57:00.115|Schedule ownership OFF → ON|
|03:57:14.752|Daily target 540 → 480|
|03:57:15.741|Pool OFF, logbook again attributes schedule / temperature trigger|

Deterministic replay of the captured schedule reproduces adoption while debt
exists, followed by quota shutdown when the dynamic target drops. The roof was
not Solar eligible. The exact historical choose-branch trace is unavailable:
only the five most recent minute traces remained. Thus writer attribution is
confirmed; branch reconstruction is strongly supported by state history and
replay, not a recovered historical execution trace. This was not a
target-satisfied thermal shutdown and no source change is recorded in this
window. Dynamic filtration targets and their thresholds are intentionally
unchanged.

Two additional confirmed configuration defects affect the requested contract:

1. Heating preference could write Pool Off/Gas/Solar with Automatic Ownership
   OFF, on activation, preference change, stabilized roof change or restoration.
2. Sanitation cleanup unconditionally set Automatic Ownership ON, including at
   every HA startup without a sanitation obligation. This could reclaim a manual
   session. It also unconditionally sent Spa OFF at ordinary startup. There is
   no evidence that this second defect caused the two overnight interruptions.

## Accessible control inventory

HA config searches completed without partial results or pagination for Pool,
the Pool thermostat/source/master/session markers, set_temperature, pool_rpm,
PMPCIRC, freeze, B1101 and grid_outage_active. Searches covered automations and
scripts; helper configuration was captured separately. Enabled states were read.

| Component / owner | Writes or authority | Disposition |
|---|---|---|
|Lightweight schedule, HA, enabled|Pool ON/OFF, Solar selection, schedule claim, minute credits, 08:00 reset|Existing master and safety checks retained; release stale claims in manual mode; recheck master before every claim|
|Heating preference, HA, enabled|Pool and Spa native heat source|Gate only Pool writes with master ON; recheck before each Pool select; ownership-resumed trigger reconciles Pool only|
|Sanitation sessions, HA, enabled|Pool circulation/source OFF, Spa circulation/source OFF, FTR02, timer, previously master OFF/ON|Retain all session actions/safety cleanup; stop writing operator master; require a session/native switch/timer obligation for restart/outage/timeout cleanup|
|Two-stage sanitation outage shutdown, HA, enabled|Sanitation switch/session/timer shutdown|Unchanged, remains authoritative independently of master|
|Grid detector/rearm and operator bypass, HA, enabled|Qualified outage and bypass latches|Unchanged; bypass is never manual Pool ownership|
|Grid safety supervisor, HA, enabled|Heating OFF, Spa/accessory/light shutdown, Guardian request|Unchanged, master OFF does not bypass it|
|RPM Guardian and HA adapter, bridge + HA, enabled|Single guarded persistent pump-program writer, journal/restoration, startup recovery|No source/config changes; existing manual-authority, flow, freeze, native readback and running-write restrictions remain|
|Native bridge transport|Manual thermostat target/ON/OFF/source and accessories; serialization and freshness checks|Unchanged; master OFF does not disarm manual commands or bypass native/outage/Guardian checks|
|Native IntelliCenter|Thermostat, body priority, freeze/flow/service/priming safeguards|Unchanged; external panel/program actors cannot be fully audited from HA config search|
|Seasonal filtration commissioning, HA, disabled|Duplicate Pool ON/OFF schedule|Remain disabled; do not activate with lightweight schedule|
|Hot Tub source-on-start, HA, disabled|Spa source only|Unchanged; current enabled preference controller retains Spa policy|
|Spillway/Jets interlocks, HA, enabled|Accessory OFF based on Spa state|Unchanged|
|PWA and HomeKit/manual HA clients|Manual target, body ON/OFF and feature actions|Unchanged; no HA automation/script set_temperature writer found|
|Light schedules/Pico color automations and scripts|Pool lighting only|Unchanged, no Pool circulation/source ownership|
|Pool-ready, light-ready, heat-source and safety notifications|Read equipment, notify or change lighting|No Pool circulation/source writes; unchanged|
|Legacy poolos-named heat alert / light SAM automation|Current native source notification / light effect|Names are historical; no active PoolOS controller reintroduced|
|Ledger helpers|Counter and dynamic daily target|Same sole reset at 08:00, verified running minute credits independent of ownership|

No HA automation/script references to `number.pool_rpm` or PMPCIRC were found.
The integration's legacy runtime number setter still rejects writes. Native
preset setters remain behind the original Guardian; no second writer is added.
Search establishes accessible HA configuration coverage, not proof that an
external panel/app has no independent commands or schedules.

## Exact implementation

* `ha_automations/heating_preference.json`: Pool-only ownership condition and
  immediate pre-write checks; OFF→ON ownership trigger reconciles Pool
  preference while leaving Spa unchanged for that new event. Existing events
  retain all their previous Spa behavior and source mappings.
* `ha_automations/pool_simple_solar_and_filtration.json`: ON→OFF ownership trigger
  and pre-gate helper cleanup release the schedule marker without an equipment
  command. Every delayed/adoption claim checks the current master. Existing
  start/stop/source guards, Solar timers, quotas and accounting are unchanged.
* `ha_automations/sanitation_sessions.json`: existing live sanitation definition
  under version control; remove all master-switch writes. The existing schedule
  explicitly gates both sanitation flags and the native sanitation switch, and
  the preference controller gates the corresponding body's session. These
  existing priority signals suspend ordinary control without commandeering the
  operator's master switch. Restart/outage/timeout cleanup requires either
  sanitation flag ON, FTR02 ON, or the restored timer active/paused. Real cleanup,
  source-OFF checks, start-failure handling and three-hour limit are retained.
* Recovery fixtures, this document, and targeted regression tests.

There is no new controller, helper, dependency, speed change or PWA change.
Do not bulk-restore helper snapshots during deployment: the counter and live
safety/ownership state continue changing normally.

## Recovery baseline

Repository recovery tag: `recovery/manual-pool-ownership-20261017`, annotated
object `9c05a29e959281e9e52cb31d6923cb5908c03917`, points to exact main above.
Captured HA exports and helper configuration/state are also preserved on GitHub:
`recovery/manual-pool-ownership-live-20261017`, immutable commit object
`64d0ad63bd3063910993d31524894c9533a402d6` (tag object
`bda505c285467caeb62be1263577ec0d87751c9f`). Neither recovery tag is to be moved.

| Affected automation | HA config hash | Exact exported JSON SHA-256 |
|---|---|---|
|Schedule, id 1791536051066|33ada334cb3b5dde|17a6dce46e0f6cb409e8bd3bf6a00550de2202de582bf69995617a519c611c00|
|Preference, id 1791649697448|271dfe036cf6856f|d32a54840090b18cf5c6ea4e3ae68e8465eb07838613e6c08ba62bfc9c3f2c44|
|Sanitation, id 1792009120003|91bf0cb2cbf9f881|673c43d1f1dd8bdebcc87a989eed60c7f617e7aaf7d7461a9379e3e4f829c3b1|

`ha_automations/fixtures/manual_ownership_20261017/manifest.json` maps exact
entity IDs, filenames and hashes. SHA-256 covers exported UTF-8 JSON with a
terminal newline; HA hashes are the connector's separate configuration hash.

Supervisor lists protected completed backup `a3c40859`, October 17 05:20:54 PDT,
563,333,120 bytes, HA 2026.9.4 including HA and database on hassio.local. Additional
backup `ec2164e2`, October 16 15:25:43 PDT, includes HA/database on local and cloud
agents. Existence/content metadata verified; restore/decryption was not tested
because restore would restart live HA. Preserve the operator's encryption key.
No live change is authorized now, even with backups present.

## Validation and limits

* 251 controller tests pass, including 15 new tests: all manual schedule triggers,
  repeated cycles, midnight, 08:00 ledger reset, restored manual state, target
  change/manual OFF, source mappings, resumed ownership, delayed claim revocation,
  sanitation ownership and active restart cleanup, and the overnight reconstruction.
* Gateway tests execute the real production dispatch/allowlist/authority/outage
  checks with synthetic native IO. They prove zero Pool protocol writes from
  manual-mode schedule/preference actions, then prove manual OFF still delivers
  and automatic preference delivery remains possible.
* Existing Solar startup/loss/recovery, target satisfaction, filtration debt,
  Spa/sanitation/freeze/service/stale telemetry/Guardian/outage tests pass unchanged.
* 46 PWA Python tests and 4 frontend handoff/cache tests pass. Entire `standalone/`
  tree, bridge source, Guardian and outage definitions match baseline byte for byte.
* JSON parsing, compile checks and diff whitespace checks pass.

HA configuration reload/schema acceptance and physical/overnight acceptance are
pending. The replay is a strict limited interpreter, not HA itself. It does not
prove arbitrary cross-automation timing. An already-dispatched native command
cannot be retroactively cancelled by changing the ownership helper. Commissioning
must establish a settled handoff before manual heating is left unattended.

## Deployment after explicit approval

1. Require the PR's exact reviewed head green, then merge that head. Re-read all
   three live hashes against the table and capture a fresh backup/export if any
   configuration changed. Never overwrite unrelated operator edits.
2. With the operator present, verify fresh native state, no pending native write,
   recovery clear, no outage/simulation, and no active sanitation session. Record
   current master/claim/counter/target/source and safety states. Obtain explicit
   agreement for the handoff; do not silently change the master or equipment.
3. Save all three replacement configurations through the supported HA automation
   config API, retaining their existing IDs, aliases and enabled states. Apply
   sanitation ownership preservation first, then Pool preference, then schedule;
   these independently narrow interference rather than adding competing writers.
   API setters may reload automatically: treat each save as a live intervention.
   Do not trigger actions for validation. No integration/PWA update is required.
4. Read back full definitions and compare parsed JSON with the approved commit.
   Validate automation health/traces after any required automation reload. Avoid
   Core restart for this config-only deployment. A restart test requires approval.
5. Confirm ledger value is continuous (allow legitimate minute credits/08:00
   rollover), native presets unchanged, Guardian production permissions unchanged,
   safety authority unchanged. Perform the approved acceptance procedures below.

## Rollback after explicit approval

1. Preserve failure traces/history/current native state; do not erase Guardian
   recovery or reset counters. Use only the operator-approved safe procedure if
   physical intervention is necessary.
2. Retrieve the three original JSON files from commit
   `64d0ad63bd3063910993d31524894c9533a402d6` under
   `ha_automations/fixtures/manual_ownership_20261017/`; verify SHA-256 against
   manifest. Reapply them through HA's supported automation config API to their
   original IDs; preserve enabled states and read back the original HA hashes.
   Restoring old sanitation behavior reintroduces its ownership-reclaim defect:
   perform under supervision and do not promise overnight manual protection.
3. Revert the repair PR in a new reviewed repository commit if source rollback is
   needed. The main recovery SHA is a code reference, not a substitute for step 2.
   No bridge/PWA package rollback or preset rewrite is needed for this change.
4. If targeted configuration recovery fails, operator may restore backup
   `a3c40859` (or the verified appropriate backup) through HA Backups using the
   encryption key. This restarts HA and requires separate explicit approval.
   Re-observe native state/authority before resuming; do not blindly restore old
   counter, helper, outage or pump values from the diagnostic snapshot.

## Proposed supervised physical acceptance (not yet authorized/performed)

With reliable native telemetry, no active outage/sanitation/freeze/service mode,
normal RPM readbacks and Guardian recovery clear: operator selects Automatic
Ownership OFF and waits for no pending command plus claim OFF. Operator manually
starts Pool, selects native Gas and a safe target above water temperature.
Observe at least five minute reconciliations and a stabilized roof/preference
evaluation: Pool stays ON, source Gas and target unchanged; valid actual heater
and pump behavior. Confirm manual target adjustment and manual OFF. Exercise Spa
priority only within a separately agreed safe session. No simulated grid outage,
preset changes or heater-safety bypass. Any unexpected shutdown/source change,
stale telemetry, unsafe flow or Guardian recovery failure is a STOP; preserve
evidence and follow operator-directed safe state.

## Proposed overnight acceptance (not yet authorized/performed)

After the short test passes, operator establishes settled manual Gas heating
with master OFF. Capture start timestamp, target, actual temperature, source,
Pool/Spa state, native/physical RPM, master/claim, filtration counter/target and
all safety latches. Record history through midnight, multiple periodic evaluations
and 08:00 rollover. Pass requires no ordinary-automation Pool OFF/source/target
write or ownership ON; native thermostat may cycle heat normally. Count only
observed valid Pool-running minutes, cap at current target, and reset once at
08:00 while manual Pool circulation continues. Legitimate safety intervention
is authoritative and recorded, not a reason to bypass protection. Recheck manual
OFF and an explicitly approved return to Automatic Ownership ON using current
demand. No future transition is declared passed before observation.
