# Pool Cleaning: provenance evidence and default-OFF shadow arbitration

Scope: issue #158, first implementation increment. No new equipment-control
behavior. STOP before merge, deployment, HA reload/restart or commissioning.

## Inspected baseline and authorization

Main/base is `f2c26196720628381d83c68e1f597ce52250f146`.
The initial working tree had no tracked modifications; only existing Python
caches were untracked. Dedicated branch: `feat/cleaning-shadow-arbitration`.

Reviewed merged progression:

- #154 (`00cd474`): Stage A proposals only, no ownership/commands.
- #155 (`d9968e3`): corrected HA diagnostic category registration using
  `EntityCategory.DIAGNOSTIC`; retain that fix and the Stage A entity unchanged.
- #156 (`20806a3`): Stage B ownership contract, mandatory single authority,
  default OFF and prohibition on ambiguous cleaning-driven Pool OFF.
- #157 (`f2c2619`): pure `StartEvidence` and logical release gates; no dispatcher.

Governing documents are the operator-provided Autonomous Engineering Workflow
v3.2, Stage B ownership contract and issue #158. The current assignment expressly
limits implementation to passive/shadow behavior. PoolOS is retired; no PoolOS
code, dependency or authority is introduced.

Before changes, the full controller suite passed **336 tests**. No failures;
there is an existing unclosed-event-loop ResourceWarning in the baseline suite.
Baseline protection includes manual command/final gateway tests, native authority,
Spa interlock, scheduler/manual ownership, sanitation, Solar session, Guardian
anti-drift and durable recovery, native mapping, observation lifecycle/fanout,
Stage A callbacks and provenance gates.

Fresh HA configuration retrievals matched the complete committed October 24
originals by both API hash and exact JSON equality:

| Live automation | HA config hash | Inspected mode / authority |
|---|---|---|
| `pool_simple_solar_and_filtration_commissioning` | `59cd45a45d9f6452` | Enabled; queued; normal Pool circulation and ledger |
| `pool_and_hot_tub_heating_preference_controller` | `685e9fae5db6a85c` | Enabled; restart; body-specific heat-source selection |
| `sanitation_sessions_pool_and_spa_3_hour_limit` | `c74d5d703ca076d1` | Enabled; queued; existing sanitation session lifecycle |

Original full configurations and SHA-256 manifest remain in
`ha_automations/fixtures/cleaning_20261024/`; no candidate automation is installed
or proposed by this increment. Fresh local API exports are preserved under
`work/cleaning-stage-b-issue158/` in the task workspace.

## Actual command paths and boundary findings

| Path | What it can do / what is verified |
|---|---|
| HA/HomeKit/PWA climate actions | `ManualBodyThermostat.async_set_hvac_mode` → runtime transport proxy → `set_body_active(B1101/B1202, bool)`; existing `heat`/`off` semantics unchanged |
| Native bridge body gateway | `set_body_active` → `_send(request_changes, BODY, STATUS)` → `_confirm_body`; this is the sole integration body-status method found by source search |
| HA Solar/filtration automation | Direct Pool climate heat/off, Solar source, schedule/manual markers; minute reconciliation, 08:00 reset, valid running-minute credits, ten-minute manual grace and cleaning OFF-for-20s guard |
| HA sanitation automation | Pool/Spa body activation, heat-source OFF and guarded cleanup; its independent three-hour timer is not a cleaning ownership receipt |
| HA heating preference | Source selection, not a Pool circulation writer; respects cleaning/master gates for Pool, separate Spa policy |
| Grid safety / sanitation outage automations | Safety source OFF, Spa/accessory/sanitation cleanup and Guardian requests; they must retain independent authority |
| Guardian | Persistent native program configuration and recovery, not a cleaning body writer; unchanged |
| Native Pentair panel/app/schedules | Can affect body/feature state outside HA; HA config search and service contexts cannot exclude this authority |
| One-time 120°F handoff / seasonal schedule | Both observed OFF; one-time helper authority and duplicate historical schedule remain disabled |
| Pool-ready notifications / other scripts | No additional Pool circulation script found in the targeted configuration searches; notification is not circulation authority |
| New shadow diagnostics | Passive native and HA service-intent observation only; no body/RPM/feature command, helper or reconciliation event |

HA searches covered Pool thermostat, cleaning, schedule ownership, grid outage
and climate target writes; responses had no partial results or remaining config
pages. No matching Pool target-temperature automation/script writer was found.
These searches do not prove absence of an external panel/app/native schedule.

