# Lightweight controller commissioning baseline — October 15, 2026

Status: implemented, CI-validated, deployed and HA-observed. Physical cycle
acceptance is pending. This is a dated evidence record, not a new control policy.

## Governing workflow and authorization ledger

The user supplied and requested the canonical **GitHub + Home Assistant Autonomous
Engineering Workflow v3.2**, updated October 8, 2026. The supplied file's SHA-256
is `0f76927551a6eab99f0dacb810765ce8a01acb64d9283b2d232b98d35cd03e30`.
It is referenced rather than copied into another universal workflow. The task's
explicit safety boundaries and commissioned native identities remain governing.

| Ledger item | Current evidence / authorization |
|---|---|
| Objective | Repair target-satisfied shutdown; audit conflicts and PoolOS retirement without deleting PoolOS or altering presets |
| Phase | Implementation/verification authorized; no forensic-only Phase A boundary |
| Implementation provenance | PR #99; tested PR head `a1655e56192c11587805bf1c9402b9732bf94b68`; merged runtime-config source `22587d8d82dd7da8d8ba476ca80d005047bdd427` |
| PR CI / merge CI | Both exact-head PR checks green; merge CI run `38797796203` green |
| Routine continuation | Tests, PR/CI, merge, narrow HA config deployment/reload, read-only verification and documentation already authorized |
| Physical envelope | Pending operator readiness for target 90 -> 71 -> 90 F, stable OFF hold and native readback; attachment supplies workflow, not a new equipment stimulus |
| Prohibited | PoolOS deletion, preset changes, essential safety removal, future RPM manager or new outage supervisor |
| Live authority | `intellicenter_manual` owns native Pool entities; master and session ownership helpers ON; legacy PoolOS config entry absent |
| Latest read-only baseline | Pool actual 74 F / target 90 F / ON / pump 2900 RPM; Spa OFF; sanitation helpers OFF; grid outage OFF; ledger 215 min |
| Suppressions | No suppression cleared, deliberately disabled controller enabled, target changed or physical commissioning service invoked; seasonal duplicate stays OFF |
| Installed artifact check | All three deployed automation configs semantically match merged JSON; exact integration implementation was unchanged by this task |
| Runtime-config hashes | Schedule `d7287ca22264c43d`; preferences `e179dc607550411c`; existing outage supervisor `f3f146689409f58c` |
| HA verification | API validation accepted configs; explicit automation reload successful; new traces show ledger credit followed by guard evaluation and no climate/source write during legitimate Solar demand |
| Release | No GitHub Release was returned by `gh release view`; none created or promoted for this commissioning work |
| Deferred conditions | Target-satisfied physical cycle, next midnight/08:00, full HA restart, historical last-proven configuration and HLM shadow reference |
| Next executable action | On explicit operator readiness, capture a fresh baseline and exercise the defined target-lower/stable-OFF/target-raise production path; stop on unexpected actuation or authority disagreement |

## Behavior-by-behavior acceptance provenance

Every runtime artifact below is the exact config tree from merge
`22587d8d82dd7da8d8ba476ca80d005047bdd427`. Added gateway tests exercise that
same unchanged transport/config tree. The test/documentation follow-up changes
no integration implementation, automation artifact, helper or preset.

`CODE TESTED` means offline execution with synthetic telemetry/protocol IO;
`HA OBSERVED` means live readbacks/traces; neither is `PHYSICALLY COMMISSIONED`.
The unavailable last physically proven commit remains unknown for each behavior.

