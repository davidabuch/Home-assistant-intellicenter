# Final recovery assurance and production activation readiness

Date: October 15, 2026, America/Los_Angeles. Governing workflow: GitHub + HA
Autonomous Engineering Workflow v3.2. PoolOS remains retired. Production
activation requires a separate explicit operator approval after readiness.

## Fresh baseline

At 17:40, remote main and installed revision both matched
f5483387bcced26b1d97d1e432d9cadf7934cc4a (PR #105). Guardian and running-write
approval OFF; no session, intent or restoration pending. Five native RPM programs
matched Pool/Spa2600, Sanitation3200, Heater3000, Solar2900. Real grid healthy,
simulation OFF, real-sensor mode ON, protection ON and bypass OFF. Pool/Spa and
actual heating OFF, pump0, master authority ON, schedule claim OFF. Freeze,
sanitation and accessories OFF; AUTO, fresh native observation. Accounting475/480.
All three ordinary controller/reconciliation automations ON with finished traces.
The old 15:13 thread-safety log entry is historical; no recurrence found.

## F1 — deterministic durable recovery

The new test file uses the actual guarded native transport and confirmation
methods with synthetic external I/O/telemetry. Reboots reconstruct the last
successfully persisted record, not a convenient copy of live memory. Every case
asserts native configuration and write behavior in addition to journal state.

| Case | Fault/window | Expected result, verified offline |
|---|---|---|
| F01 | Restart after durable intent, before dispatch | Native2600; no write; restored record clears on qualified return |
| F02 | Native accepted, ACK lost | Native1500 and dirty journal; restart restores2600 once |
| F03 | Gateway success, core verification interrupted | Durable intent still unverified; actual1500 restored after boot |
| F04 | Restart active outage | Matching1500 not rewritten; authority remains blocked |
| F05 | Restart after restoration accepted/ACK lost | Fresh2600 resolves pending recovery without duplicate write |
| F06 | Grid returns while write waits on native lock | Epoch/permit denies stale dispatch; native2600; no write |
| F07 | Outage recurs during restoration | Pending intent retained; current qualified policy wins |
| F08 | Native timeout | No unverified success; native and journal preserved |
| F09 | Communication loss and restart | No writes while stale; recovery retained until fresh restoration |
| F10 | SPEED changed but observation generation stale | Real confirmation loop rejects; dirty recovery persists |
| F11 | External native change, manual authority | No competing correction until automatic authority restored |
| F12 | Applied normal RPM changes during outage | Temporary1500 retained; current2700 restored after reboot |
| F13 | Repeated manual reconciliation in outage | One native outage write, no repeated writes |
| F14 | Guardian disabled while dirty | Native1500 and blocking recovery retained; no unauthorized write |
| F15 | Running approval revoked while dirty | Running restore deferred; safe idle restore permitted |
| F16 | Repeated grid flapping | One verified write per actual policy transition |
| F17 | Journal identifies wrong program | Fail closed, no native write, loaded=false and recovery held |
| F18 | Journal says outage; native already normal | Fresh native2600 resolves recovery without rewrite |
| F19 | Clean journal; native still outage value | Detect recovery, block normal authority, authorized restore2600 |
| F20 | Native restored; cleanup save interrupted | Last durable intent survives; native2600 resolves without rewrite |
| F21 | Twelve concurrent queued requests | Serialized; exactly one write per outage/restoration transition |
| F22 | Restart with unresolved restoration warning | Warning and native1500 retained until verified recovery |
| F23 | Intentional equal normal/outage values | No false recovery obligation |
| F24 | Unjournaled outage value with manual authority | Preserve manual authority; no write; retain recovery warning |
| F25 | Missing journal, native outage value | Detect restoration obligation even while writer disarmed |
| F26 | Recovery barrier plus nighttime schedule | No early start; restore, catch up remaining debt, stop at quota, reset08:00 |
| F27 | Recovery release plus current Solar demand | Quota does not stop viable heat; target stop/restart and Solar loss retained |

The complete suite passes214 tests, including all187 prior cases. Existing
priming/settling, heating-source selection, Spa/sanitation/freeze/service-mode,
manual ownership/bypass, target shutdown, Solar recovery, ledger/no double
counting, midnight debt and08:00 reset tests remain enabled.

### Defect found and repaired

F19 failed on the prior build. With a clean record and native Pool1500, the
Guardian treated that exact outage-value mismatch as ordinary drift. A running
normal correction deferred, while no durable restoration barrier was established.
The narrow fix recognizes native Pool equal to applied outage RPM but unequal to
applied normal RPM on normal grid. It durably records restoration_pending and a
session, blocks normal authority, and uses the existing guarded restore path.
Disarmed/manual/unsafe states do not authorize a write. Equal intentional normal
and outage policy does not produce a false alarm. No second writer was added.

## F2 — normal HA restart

HA VERIFIED at17:50 PDT after the authorized normal restart. Installed revision
5d463dfd59ac1290c47f5f579d399b4935ecb2ab matches PR106 and its green post-merge
CI run38831421930. Both approval flags remained false; session/intent null,
recovery false. Read-only Reconcile verified all five MATCH values, corrected6/
failed0 unchanged. Pool/Spa stayed OFF, pump0, roof83°F, ledger475/480 retained.
MasterON/claimOFF; normal automationsON; real grid healthy, simulation/outageOFF.
The17:50 controller trace completed with no equipment command. Startup guard
warnings resolved to fresh reads. No new Guardian thread-safety error appeared;
the15:13 entry remains historical. No equipment stimulus or preset write occurred.

All20 installed files were compared to the pinned merge after backup to
/config/local_backups/intellicenter_manual_pre_final_recovery_20261015_174718.
Both exact-head PR106 checks and post-merge CI passed. All214 tests passed.
Dashboard verification found the persisted prior outage result still labeled as
runtime verification even while Pool was OFF. Clarify it as last observed outage
result; do not erase valid historical evidence or pretend it describes current RPM.

## F3 — physical recovery decision

No additional hazardous physical fault injection is needed for this acceptance
scope. B–E already established native configured writes, new native readback,
running1500 response without cycling, verified2600 restoration before current
demand, and Solar2900 return. Deterministic tests now cover each durable cut point
and native divergence at the same real gateway boundary; F2 covers live HA boot.
Interrupting a real persistent write adds physical risk without testing a new
hardware contract. No live outage restart, interrupted write, communication fault
or deliberately stranded1500 test is authorized or performed here.

Residual risks: host/storage corruption can require operator recovery; an invalid
journal fails closed rather than erasing itself. Native controller power-cycle
persistence and quantitative flow certification remain untested. Existing fresh
telemetry, safety gates, verified readbacks and visible recovery barriers remain
mandatory. This is assurance for the tested envelope, not proof of all physical
failure modes.

## Natural operational evidence

Recorder: roof89 at17:27:24.128407, PoolOFF at17:32:24.990870,
pump0 at17:32:25.009975, claimOFF at17:32:25.145092. Ledger advanced one minute
per observed minute to475 and then stopped; target480 leaves five minutes debt.
This demonstrates natural Solar-loss termination and stable OFF with debt kept
for midnight. The retained source selection Solar is not actual heat delivery.
The brief trace ring no longer contains that termination run; history timing and
current config agree, but no missing trace is fabricated.

Midnight catch-up/completion, next08:00 reset and next eligible Solar restart are
pending future natural observations. Their offline regressions pass; they are
not claimed physically observed. A missed08:00 boundary across HA downtime remains
the pre-existing accounting limitation outside this targeted change.

## Activation authorization boundary

Keep both flags OFF until explicit final production approval. On approval,
configure enabled=true AND approve_running_pool_write=true through the intended
service, preserving normal floors and180-second settling. The latter flag is an
ongoing narrowly scoped capability required by pool_change_safe for running Pool
outage/restoration; it is not an arbitrary runtime-speed privilege. Normal preset
correction still requires safe idle equipment, and every write remains gated.
Setting enabled=true alone would leave running outage/restoration deferred.

Do not repeat physical D/E solely for promotion; their evidence is retained.
Any further physical outage simulation needs separate authorization. After
production activation, immediately verify flags, all presets, journal, ownership,
native state, dashboard and no contention. Continue read-only observation of
natural scheduled/thermal transitions; do not claim future events early.
