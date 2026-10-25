# RPM Guardian missing-service repair — lifecycle investigation

Status: implementation and offline regression verification; review PR only.
No merge, live configuration change, deployment, reload/restart, Guardian service
execution or Pentair command was performed in this assignment.

## Baseline and live evidence

Base main: `aad00c97c1f02f5f161909f07b0c30acbca1c69e` (merged #159).
Branch: `fix/guardian-service-lifecycle`. No tracked local edits preceded this
branch; existing untracked Python caches were preserved. Baseline: **377
controller tests PASS**, with the existing unclosed-event-loop ResourceWarning.

Read-only HA inspection reported Core **2026.10.2**, the seven IntelliCenter
service descriptions, and five successful reconciliation traces from October
24, 23:09–23:13 PDT. The operator separately supplied actual WebSocket registry
and successful direct-call evidence; no direct service call was repeated here.
The retained system-log entries available now do not include the earlier
missing-service error. They cannot establish its exact wall-clock ordering.

Reconciliation automation was retrieved intact, hash `fb8228fbe53cab17`:
`intellicenter_manual.reconcile_pump_speeds`, exact entry ID
`01M4F1DFGA4AH4F9E9M7MJCR5Q`, and reason
`{{ trigger.id | default('manual', true) }}`. Queued mode/max 3; original startup,
minute recovery, grid, scheduled, session, Solar and cleaning-release triggers
are unchanged. No live or repository automation artifact was edited.

Final read-only check: automation still ON and exact config/hash unchanged;
Guardian NORMAL, enabled and running-Pool approval true, failed writes 0,
recovery not pending. Pool/Spa/cleaning OFF. Native readbacks remain Pool 2600,
Spa 2600, Sanitation 3200, Heater 3000, Solar 2900, Cleaning 3000 RPM. These are
observations of the existing deployed build, not deployment proof for this fix.

## Confirmed failure mechanism

The pre-fix source registers domain services with a config-entry lifetime:

- [Base `GuardianHA.setup`, lines 157–181](https://github.com/davidabuch/Home-assistant-intellicenter/blob/aad00c97c1f02f5f161909f07b0c30acbca1c69e/custom_components/intellicenter_manual/rpm_guardian_ha.py#L157-L181)
  awaits revision lookup, durable load and startup-scan persistence first.
- [Base lines 227–232](https://github.com/davidabuch/Home-assistant-intellicenter/blob/aad00c97c1f02f5f161909f07b0c30acbca1c69e/custom_components/intellicenter_manual/rpm_guardian_ha.py#L227-L232)
  then register all four Guardian services and add unconditional per-entry
  `async_remove` callbacks.
- [Base integration setup](https://github.com/davidabuch/Home-assistant-intellicenter/blob/aad00c97c1f02f5f161909f07b0c30acbca1c69e/custom_components/intellicenter_manual/__init__.py#L122-L138)
  calls `GuardianHA.setup()` before assigning runtime data and starting native
  transport/platforms. There was no component `async_setup` service registration.

Deterministic event ordering:

1. Successful old entry setup registers `reconcile_pump_speeds`; a heartbeat
   request succeeds.
2. Integration unload succeeds. Core runs entry unload callbacks, including the
   unconditional service removal. The separate HA automation stays enabled.
3. Reload starts a new `GuardianHA.setup()`. It suspends on revision/storage IO;
   the service has not been re-registered.
4. A heartbeat or other automation trigger calls the missing service. Registry
   lookup raises `ServiceNotFound`, matching the operator's reported exception.
5. New setup completes and registers it. Later identical requests succeed.

This is a real registration gap, not proof of a permanently missing service,
a YAML naming mistake, or a broken reconciler. Its duration depends on setup
work; no arbitrary delay is needed to reproduce it.

### Reproduction and fidelity

`test_guardian_service_lifecycle.py` executes actual adapter setup, registered
handlers, unload callbacks and the new component-hook body. Only external HA
registry/config-entry/storage boundaries and native IO are substituted. The
fixture models Core's dictionary service lookup, loaded-entry validation and
LIFO unload ordering; it does not run a complete HA server or real automation.
A controllable event holds setup at the real revision-lookup await. There are
no timing sleeps, sockets or equipment writes.

Against base code the initial 13 targeted tests produced **5 assertion failures
and 6 errors** (2 passed). The preserved pre-fix output includes
`Action intellicenter_manual.reconcile_pump_speeds not found` after unload;
`test_reload_gap_service_remains_registered_during_initialization` also fails
because the registry is empty at the held setup boundary. Releasing the setup
barrier re-registers the service; subsequent requests succeed. With the fix all
16 final lifecycle tests pass. Local pre-fix evidence is preserved in the task
workspace at `work/guardian-service-lifecycle/before-fix-tests.txt`.

### Core behavior checked, not assumed

The official 2026.10.2 release source was downloaded read-only and inspected:

- [Config entry reload](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/config_entries.py#L2596-L2631)
  holds the same entry setup lock, awaits unload, then setup.
- [Entry cleanup](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/config_entries.py#L1131-L1144)
  executes unload callbacks before deleting runtime data; failed entry setup
  also runs callbacks. [Callbacks are processed LIFO](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/config_entries.py#L1333-L1341).
- [Registry registration/removal](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/core.py#L2750-L2832)
  replaces/removes the domain/name handler. Removal carries no instance token.
- [Component setup](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/setup.py#L405-L480)
  runs integration `async_setup` before config-entry setup.
- [Automation enable](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/automation/__init__.py#L847-L866)
  normally defers initial triggers to startup jobs; an ordinary successful cold
  boot is not automatically proof of an automation-before-service race.

**Not the confirmed historical cause:** a late old callback removing the new
same-entry registration. Core's normal reload lock/order prevents that ordering.
The old callback was unconditionally destructive if artificially replayed, and
the old implementation also let a second entry overwrite the first entry's
handler. Tests cover both defensively, but no evidence shows either occurred at
this installation.

## Minimal fix and failure semantics

Only two production files change:

1. `__init__.py`: add config-entry-only `CONFIG_SCHEMA` and a component
   `async_setup` that registers the four Guardian services synchronously before
   entry IO. It neither creates a transport nor issues commands.
2. `rpm_guardian_ha.py`: register stable component-owned handlers, remove the
   four per-entry service registration/removal callbacks, and resolve the exact
   entry at invocation through HA's `service.async_get_config_entry` helper.
   Existing operation bodies are exposed through `GuardianHA.service_handlers`.

Each handler requires an explicit entry ID; the standard helper validates
existence, domain and `LOADED` state. Missing/partially loaded/unloading runtime
raises a visible `ServiceValidationError`. No unavailable request is silently
accepted, deferred or replayed against a later runtime. The next existing
heartbeat services the current recovered state. The existing persisted startup
scan is still queued during setup; normal startup/outage recovery policy and
initialization settling are unchanged.

The require-entry/reconcile/inspect/apply/configure function bodies compare
identically as Python AST against base. The Guardian core, native writer,
conditions, flow floors, service inputs, confirmation text, reason classification,
write gates, persistence and exceptions are unchanged. Actual Guardian failures
propagate. No repair issue is deleted and no error is swallowed.

The three existing manual/diagnostic services remain entry-scoped; moving them
is unnecessary for this warning and outside this correction. During reload only
the four Guardian domain services are guaranteed to remain registered.

This follows HA's [component-level action registration guidance](https://contributors.home-assistant.io/core/integrations/actions/#register-actions-in-async_setup),
which explicitly recommends keeping actions available without a loaded entry.
[HA's entry helper](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/helpers/service.py#L1347-L1386)
reports an unloaded target explicitly rather than pretending an action is absent.

## Regression protection

Full local results: **393 controller tests PASS** (377 baseline + 16 new),
**46 PWA Python PASS**, **4 Node PASS**. Compilation, JSON manifests and diff
checks pass. CI results and exact tested SHA are recorded in the PR.

New tests exercise component startup before entry IO; held startup/reload
initialization; successful setup; unload/repeated reload; revision/storage setup
failure and recovery; exact multi-entry routing; missing/wrong-domain/unloaded
entry; old callback replay; close concurrent requests; no stale replay; retained
startup-scan obligation; apply/inspect/configure authorization/freshness; and
unmasked Guardian failures. Unexpected native IO raises immediately in the
fixture; setup/unavailable-path tests assert no native calls.

The existing callback test fixture now performs component registration, retaining
all original listener/reason assertions. The existing lifecycle assertion now
includes the new `async_setup` hook and additionally checks that its only call
is service registration, with no await or equipment action. No test was deleted
or weakened to conceal a regression.

Transport, Pool/Spa climate control, Guardian core, Solar/filtration/manual grace,
HA automation artifacts, sanitation/safety policy, pump presets/maps, PWA and all
Cleaning Stage A/provenance/shadow files remain byte-for-byte unchanged from base.
The existing suites continue to verify their command and prohibited-command
behavior. No new Cleaning authority, ownership claim or physical action exists.

## Persistent Repairs warning and remaining uncertainty

Core catches automation `ServiceNotFound` and creates an [issue with
`is_persistent=True`](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/automation/__init__.py#L789-L811).
The successful-run path returns without deleting that issue. The issue registry
[restores persistent issues](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/helpers/issue_registry.py#L261-L305)
across HA restart. Service registration does not clear it. Thus an old repair
remaining visible after successful calls or after restart is expected and does
not prove a fresh startup failure.

The unavailable historical log/trace ordering prevents proving which trigger
hit which reload, whether a cold-start setup retry also contributed, or whether
the post-restart report referred solely to the restored issue. The confirmed
reload/entry-failure mechanism is reproduced and corrected; ordinary successful
cold boot is not claimed as an independently proven incident cause. The fix also
keeps services registered across failed/retrying entry setup once the component
has initialized. It cannot register anything if the entire integration module
cannot import or its component setup fails; those would remain genuine failures.

No new structured logging is needed to infer past events. A future authorized
verification should record registry service_registered/service_removed events,
entry lifecycle state and automation run IDs across one controlled reload if
more timing evidence is required. Never log credentials or modify triggers.

Do not expect this integration fix alone to automatically remove the already
persistent warning. After successful authorized deployment and verification,
request separate authorization to resolve this specific repair through Settings
→ System → Repairs. Core's [generic confirm flow](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/repairs/issue_handler.py#L17-L47)
then [deletes the resolved issue](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/repairs/issue_handler.py#L121-L134).
Do not clear all repairs, edit `.storage`, suppress service errors, or resolve it
before establishing that the cause is corrected. No warning was resolved here.

## Future deployment plan — requires separate authorization

1. Review and merge only the exact green PR head. Schedule a maintenance window
   with no active native persistent write, unresolved recovery or qualified
   outage. Obtain operator approval for the HACS update, full HA restart and
   integration reload verification. None is authorized by this assignment.
2. Capture a restorable HA full backup, installed integration files/build ID,
   approved source SHA, Guardian journal/permissions/preset readbacks, automation
   config hashes and native equipment/ownership state. Preserve recovery data.
3. Before updating, inspect actual WebSocket `get_services` and confirm the four
   Guardian actions are present; save recent heartbeat traces. Registry reads
   are sufficient—do not press Apply or enable commissioning permissions.
4. Install the approved HACS package/release through the established workflow;
   confirm installed files/build SHA. A full HA restart is needed to load the
   new component-level `async_setup`; a reload alone does not rerun component
   setup and is not adequate proof of this change. Verify boot health and all
   required service names in actual `get_services` before calling any action.
5. Observe natural heartbeat completion after the existing initialization gates
   settle. Confirm reasons/request classes, no unexpected writes, Guardian
   permissions unchanged, native presets correct and recovery healthy. Do not
   bypass normal initialization, outage qualifications or flow checks.
6. With separately authorized reload testing, record the service registry before,
   throughout and after the reload and entry state changes. The four Guardian
   services must never be removed. A natural trigger during unavailability may
   fail with a clear entry-not-loaded validation error; it must not create an
   unknown-action repair or execute against a retiring runtime. After LOADED,
   the next natural heartbeat must succeed. No physical stimulus is required.
7. Verify Pool/Spa ownership, Solar/filtration accounting, sanitation, Cleaning
   Stage A and default-OFF Stage B diagnostics, Guardian preset readbacks and
   unchanged automation hash. Stop on unexpected native activity, missing
   service, setup failure, recovery contradiction or changed authority.
8. Only then resolve the old specific repair with separate explicit approval.
   If a new unknown-service issue appears, preserve timing/registry evidence
   and investigate rather than dismissing it.

Rollback, if needed and authorized: restore the saved known-good integration
package through the supported HACS/recovery workflow, restart in the approved
window, verify exact installed revision and native/Guardian/automation health.
Do not erase the journal or change presets. The old package reintroduces the
registration gap; retain that limitation in the rollback record. No automation
rollback is needed because no automation was changed.
