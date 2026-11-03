# Opportunistic Spa Solar — isolated implementation contract (DRAFT)
Date: 2026-10-23
Base: 2d0f129424922738b2e9a0edb3a2581efbd77aad (AUX 9 cleaning protection)
Status: DESIGN ONLY — no HA deployment, no physical commissioning authorization.

## Boundary
PoolOS remains retired. The Pool Simple Solar and Filtration scheduler, Heating Preference Controller, sanitation sessions, grid-outage supervisor, and RPM Guardian retain their current responsibilities. PWA is a manual user interface and is out of scope. Use the existing intellicenter_manual climate and select entities; no second native transport, RPM writes, persistent preset writes, or Spa target-temperature writes.

## Ownership priority
Safety / freeze / outage / service / Guardian / cleaning > explicit manual Pool or Spa > sanitation > Pool heating or currently-due filtration > opportunistic Spa > idle.
Any unknown or stale critical observation denies acquisition; uncertain owned-session release must not blindly switch equipment OFF.

## Preconditions for acquisition
- Feature explicitly enabled, and no restart/manual-OFF suppression or recovery-required latch.
- Native observation fresh and credible; both bodies, source and roof valid.
- Automatic ownership enabled, Pool OFF and not manually owned; no Pool heat demand, no filtration currently due, no active independent Pool circulation authority.
- Spa OFF and no manual Spa claim; sanitation, cleaning AUX 9, freeze, outage, service, accessory and RPM Guardian gates clear.
- Solar roof >=130 F continuously for two minutes; source can be selected Solar and read back before Spa activation.
- Recheck all authority gates immediately before each write; bounded verification of source and body ON.

## During an owned session
- Existing Spa setpoint unchanged; maintain Spa ON at target while Solar remains viable. No direct RPM command.
- Never select Gas or permit another controller to choose Gas while this owned session is active.
- Heating Preference Controller must have an explicit owner-aware exception for Spa only; normal manual Spa Eco Heat behavior remains unchanged.
- Legacy 'Hot Tub - Select Heat Source on Start' is currently OFF; if enabled later, its Gas fallback is unsafe unless owner-aware.
- Roof below 120 F: enter recovery for up to five minutes. Recover on valid Solar; after sustained loss terminate only if ownership still proven.
- Pool heating demand or due filtration preempts promptly, without forfeiting filtration debt.
- Manual ON/source changes, manual OFF, or PWA takeover yield ownership; manual OFF suppresses reacquisition. Distinguish commanded changes from manual events via epoch/receipt, not solely Spa ON transition.
- HA restart during acquisition/owned session: fail closed, no blind shutdown or reacquisition. Require explicit operator recovery when ownership cannot be proven.

## Release / rollback
A dedicated disable switch blocks acquisitions. For a currently owned session, a disable/release operation must follow verified owner-aware shutdown/handoff rules; disabling is not proof that it is safe to command Spa OFF.
Rollback must restore the exact pre-feature heating-preference configuration as well as remove/disable the coordinator and helpers. Protect the existing AUX 9 and RPM Guardian changes. Record fresh HA backup, live automation hashes, GitHub SHA, and installed build before deployment. Restore tests are NOT RUN.

## Regression matrix — all NOT RUN
1 Pool Solar acquisition and stable delivery
2 Pool target-satisfied daytime shutdown
3 Filtration debt accumulation and 08:00 reset
4 Filtration due preempts opportunistic Spa
5 Pool heat demand preempts opportunistic Spa
6 Spa starts only after 130 F for two minutes
7 Existing Spa target preserved; Spa remains ON at target
8 Short Solar loss recovers; sustained below 120 F for five minutes releases
9 No Gas fallback from Heating Preference Controller
10 Disabled legacy Spa-start source selector remains disabled and cannot cause Gas
11 Manual Spa ON/OFF and source override yield, suppress reacquisition
12 Sanitation, cleaning AUX 9, outage, freeze, service and Guardian blocks
13 Restart/stale telemetry fail closed; no orphaned write
14 No direct RPM writes or unintended Pool filtration credit
15 Exact rollback returns existing behavior without reverting AUX 9 protections
16 Full physical cycle: acquire, sustain, maintain, release, stable OFF, later reacquire

## Implementation gate
Do not merge, deploy, reload, enable, or physically test based on this document alone. First implement coordinator and owner-aware source arbitration on this isolated branch, test against command gateway with deterministic observations, establish deployed-build provenance, and compare fresh predeployment snapshots. Record test evidence rather than inferring PASS.