The transport dispatch lock surrounds freshness/connection, native write-arm,
legacy-integration exclusion, Guardian and outage gate checks and the controller
call. `_confirm_body` subsequently waits up to 25 seconds for a newer native
model snapshot showing the requested body field. The lock is released before
this confirmation loop. Controller-call completion is not physical flow or RPM
verification. The existing code does not expose a structured dispatch/ACK record
to these diagnostics, and a global model timestamp is not a per-body ACK.

The transport's “exclusive manual authority” check excludes the retired legacy
integration; it does **not** serialize operator intent at the Pentair panel with
HA automation decisions. HA schedule helpers and delayed ownership claims are
policy markers, not a receipt proving who started circulation. Its queued runs,
source preference restarts, manual climate requests and native transitions can
interleave. Cleaning release, Solar eligibility, filtration debt and safety can
also change during an action/confirmation delay. No new arbiter is inferred from
the transport lock or these helpers.

Read-only trace `d0e40aaccf0be22415f1070bc6311b91`, October 24 22:33 PDT, showed a
normal minute scheduler evaluation finishing without selecting an equipment
branch. This confirms accessible live execution, not exclusive authority or
coverage of a cleaning dispatch. The operator's Stage A ON/OFF physical tests
are accepted as baseline evidence for Stage A only. Cleaning-created circulation
and native 3000 RPM operation remain physically uncommissioned.

## Implemented increment and exact files

- `cleaning_shadow.py`: pure arbitration model plus a 16-record in-memory
  chronology. Composes the unchanged Stage A observer and uses the existing
  `evaluate_start_claim` logical model for explicitly supplied test evidence.
- `cleaning_shadow_sensor.py`: separate, optional read-only diagnostic adapter.
  `EntityCategory.DIAGNOSTIC`; disabled in the entity registry by default.
- `sensor.py`: two additions: import and register the new diagnostic entity.
  Existing entity constructors/identities remain unchanged.
- `tests/test_cleaning_shadow.py` and `tests/test_cleaning_shadow_sensor.py`:
  deterministic model, actual adapter callback and negative command-boundary
  coverage. No existing tests were weakened or removed.
- This report records findings, evidence limits and review/commissioning gates.

No transport, thermostat, switch, source, target, Guardian, preset, Stage A,
provenance-model, HA automation, PWA or CI policy code was changed.

### Passive evidence, not fabricated attribution

The optional diagnostic observes fresh native cleaning episodes and Pool
transitions, initial Pool state, interruption/reconnect and the first reported
running RPM per episode. Episode IDs combine a fresh boot UUID with a monotonic
local counter; restart never restores a previous claim or enable flag. Unknown,
stale, backwards, contradictory or wrong-identity evidence abandons continuity.

Its HA event subscription observes only `climate.set_hvac_mode`, `turn_on` and
`turn_off` requests explicitly targeting `climate.pool_thermostat`. These are
**HA service intent**, not proof of transport dispatch, device ACK or physical
execution. No user/context IDs, tokens or arbitrary event payloads are retained.
HA actor origin remains unattributed. Native Pool ON remains origin unknown even
if it follows such an intent. Redundant native-panel ON can produce no edge;
absence of a service event therefore proves nothing about manual intent.

Area/device targets, generic `homeassistant.turn_on/off`, external direct
transport callers and non-HA native requests are not fully attributable through
this adapter. It reports dispatch ACK “not observed”, exclusive writer/manual
exclusion “not attested” and physical verification false. It does not intercept
or alter the existing dispatcher to obtain stronger evidence. RPM telemetry is
not a preset readback, nor proof of cleaning flow or exact 3000 RPM operation.

The deque retains at most 16 structured records with no persistent storage.
Only chronology/decision/authority changes publish attributes; ordinary native
timestamps and RPM jitter do not create a Recorder stream. Unload and failed
partial subscription setup remove listeners. Existing telemetry remains the
source of continuous temperatures, RPM and debt values.

### Shadow semantics and permanent authority limits for this increment

`CleaningShadow()` defaults OFF. Production constructs it without an enable
argument; no HA option, service, switch, saved flag, mutator or dispatcher enables
it. Even enabling the optional diagnostic entity permits only passive listening.
Pure tests can explicitly instantiate an enabled evaluator.

