# Solar RPM and adopted manual circulation — October 20, 2026

Engineering candidate, not deployed or physically commissioned. This assignment
authorizes code, offline tests and PR/CI only. No HA automation/helper writes,
native commands, preset changes, restarts, or physical tests were performed.
Merge/deployment and physical commissioning require explicit operator approval.
PoolOS remains retired. There is no additional equipment controller or writer.

## Baseline and live/source divergence

Main: `d1e29cfdf9057b0b9d7058bb5576bf09fe09fc14` (PWA v0.1.33).
Feature branch: `fix/solar-demand-manual-filtration`.
Bridge installed revision reported by HA:
`966767a3607ea1722284b6651c86dcc22a8b68b5`.
Exact live definitions, including IDs and config hashes, are preserved in
`ha_automations/fixtures/solar_session_20261020/`.

| Live component | Hash at inspection | Source disposition |
|---|---|---|
|Pool schedule|`f1897c0d1e1ab60e`|Start from live sanitation-release handling; replace provisional cold-only branches with the tested policy below|
|Guardian reconciliation|`4560b9a2ae1bbc77`|Preserve live ID; use independent Solar-delivery signal for the transition and fix reason classification in integration|
|Sanitation sessions|`c74d5d703ca076d1`|Sync exact live cleanup/release-event behavior, unchanged; do not overwrite it with the October 17 version|
|Heating preference|`b67810629de5881f`|Unchanged|

The provisional schedule's cold-only branches were appended to a first-match
choose list, after existing reconciliation branches. They require roof <90 F,
so they do not cover warm-roof/nonheating sessions. The debt branch can adopt
immediately, allowing an existing owned-session shutdown to bypass the nominal
ten-minute grace on the unowned debt-zero branch. Its negated numeric comparison
also lacks positive validation of both ledger inputs. These are configuration
findings; the branches have not been physically commissioned.

Live sanitation has additional guarded Pool cleanup and emits
`intellicenter_sanitation_released`. Those changes are preserved byte-for-byte in
the new source artifact and exercised by regression tests. No other automation,
native preset, source mapping, dashboard, PWA, or seasonal schedule is changed.

## Incident reconstruction and root-cause confidence

All times below are October 20, PDT (America/Los_Angeles).

| Time | Native/HA evidence |
|---|---|
|08:08:26.295|Pool changes OFF → HEAT|
|08:08:41.199–08:08:50.349|Read-only **p0102 Pool configured RPM** moves 2600 → 2630 → 2720 → … → 3010 → 3000|
|08:09:05.221|Actual motor settles at 3000 RPM|
|09:33:52.242|Existing Solar-active sensor changes ON|
|09:38:00.398|Schedule ownership changes ON|
|10:33:55 / 10:34|Operator reports button/service reconciliation; 3000 RPM persists|
|12:53 inspection|Pool HEAT, Spa OFF; p0102 **3000**, p0104 3000, p0105 2900; motor 3000; Guardian applied Pool target **2600**, pending routine Pool correction **2600**, result DEFERRED, zero failed writes|

The important missing observation in the incident summary was the changed Pool
preset. It is persistent PMPCIRC SPEED, not merely physical RPM or a selected
heat source. The service person may have adjusted the native slider, but HA
history does not identify the actor. Timing alone is not proof of attribution.

Pentair's [IntelliCenter troubleshooting guide, page 2](https://flowandfiltrationsolutions.pentair.com/content/dam/extranet/nam/pentair-pool/residential/automation/intellicenter/faq-documents/archive/IntelliCenter-Trouble-Shooting-Guide.pdf)
documents highest-speed selection for multiple assigned RPM circuits, GPM
priority over RPM, and separate freeze-speed behavior. Therefore active Pool
circulation assigned 3000 RPM is sufficient to explain why a 2900-RPM Solar
assignment cannot lower the pump. Heater p0104 need not be stuck active to
explain this incident. Its stored 3000-RPM value alone does not prove it is active.
An additional Heater/auxiliary demand cannot yet be excluded.

Reconcile Pump Speeds did not fail a write: its ordinary-write policy deliberately
requires idle Pool and motor <500 RPM. Manual/button reconciliation detected the
Pool mismatch, durably queued 2600, and deferred it while running. The running
approval flag permits only commissioned outage/restoration phases, not general
running anti-drift writes. It must not be broadened to force a Solar transition.