| Acceptance case / stimulus | Code and authority evidence | HA/native receipt | Current acceptance |
|---|---|---|---|
| 1. Eligible Solar, target > actual | Config replay permits owned daytime start; generated restart crosses real transport allowlist and protocol write gate | Existing 74/90 F Solar session retained at 2900 RPM, both ownership helpers ON | CODE TESTED; HA OBSERVED steady state; acquisition physical test NOT RUN |
| 2. Lower target below actual | Actual >= target generates OFF; real `set_body_active`/`_send`/`_confirm_body` execute; helper cleanup waits for verified native OFF in awaited replay | Historic 12:31 failure reconstructed; no new lowering performed | CODE TESTED; physical acceptance NOT RUN |
| 3. Roof remains eligible after shutdown | Three repeated ticks after synthetic native OFF generate no further body/source commands | No deliberate hot-roof OFF hold induced | CODE TESTED; physical acceptance NOT RUN |
| 4. Raise target again | Same cycle restarts through actual source/body gateway methods and new native confirmation | No deliberate target restoration/start induced | CODE TESTED; physical acceptance NOT RUN |
| 5. Brief Solar interruption | Existing pre/post config replay preserves short hold, five-minute Solar-loss trigger and Eco Heat fallback | Roof was not deliberately interrupted | CODE TESTED; physical acceptance NOT RUN |
| 6. Midnight filtration debt | Debt independently permits start/adoption despite satisfied thermal target; restart tick reconciles night debt | Runtime config loaded; next midnight not observed in this session | CODE TESTED; overnight acceptance NOT RUN |
| 7. Quota reached | Boundary tick increments before shutdown reconciliation; legitimate hot-roof demand retained | Counter credit observed; quota not reached during observation | CODE TESTED; live quota acceptance NOT RUN |
| 8. Spa active | Config replay blocks schedule actuation and credit during Spa; bridge interlocks retained | Spa OFF at baseline; no Spa stimulus | CODE TESTED; physical acceptance NOT RUN |
| 9. Sanitation active | Either helper or physical sanitation switch blocks schedule actuation; independent accounting preserved | Both helpers OFF; sanitation automations remain enabled | CODE TESTED; physical acceptance NOT RUN |
| 10. Grid outage | Config blocks ordinary equipment commands; actual production outage callback rejects a previously planned Solar restart at final dispatch | No simulated or physical outage induced; native safety controls retained | CODE TESTED for authority; physical acceptance NOT RUN; 1500-RPM enforcement remains BLOCKED by deferred supervisor |
| 11. External/manual ownership | Replay honors master OFF and unclaimed external session; real transport rejects authority revoked after planning and after lock wait; disarms writes | Current master/session claims ON; no manual authority changes | CODE TESTED; existing authority HA OBSERVED; physical handoff NOT RUN |
| 12. HA restart/reload | Replay reconciles restored state without blind startup; actual gateway rejects stale observation; existing transport disconnect tests retained | Explicit automation reload completed; post-reload traces normal | CODE TESTED; reload HA OBSERVED; full restart NOT RUN |
| 08:00 rollover | Reset independent of equipment ownership/outage, sole reset writer in exhaustive config search; dynamic target unchanged | Configuration verified; 08:00 not reached during session | CODE TESTED; HA OBSERVED configuration; physical/accounting cycle NOT RUN |
| Failed cleanup binding | Synthetic matching OFF with an old timestamp times out in production confirmation; awaited config replay retains session claim until a fresh receipt permits cleanup | No deliberate failed physical command | CODE TESTED; physical acceptance NOT RUN |
| Preset preservation | Actual bridge identity/allowlist/readback implementation unchanged; no schedule configured-speed writes | Six read-only sensors and six configured numbers observed as 2600/2600/3200/3000/2900/1500 | HA OBSERVED preservation; new preset write test NOT RUN by design |

## Workflow fidelity follow-up

The first 113 passing tests included a schedule interpreter and separate native
contracts. The follow-up adds nine tests connecting generated schedule actions
to actual production dispatch/confirmation methods, including the actual HA
outage callback. Only external protocol IO and incoming observations are fake.
It also brings two existing free-function authority checks into the repository's
`unittest` CI discovery. The full local suite now executes **124 tests**.

The gateway tests do not run the Home Assistant automation engine. They do not
prove real valve timing, native priming/cooldown, physical flow, a completed
unattended operating cycle or every possible reordered event. Physical
acceptance remains pending; no release is promotable on these tests alone.

## Exact next commissioning scenario and STOP conditions

Use the intended production/user path: lower the target via the Pool UI used by
the operator. Read-only HA observation can collect resulting trace, native state
and authority without replacing that user path with an easier control path.
With fresh safe baseline and operator authorization:

1. Confirm target 90 F / actual about 74 F, hot roof, automatic ownership ON,
   schedule claim ON, Spa/sanitation/outage/freeze OFF, AUTO service mode, and
   no independent accessory circulation. Capture native state and all presets.
2. Lower target to 71 F. Observe the thermal trigger, satisfied branch, native
   body OFF receipt, eventual equipment settling and session claim clearing.
3. Hold two minutes with roof still eligible. Confirm no Pool/source restart.
4. Restore 90 F, subject to fresh operator intent. Observe legitimate demand,
   acquired claim, native Pool ON receipt, Solar activity and eventual 2900 RPM.
5. Verify all six presets, stable authority and final operator-desired state.

Stop for an unexpected actuation, stale/contradictory native observation,
missing OFF confirmation, competing authority, safety preemption, operator
cancellation or unanticipated circulation requirement. Preserve trace/history;
perform only authorized minimum safe-state recovery. Do not force ownership,
change presets, bypass safety or fabricate a successful receipt to finish.

No startup-command execution hook was configured for this task; host inspection
commands were interactive and completed. No persistent commissioning monitor or
new release/tag was created. Keep the controller on this commissioning line;
repair forward through CI if acceptance fails rather than churning versions.

## Continuous-execution handoff

CONTINUOUS EXECUTION DIRECTIVE: Once the objective is authorized, do not stop at routine intermediate milestones. After each tool result, determine and execute the next authorized, safe action. Handle PRs, CI failures, authorized merges, authorized deployment, HA verification, and regression correction without repeated permission requests. Stop only at an explicit approval, safety, physical, permission, tool, or commissioning boundary. A progress report is not completion.

Use the continuous workflow in this document. Do not routinely stop between
investigation, implementation, CI repair, merge, Home Assistant deployment,
runtime verification, and commissioning. Use GitHub and Home Assistant directly,
and use a controlled HA-host execution path before asking for Mac Terminal.
Stop only for a genuinely necessary human, physical, safety, permission,
destructive-action, policy, or unresolved design boundary.