An enabled evaluator can describe a hypothetical controller Pool ON request
only for a new observed FTR03 OFF→ON edge, with idle bodies, fresh clear safety
inputs and an affirmative current-episode controller/exclusive-writer/manual-
intent attestation. The production adapter supplies **no** such attestations.
Missing/ambiguous evidence cancels the proposal; it is not replayed when gates
later clear. Repeated samples do not duplicate start/handoff proposals.

Pool already ON is not claimed. Pool ON simultaneous with cleaning is ambiguous.
Pool OFF or observed competing/unknown HA request during the episode cancels
pending work. Spa, sanitation, freeze, outage, service, Guardian, auxiliaries,
master OFF and unknown safety inputs cancel work. Startup or reconnect ON is
observation recovery only. Reactivation cancels the old release episode.

Release uses the unchanged Stage A two-distinct-snapshot, >=20-second hold.
Even with complete hypothetical evidence, its only candidate is reconciliation
by the existing controller. Solar/debt context is never used to create another
planner or OFF command. The ten-minute manual grace is never bypassed.
`claim=none`, `pool_off_eligible=false`, `command_authority=false` and empty
`commands` hold for every model output. Even an accepted hypothetical
`StartEvidence` result grants no live claim or OFF eligibility. The older pure
`release_may_stop_pool` gate is deliberately not called.

## Regression results and coverage

Local full controller suite: **377 PASS** (336 baseline + 41 new).
PWA isolation: **46 Python PASS, 4 Node PASS**. Manifest/compilation/diff checks
pass. CI result and exact review head are recorded in the PR.

| Required scenarios | Evidence in new tests |
|---|---|
| Idle cleaning; preexisting Pool; simultaneous Pool ON | No live commands or claim; hypothetical request needs affirmative arbiter evidence |
| Release, native timer duration, early cancellation, retrigger | Same >=20s confirmation, no new timer, old release cancelled, one handoff proposal |
| Panel/manual ON during cleaning or immediately before release | Unknown origin; no OFF eligibility, including redundant/no-edge ambiguity |
| Solar yes/no, filtration due/satisfied/unknown, manual grace yes/no | Existing-controller-only handoff; no independent schedule, no grace bypass or OFF |
| Spa, sanitation, freeze, outage/recovery, service, Guardian, auxiliaries, master | Cancellation and no later replay of cancelled work |
| Restart, disconnect/reconnect, stale/duplicate/future/reordered/contradictory data | New epoch, default OFF, continuity discarded, no stale claim or replay |
| Missing ACK, delayed/expired/wrong-boot start evidence | No ownership; a complete simulated receipt also never grants live control |
| Repeated reconciliation and native RPM jitter | No duplicate hypothetical request, bounded chronology and publication |
| HA service callbacks, unload, partial setup failure, persisted opt-in attempts | Read-only fake bus/transport rejects command access; subscriptions clean up; flags remain OFF |

Existing suites continue to protect normal Solar startup, five-minute loss,
target satisfaction/reacquisition, filtration debt/night/reset, manual ownership
and grace, sanitation/Spa exclusion, Guardian/outage restoration/final gateway,
native maps/presets and all Stage A behavior. Source-isolation checks found those
paths byte-for-byte unchanged. Passing deterministic tests does not prove all
physical transitions or a new live diagnostic load.

## Unresolved evidence and smallest safe next step

There is no demonstrated shared arbiter spanning HA scheduling and native-panel
manual intent; no reliable native manual-takeover signal; no structured
controller-bound dispatch/ACK receipt; and no per-circuit freshness guarantee
from global model snapshots. A state context/helper/timestamp cannot fill these
holes. Automatic cleaning-driven Pool OFF remains prohibited.

After review, the smallest next increment is a separately approved passive
deployment of this optional diagnostic, followed by supervised observation that
compares actual controller traces/service intent/native transitions. This is
not permission for equipment stimulus or enabling arbitration. If actual ACK
capture is needed, propose and test a narrowly isolated, non-interfering receipt
hook on the existing single dispatcher in a separate change; do not add a new
writer. Its failure must not affect commands, and it still cannot prove absence
of native-panel manual intent. A real controller arbitration/manual takeover
contract must be demonstrated before any limited Pool ON commissioning; keep
OFF prohibited until that ambiguity is resolved.

No live changes occurred, so this increment requires no live rollback. Code
rollback would remove the optional new sensor registration and its modules after
an approved deployment; it has no saved claim/helper/timer to unwind. Current
HA originals remain restorable from their untouched evidence fixtures. Do not
merge/deploy/restart automatically. Physical Stage B is NOT RUN and NOT enabled.