The newly added `solar_delivery_started` reason was absent from ROUTINE_REASONS,
so it was classified as recovery: reads and existing obligations, not new drift
discovery. Adding the reason fixes event discovery, **not** the running motor.
Current heartbeat already retries established obligations but never discovers
new ordinary drift. That distinction is retained.

Exact historical Guardian traces around 10:34 have expired (only five recent
minute traces remain). User-reported button timing is physical/operator evidence;
current pending state and code explain deferral. It is not represented as a
recovered button execution trace or a verified command to the motor.

## What the current Solar sensor proves, and what is missing

The deployed library `pyintellicenter==0.1.20` uses BODY HTMODE != "0" for heating.
The bridge combines that body-heating indication with BODY HEATER selection to
publish Solar-active. It does not merely check selection, but it also does not
independently read X0052 or use HTSRC as delivery attribution. The existing
sensor's name therefore must not be taken as proof of the virtual circuit's
state or hydraulic delivery. Its commissioned behavior is left unchanged.

A new read-only `binary_sensor.solar_delivery_confirmed` requires both fresh
native X0052 ON and native body-heating/source evidence. Missing/unknown X0052
makes it unavailable; selection or the legacy sensor alone cannot assert ON.
The existing Solar-active sensor is unchanged. The Solar reconciliation trigger
and adopted-session promotion use this stronger signal. It confirms native
indications, not hydraulic flow. Verify its actual entity registry ID and native
circuit availability before enabling the candidate automation.

The new read-only `pump_demand` Guardian attributes expose:

* Every PMP01 assignment, including extra/unknown RPM or GPM assignments;
  native identity, associated circuit, configured RPM, and circuit ON/OFF/unknown.
* X0051 and X0052 evidence independently of selected source, plus raw BODY
  STATUS/HEATER/HTMODE/HTSRC/MANUAL/MANHT/SPEED and observation timestamp.
* Known active maximum and effective RPM only when the complete demand inventory
  is known. Missing/invalid/duplicate identity, unknown circuit state, stale data,
  extra unknown assignments or GPM do not produce a Solar verification claim.
* SETTLING, SAFETY_PREEMPTED, SOLAR_CIRCUIT_UNCONFIRMED,
  INCOMPLETE_NATIVE_DEMAND, HIGHER_PROGRAM_DEMAND, runtime mismatch, or verified
  Solar RPM after native settling (50-RPM diagnostic tolerance).

This is a cached-model inspection; no diagnostic command, toggle or writer is
added. Existing Guardian publications/heartbeat refresh the display. Runtime
matching is never used as configuration-write authority. Existing runtime_status
is explicitly labeled `outage_only`; the old VERIFIED value was a historical
outage result, not proof of normal Solar RPM.

Exact X0051/X0052 status is not exposed by the deployed entities, so it cannot be
claimed observed in this investigation. The diagnostics must first be installed
under separate deployment authorization to obtain that evidence. Even correct
native indication does not certify real valve position or water flow; that is
physical commissioning evidence.

No supported independent speed-override release was identified in the deployed
library. Pump-circuit SPEED changes are persistent configuration changes. The
bridge continues rejecting direct runtime RPM writes. It does not turn Pool
OFF/ON, toggle virtual heater circuits, or rewrite the Solar preset to counter
the elevated Pool preset. A running drift is queued until safe idle. If the
operator requires immediate running correction, a separately engineered and
physically authorized mechanism is needed; this PR does not claim one exists.

## Deterministic manual-session policy

One HA-restored passive marker, `input_boolean.pool_simple_manual_circulation`,
distinguishes adopted filtration from a normal scheduled/Solar session. It is
not operator authority, a controller, or a timer. The existing master remains
the only ordinary automatic/manual authority boundary. No initial value is
forced on reload: HA restores the marker, while a new helper defaults OFF.

1. New unowned native Pool HEAT gets ten minutes of service grace before **all
   ordinary schedule equipment commands or claims**, not just debt-zero cleanup.
   Accounting continues. A periodic tick acts at/after ten minutes (up to one
   additional tick); it is not an immediate command at Pool ON. This is a bounded
   policy proposal retaining the provisional duration, not physical acceptance
   of ten minutes as sufficient for every service visit. Longer intentional
   service requires Automatic Ownership OFF.
