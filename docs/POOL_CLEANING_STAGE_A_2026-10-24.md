# Pool Cleaning activation and ownership handoff — Stage A

Status: observation-only implementation for review; STOP before merge/deployment.
No physical commands, HA configuration changes, restarts, feature enablement,
RPM writes, or commissioning were performed for this assignment.

## Authority, baseline and reconstruction

The governing workflow is GitHub + Home Assistant Autonomous Engineering
Workflow v3.2 (operator-provided October 8 document). The explicit Stage A
approval boundary overrides its default merge/deploy continuation. PoolOS is
retired. Its historical single-writer/cutover contract supplies context only;
its instructions to restore PoolOS authority are inapplicable. The October 23
AUX9 ownership contract remains design context. Its final paragraph claiming
HA has no cleaning guards is historical: the October 24 live configuration
already has guards and a 20-second release trigger.

Branch base / inspected main:
`5a46cf0ff7bbce07da1095d6ab90bfe7c7f6fff3` (PR #153).
Baseline controller tests: 283 PASS. Working tree had only untracked Python
caches before branching; no prior tracked edits were overwritten.

Live HA originals were retrieved before implementation and retrieved again
unchanged after implementation. Complete copies and file SHA-256 checksums:
`ha_automations/fixtures/cleaning_20261024/manifest.json`.
These are evidence originals, **not installation candidates**.

| Automation | Original and final HA config hash | Live state |
|---|---|---|
| Pool Solar/filtration | `59cd45a45d9f6452` | ON |
| Heating preference | `685e9fae5db6a85c` | ON |
| Sanitation sessions | `c74d5d703ca076d1` | ON |

Observed October 24 (America/Los_Angeles):

| Time | Native-facing HA history |
|---|---|
| 17:04:12 | Pool OFF; reported pump RPM 0 |
| 17:12:25 | Cleaning switch and binary sensor ON |
| 17:22:29 | Cleaning switch and binary sensor OFF |
| Throughout this cleaning interval | Pool remained OFF; no new pump-RPM state after 0 |

The preserved recorder extract corroborates the operator's idle-start failure.
It does not supply per-command receipts or per-circuit native timestamps.
Earlier cleaning at 12:05 occurred with Pool already running: reported RPM
changed from 2900 to 3038, then back to 2900 after cancellation. This is useful
historical telemetry, not a new cleaning-RPM acceptance test or proof of exactly
3000 RPM operation.

Confirmed cause: `PoolCleaningSwitch` calls `transport.set_pool_cleaning()`.
That method validates the unique feature identity, sends only the native
feature switch request and waits for observed confirmation. It never calls
`set_body_active()`. The commissioned body request is climate `heat` →
`set_body_active('B1101', True)`; climate `off` is body OFF. A feature ON alone
therefore does not request an idle Pool body, matching the observed failure.

## Control and ownership map

| Component | Current authority / interactions | Stage A disposition |
|---|---|---|
| Native panel/app, HA, HomeKit, PWA manual clients | Explicit body/target/source/feature requests through existing native/manual interfaces | Unchanged; no inference that Pool ON identifies its author |
| Bridge climate and transport | Body activation, target/source commands; existing freshness, final command gates and confirmation | Unchanged |
| Cleaning switch / native feature | Feature ON/OFF; native cleaning program and operator-reported native three-hour egg timer | Unchanged; no new timer or RPM request |
| Cleaning binary sensor | Read-only uniquely discovered native circuit state | Unchanged |
| Enabled Solar/filtration scheduler | Normal Pool body/source decisions, schedule/manual markers, service grace, filtration credits/reset | Unchanged; release gaps reproduced offline below |
| Enabled heating preference | Pool source with master/cleaning/freshness gates; independent Spa preference | Unchanged |
| Enabled sanitation sessions | Body/source/sanitation requests, existing HA three-hour sanitation timer, guarded cleanup and release event | Unchanged; its cleanup is not suitable as a cleaning template |
| Grid safety supervisor / detector / bypass / sanitation outage cleanup | Qualified outage authority, source OFF, Spa/accessory shutdown, Guardian reconciliation | Unchanged; cleaning cannot override safety |
| RPM Guardian | Sole guarded persistent program writer, recovery journal and restoration barriers | Unchanged; no new writer, mappings or allowlists |
| Native IntelliCenter | Mutual exclusion, flow/heater/freeze/service/priming protections and native program priority | Unchanged; configured RPM is not actual motor RPM |
| One-time 120°F handoff automation | Can change Automatic Ownership; currently OFF | Remains OFF |
| Older seasonal filtration automation | Duplicate historical scheduling; currently OFF | Remains OFF |
| New Stage A observer | Read-only proposals and suppression diagnostics | No command authority, helpers, events, timers or persistent claim |

HA configuration searches covered the Pool thermostat, cleaning, schedule
ownership, grid outage, target-write service, native body method and ID, with no
partial results or remaining pages. No automation/script target-temperature
writer was found by the service query. Pool-ready notifications do not command
circulation. These searches inventory accessible HA configuration, not external
Pentair schedules or every external client's intentions. The historical manual
ownership inventory provides additional context; it is not substituted for the
three freshly captured live configurations.

## Stage A semantics actually implemented

A separate diagnostic `Pool Cleaning Observer` sensor subscribes to the existing
native observation fanout and relevant HA policy changes. It adds no periodic
task. The existing integration refresh supplies stale-data reevaluation.

* Fresh observed OFF→ON, Pool OFF, Spa OFF and all diagnostic safety gates clear:
  propose `would_request_pool_on`. The intended future request is the existing
  normal body activation, preserving target/source/preferences. No request is
  executed. `claim=none`; `proposed_claim=only_after_verified_pool_start`.
* Pool already ON: `pool_already_on`; no redundant start or claim.
* Pool later becomes ON: `external_pool_activation`; Stage A did not send a
  command and cannot claim its consequence. Delayed/failed hypothetical starts
  are never reported as successful.
* Pool transitions OFF during cleaning: suppress the remaining episode. Do not
  repeatedly restart it. Spa, sanitation, grid, freeze, service, auxiliary
  demands, Guardian degradation and unavailable policy suppress proposals.
  This conservative diagnostic gate does not replace or weaken transport gates.
* OFF after observed ON: wait at least 20 seconds across two or more distinct
  native snapshot timestamps. Cache refreshes, HA policy changes and repeated
  identical receipts do not manufacture confirmation. An intervening ON cancels
  the old pending release. There is no separate three-hour cleaning timer.
* Settled release: propose only `would_reconcile_existing_controller`, subject
  to current authority. Never propose a direct cleaning-driven Pool/Spa OFF,
  change Automatic Ownership, claim circulation, or bypass manual service grace.
  Solar eligibility, nighttime filtration debt and shutdown stay with HA.
* Startup/reconnect while ON: report recovered activity without a start receipt;
  never replay a start. Startup/reconnect OFF has no historical release to replay.
  Unknown/disconnected/stale (>120s), future/backwards time, contradictory cached
  values or changed circuit identity discard continuity. No restored state is
  used to manufacture ownership. Lost continuity is diagnostic uncertainty,
  never permission to turn equipment OFF.

Diagnostics include phase, proposed action, reason, proposal identifiers, live
claim (`none`), proposed claim, safety suppression reasons, native identity/body
states and a decision-time context snapshot. `command_authority=false`, empty
`commands`, `physically_verified=false` and `bypass_manual_grace=false` are
invariant. RPM/context/timestamp samples are labeled as decision-time evidence;
ordinary native timestamp/RPM churn does not publish new observer states.
Existing telemetry entities remain the source for continuous measurements.

**Evidence limitation:** distinct `ReadObservation.observed_at` values are native
model snapshot updates, not independently timestamped acknowledgments for every
circuit. This is explicitly exposed in `release_evidence_scope`. Stage A's
settled-release proposal is not a production release authorization or proof
that native timer expiry physically occurred.

## Proposed HA changes — separate, not implemented or deployed

Offline replay of the actual originals establishes:

1. The scheduler performs ledger credit/reset before the normal-control gates.
   Valid cleaning circulation is still credited; cleaning ON with RPM 0 is not.
2. Its global ten-minute service gate precedes the cleaning OFF-for-20s gate and
   the branch chooser. Adding a trigger cannot bypass that gate safely.
3. `cleaning_released` is absent from adopted/unowned debt-completion and manual
   adoption trigger lists, explicit authority resumption, target-satisfied
   shutdown, Solar start/reacquisition and nighttime filtration lists. Later
   minute ticks may handle these; release is not a complete immediate handoff.
4. Heating preference already has `cleaning_released` and an OFF-for-20s guard.
   Its Pool preference writes resume after that guard; Spa policy is separate.
5. Sanitation release can issue body OFF and has its own session obligations;
   copying it would not preserve cleaning ownership.

The future minimal patch should use a **verified, session-bound cleaning-start
receipt**, checked by the existing scheduler, to allow only that episode past
manual grace and into current-state reconciliation after confirmed release.
The master and all safety/independent-demand checks must be rechecked immediately
before every equipment command. Add the confirmed-release reason only to the
necessary existing branches, retaining their current guards. Keep the ordinary
manual ten-minute grace intact; do not turn a read-only observer proposal into
an authorization event. Existing heating preference may need no logic change;
its release evidence and ordering must be verified alongside the scheduler.
No sanitation change is proposed.

This PR deliberately includes **no executable HA automation patch** or Stage B
switch. An unproven grace bypass would be a consequential authority change.

## Stage B ownership prerequisite / NO-GO

Stage B must not be enabled from this PR. A safe command implementation needs:

* A durable bounded transaction receipt written before dispatch, bound to the
  cleaning episode, uniquely verified idle Pool and the accepted body activation;
  failed/unverified writes cannot create a circulation claim.
* Restart reconciliation using fresh native evidence; no blind acquisition or
  cleanup replay. An ambiguous record protects existing circulation rather than
  authorizing its shutdown.
* Invalidation on manual OFF, new independent owners, Spa/sanitation/safety
  preemption, native identity or freshness loss, and failed verification.
* A trustworthy way to detect or explicitly define independent manual takeover
  during cleaning. An external panel can issue redundant Pool ON while already
  ON without an observable state edge. Existing thermostat ON/HA helper state
  cannot establish that provenance. HA service contexts alone do not cover
  native-panel/app requests. Do not invent an ownership bit that claims otherwise.
* Strong enough native release evidence to authorize the narrow grace exception;
  the present global model timestamp alone cannot prove every circuit's freshness.

No new persistent helper or journal is introduced in Stage A because no command
or real claim exists to recover. The eventual receipt is essential only once
actuation is designed. Until takeover and release evidence are resolved, automatic
cleaning-owned shutdown cannot be demonstrated safely. This is an identified
Stage B design/commissioning prerequisite, not permission to weaken ownership.

## Tests and evidence boundaries

At this review point: **332 controller tests PASS** (283 baseline + 49 added),
**46 PWA Python tests PASS**, **4 browser handoff Node tests PASS**. Existing
Python syntax/manifest gates also run in CI. The existing test harness emits
its pre-existing unclosed-event-loop ResourceWarning; tests pass.

| Evidence | Coverage / status |
|---|---|
| Pure observer tests | 24 tests: fresh/duplicate/delayed/unfulfilled proposals; preexisting/external Pool; manual OFF; early/native-timer-duration release; 20s confirmation; reactivation; Spa; restarts; gaps; stale/future/reordered/contradictory data; identity changes; authority suppression |
| Actual diagnostic sensor callbacks | 13 tests: fanout subscription/unload, strict read-only transport, forbidden HA service/bus access, policy gates, freeze/service/Spa, Guardian/grid, source/target context, release current context, no cached release fabrication, stale refresh, bounded publication and absence of command APIs |
| Exact live automation replay | 12 tests: original SHA-256 integrity, recorded idle failure, cleaning guards across all schedule triggers, 20s hold, grace preservation, release branch gaps, Solar/night catch-up on subsequent ticks, actual ledger commands/reset and preference actions |
| Existing full suite | Solar startup/loss/target/reacquisition, ledger/night/reset, manual grace/master, sanitation, Spa exclusion, freeze/outage/Guardian final gateways, durable RPM recovery/native mapping all retain their existing coverage |
| New live observer loading | NOT RUN: PR is not merged/deployed; sensor callbacks tested with HA-compatible stubs, not a running HA process |
| Actual cleaning Pool ON/OFF gateway and failed/late live writes | NOT RUN / Stage B: no actuation code exists in Stage A |
| Proven cleaning-start receipt, independent takeover and restart recovery | BLOCKED for Stage B as above; no fabricated physical acceptance |
| Cleaning RPM settling / native timer expiry / release physical cycle | NOT RUN for this build; no physical stimulus authorized |

The observer context tests intentionally do not implement a second Solar/debt
planner. Current inputs are handed conceptually to the existing controller;
only its unchanged configuration replay verifies its command intent. Green CI
cannot establish final physical cleaning acquisition/release acceptance.

## Review, deployment gate, rollback and commissioning proposal

Review the observer and evidence PR; stop before merge/deploy. After separate
approval for Stage A deployment, verify a restorable HA backup, exact package
SHA, original automation hashes and known-good installed integration copy.
Install only the approved observer build through the established workflow; do
not install the evidence fixture JSON or change controller configuration.
Verify the diagnostic entity loads, normal entities remain healthy, and its
proposals/claims match passive observations. A reload/restart needs its own
approved maintenance envelope; none was performed here. Rollback restores the
saved integration package through that workflow and verifies original entities;
there is no new claim/helper/timer or HA configuration to unwind.

Only after the Stage B evidence/ownership prerequisites are resolved and the
operator separately authorizes physical commands:

1. Fresh safe baseline: native preset readbacks, Guardian normal, outage/freeze
   inactive, service AUTO, Spa/sanitation/auxiliary demands absent, native data
   fresh. Confirm intended source/target; do not change them merely for cleaning.
2. Idle Pool/Spa: operator activates cleaning through the actual Pentair feature
   path. Verify exactly one normal Pool body request with its durable receipt,
   native Pool ON, normal priming then cleaning RPM; allow up to three minutes
   for normal settling, otherwise STOP and investigate. No direct RPM writes.
3. Cancel cleaning. Verify fresh OFF evidence and >=20s hold, then the existing
   scheduler's decision/receipt: Solar with demand continues; nighttime debt
   retains circulation; otherwise only proven cleaning-owned circulation stops.
   Verify settled physical outcome within three minutes after the release hold.
4. Repeat separately with Pool preexisting, manual takeover, manual OFF and Spa
   priority; no redundant starts, stolen ownership or unrelated OFF requests.
5. Supervise one native timer-expiry cycle (three hours plus the release hold
   and <=three-minute settling window), then verify legitimate reacquisition.
   Do not add a software timer or simulate expiry by assuming elapsed time.

STOP on stale/contradictory telemetry, failed/unverified request, unexpected
shutdown/restart, lost manual authority, heater/flow/safety concern, unexpected
RPM writes, or failure to release. Operator cancels the cleaning stimulus using
native controls; only independently justified equipment commands may follow.
Preserve receipts and recovery evidence; never force Pool OFF to clear an
ambiguous claim. Neither these steps nor the Stage A PR authorizes execution.

Final read-only HA check: Guardian NORMAL, enabled and guarded running-Pool
permission true; recovery not pending; failed writes 0; all six configured
programs read 2600/2600/3200/3000/2900/3000. Pool OFF, Spa HEAT, actual RPM 2600;
cleaning OFF; grid simulation OFF, real sensing ON, outage OFF. Three reviewed
automations ON and unchanged. Guardian's `installed_commit` reports
`development`, so the exact loaded commit cannot be independently certified
from that field. No Stage A code is claimed deployed or physically accepted.
