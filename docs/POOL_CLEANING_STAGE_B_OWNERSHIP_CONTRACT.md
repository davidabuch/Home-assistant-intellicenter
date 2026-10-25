# Pool Cleaning Stage B — ownership and commissioning gate (draft)

Status: DESIGN ONLY. Stage A remains deployed and read-only. No Stage B actuator may be enabled by this document.

## Verified physical evidence (2026-10-24)
- Pentair native cleaning feature FTR03 ON from idle: Pool OFF, pump 0 RPM.
- Stage A reported `would_request_pool_on`, no commands, no ownership claim.
- Native cleaning OFF: after distinct native OFF observations spanning >=20 seconds, Stage A reported `would_reconcile_existing_controller`, no commands.
- Native cleaning speed preset 3000 RPM verified by RPM Guardian. The pump has **not** been verified running at 3000 RPM under cleaning.
- Spa OFF, Pool OFF, Guardian NORMAL, no failed writes during the observed cycle.

## Non-negotiable authority rules
1. Native Pentair cleaning remains the feature/timer authority. Never replace its 3-hour timer with an HA timer; never write cleaning RPM in the handoff.
2. Stage B must be explicitly opt-in, default OFF after install/restart/upgrade. Stage A diagnostics remain available with Stage B disabled.
3. Startup/reconnect with cleaning already ON is recovery-only; it must not manufacture an activation edge or issue Pool ON.
4. Every action requires fresh, distinct native snapshots, correct FTR03 identity, connected AUTO mode, freeze=false, Spa OFF, and all Stage A policy gates green. Recheck immediately before each dispatch.
5. No commands if grid outage, sanitation, Guardian interlock/degradation, auxiliary demand, service/freeze, unknown telemetry, or manual ownership. Changes in any authority gate cancel pending work.
6. Never interpret Pool ON following a cleaning proposal as proof of our command. A successful dispatch receipt plus subsequent fresh native Pool ON and appropriate pump demand must be tied to the same session before recording a cleaning-created circulation claim.
7. A command receipt is not physical verification. The claim must carry episode identity, native observation chronology, exact dispatched command and its acknowledgment, verification, and an expiry. Lose claim on reconnect, restart, ambiguous manual intervention, stale telemetry, or identity change; fail closed.
8. On native cleaning OFF, wait for at least two distinct native OFF receipts spanning >=20 seconds. Do not turn Pool OFF simply because cleaning stopped. Re-evaluate the independent Solar/Filtration controller's current desired state and any active manual Pool ON. Never bypass its manual grace period.
9. **Blocking uncertainty:** An independent manual Pool ON during cleaning may be observationally indistinguishable from cleaning-created circulation. Until a reliable, separately sourced manual-intent/command attribution signal or exclusive command arbiter exists, Stage B must NOT automatically turn Pool OFF on release. Reconciliation may only hand off to the existing controller without issuing an OFF command.
10. Stage B must not introduce a second competing Pool command writer. Use a single serialized command authority shared with the existing Solar/Filtration controller, with dispatch-time checks and a recoverable abort path. If this cannot be demonstrated, remain observation-only.
11. Native cleaning OFF/timeout while Solar or filtration requires Pool ON must preserve circulation. If neither requires circulation, only the existing controller may decide to stop Pool after checking its normal protections.
12. No direct calls from sensor update callbacks. Dispatch must be isolated, bounded, cancellable, logged, and idempotent across repeated observations.

## Required tests before any Stage B physical actuation
- Normal idle activation, native 3000 RPM physically observed, timed native release.
- Native cleaning ON while Pool already ON; no cleaning ownership claim.
- Manual Pool ON during cleaning and immediately before release; preserve manual operation.
- Solar required/not required, filtration debt due/not due, manual-grace transitions.
- Spa preemption; sanitation; freeze; outage; service; Guardian degraded; auxiliary features.
- HA restart/disconnect/reconnect while cleaning ON, during Pool ON dispatch, and during release.
- Duplicate/stale/out-of-order native observations, circuit identity change, missing acknowledgments.
- Cleaning reactivation during release confirmation, timed native OFF and explicit manual OFF.
- Fault injection proving no Pool OFF under ambiguous provenance, no second writer, and no timer/RPM override.

## Promotion sequence
A. Add read-only command provenance instrumentation to the **existing** HA Pool controller and inventory all writers of Pool ON/OFF; validate attribution against a manual Panel Pool ON.
B. Implement Stage B state machine with simulated transport and deterministic regression tests; retain a hard default-off feature flag.
C. CI green, review and merge, deploy with flag OFF, verify unchanged Stage A.
D. With explicit physical commissioning approval, enable limited Pool ON only after exclusive command authority and provenance tests pass; observe pump and 3000 RPM.
E. Keep automatic Pool OFF blocked until manual-intent ambiguity is solved and independent controller arbitration is demonstrated.