2. After grace, with current master/safety/native evidence valid and no competing
   circuit, running manual circulation with remaining debt is adopted without an
   ON/OFF/source/RPM command. It is not limited by calendar or roof temperature.
3. The restored marker lets filtration-only circulation survive satisfied thermal
   target and 08:00 rollover. Verified circulation still uses the existing capped
   minute ledger and the sole 08:00 reset. Unknown/negative/nonfinite ledger
   inputs cannot be incremented or treated as proof of completed debt.
4. Once debt is zero, a manual-origin or unowned session ends only after grace,
   with positive ledger validation, fresh native evidence, known Solar absence,
   no eligible thermal Solar demand, and all existing safety/auxiliary guards.
   OFF is awaited before releasing both ownership and the passive marker.
   A command/receipt failure retains the markers for recovery.
5. Confirmed native Solar delivery plus native Pool source Solar promotes an adopted session
   to existing Solar handling by clearing only the passive marker. The existing
   five-minute Solar-loss / Eco Heat policy, target-satisfied shutdown, recovery,
   and legitimate Solar heating beyond filtration quota then remain in force.
   An already Solar-heating unowned session is adopted by the existing Solar
   path after service grace. No selection-only runtime verification is claimed.
6. Pool OFF or master OFF clears the passive marker without equipment actions.
   Master OFF still permits counting/reset but prevents ordinary equipment writes
   and automatic claims. Spa, sanitation, freeze, service mode, outage, Guardian
   barriers and active auxiliary circuits preempt ordinary decisions.
7. The marker and existing claim restore across HA restart during an adopted
   session. A new/unowned restored state receives a conservative fresh grace
   window because HA state duration restarts. A missing/unavailable marker fails
   closed for equipment decisions until the helper is correctly installed.

No new automatic Pool start path is introduced. After debt-completion OFF there
is no restart without legitimate current thermal or next accounting-day debt.
Daytime manual OFF before completion releases the claims. This does not invent
a permanent manual-OFF suppression while master is ON: an existing legitimate
nighttime catch-up can still start later. Master OFF is the explicit boundary
for lasting manual control. HA cannot reconstruct an unobserved OFF/ON episode
during a communications outage from a restored boolean alone; that edge still
requires conservative operator review and is not claimed physically commissioned.

## Changes and validation

Code: `pump_demand.py`, independent read-only Solar delivery observation/sensor,
transport evidence/subscriptions, HA adapter and
Guardian sensor attributes; add Solar transition reason to routine event set.
Automations: source sync of live Solar trigger and sanitation release behavior;
schedule changes above; one helper-creation argument artifact. No native writer,
command allowlist, RPM floors, durable transaction phases, running permission,
outage/restoration protocol or PMPCIRC identity gate is weakened.

276 controller tests pass (25 additional tests grouped across the requested
25-case matrix), plus 46 PWA Python tests and 4 frontend tests. All existing
controller tests remain passing. JSON parsing, Python compilation and diff checks
pass. PWA, number/button/select interfaces and configured target RPMs are unchanged.

| Requested cases | Evidence level / assertion |
|---|---|
|1–5 Solar transition/already active/preset vs runtime/higher demand/inactive X0052|CODE TESTED: pure native-demand calculation; no motor/config writes|
|6–8 manual RPM/repeated observations/ON-OFF-ON|CODE TESTED: actual Guardian/native gateway rejects running normal correction; no heartbeat discovery, one deferred idle correction, settling and read-only transitions|
|9–15 manual debt/grace/winter/summer/Solar promotion/loss|CODE TESTED: replay actual HA artifact, ledger and explicit equipment-command intent|
|16–20 manual authority/Spa/sanitation/freeze/outage|CODE TESTED: new priority matrix plus existing native policy/outage/recovery suites|
|21–24 restart/manual OFF/target/stale or rapid changes|CODE TESTED: restored marker, release/quiet window, existing thermal behavior and fail-closed evidence|
|25 command failure/delayed settling|CODE TESTED: real native dispatch and fresh OFF receipt awaited before cleanup; timeout retains markers; runtime diagnostic waits for settling|

Replay is a strict limited interpreter, not the HA engine. Pure expected-demand
tests cannot prove this installation's actuator or firmware behavior. No live
configuration or physical acceptance is established by these passes. The raw
body subscription fields are protocol-library fields, not new control semantics.

## Approval-gated deployment and rollback

Before any live step: explicit operator approval, current backup/export, exact
approved green SHA, live hash comparison against the baseline fixtures (do not
overwrite concurrent edits), fresh telemetry, recovery clear, settled idle safe
state and operator supervision. The service-session policy and helper are new
and must be explicitly accepted before activation. The older seasonal schedule
must stay OFF. Preserve all production Guardian permissions.

Install the passive helper using `manual_circulation_helper.json` through the
supported helper API. Verify exact ID and restored OFF baseline; never silently
reset an already existing active marker. Deploy the reviewed integration build
through the established installation process only when authorized; any required
HA integration reload/Core restart needs explicit approval. Startup reconciliation
can actuate through existing policy when safe: this is not a read-only deployment.
Verify `binary_sensor.solar_delivery_confirmed` is present with trustworthy X0052
evidence before installing the reviewed Guardian and schedule definitions with hash locking,
compare parsed readbacks, health and normal traces after each. Sanitation is
already live at the captured definition; verify and skip a redundant save.

Rollback: preserve traces/native observations and the journal, restore the exact
previous integration build and original Guardian/schedule definitions from the
October 20 fixtures through supported APIs. Do not substitute October 17
sanitation. Keep the helper until no candidate definition consumes it; only then
remove it if explicitly approved. Never reset filtration or recovery to diagnostic
snapshot values. A full HA restore/restart is a separate authorization boundary.

## Proposed low-risk physical commissioning — NOT AUTHORIZED / NOT RUN

1. Obtain separate approval for deployment, supervised physical commands and the
   specific timing. Capture all circuit/thermal/native program/demand diagnostics,
   raw source fields, master/claims/marker, counter/target, Guardian journal and
   permissions. Stop for stale/contradictory observations, outage/freeze/service,
   active sanitation/Spa/auxiliary demands or unresolved recovery.
2. To recover today's elevated Pool preset, operator ends circulation once, only
   when native heater cooldown/flow requirements permit. Wait for native Pool OFF
   and actual motor 0; do not cycle repeatedly. Invoke the existing guarded
   reconciliation at safe idle and verify p0102 restores approved **2600** while
   the other four programs remain 2600/3200/3000/2900. Stop on failed/unverified
   write. No direct live-RPM command or forced virtual-circuit toggle is permitted.
3. With approved presets, safely initiate a Solar-eligible Pool session. Observe
   actual delivery, X0052 and X0051 evidence, all active program demands and
   native priming. Allow at least the configured 180-second settling interval
   after the latest transition. Expect 2900 only if no higher RPM/GPM/freeze
   demand exists. Verify actual RPM against the complete demand report. Capture
   readings before/after one manual reconciliation; do not infer success from
   MATCH or an accepted service call alone. Stop and inspect if unstable or
   contradictory after five additional minutes; do not force or blindly retry.
4. On a naturally non-Solar day, or with separately approved safe heating intent,
   initiate an unowned Pool session with master ON. Verify the first ten minutes
   remain unclaimed/uninterrupted while valid circulation credits accrue. Verify
   one helper-only adoption if debt remains. Use naturally near-complete debt;
   do not change/reset the real ledger merely to shorten a test.
5. Observe debt reaching zero: one native OFF intent, fresh OFF receipt, both
   claims cleared, motor 0 after normal native transition, and no automatic
   restart over several ticks without a new legitimate demand. Separately, with
   debt already complete, verify grace through ten minutes then guarded OFF at
   the next tick. Master OFF must prevent either ordinary shutdown/adoption.
6. Observe natural Solar arrival during adopted filtration: promotion without
   Pool cycling, correct effective demand, heating beyond quota where needed,
   qualified Solar-loss termination and stable post-stop state. Verify 08:00
   rollover without resetting a manual-filtration session prematurely. HA restart
   testing, grid simulation and fault injection require separate authorization.

Maximum expected debt-zero grace test is eleven minutes plus native shutdown
settling. Debt-remaining tests may require hours of real accounting; those are
pending observations, not a reason to edit thresholds. Operator cancellation,
unsafe flow, unexpected shutdown, manual authority overridden, failed preset
restoration, command contention or unreliable native data is an immediate STOP.
Preserve evidence, follow only the operator-approved safe recovery procedure,
repair through the same PR/CI process, and repeat only the affected acceptance case.
