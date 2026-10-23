# AUX 9 Pool Cleaning ownership and release contract

Status: APPROVED DESIGN; implementation and physical commissioning pending.

## Authority

- AUX 9 native Pentair Pool Cleaning is a temporary, externally commanded 3000 RPM cleaning session with native three-hour egg timer.
- `binary_sensor.pool_cleaning_active` is read-only evidence of native AUX 9. Neither integration nor HA may turn AUX 9 on/off on behalf of the schedule.
- Keep `input_boolean.pool_automatic_ownership` unchanged. Operator master OFF remains OFF after cleaning.
- Safety authority (freeze, outage, service mode) and independent Spa/sanitation sessions are never bypassed.
- While AUX 9 is confirmed ON, schedule must not turn Pool OFF or override cleaning pump speed. Solar remains eligible when native IntelliCenter permits it, but must not cause conflicting RPM writes.
- Continue verified filtration credit when the Pool body and pump are running. Do not credit mere AUX ON without verified circulation.

## Native transition protocol

1. On ON observation, latch cleaning-session ownership, without changing operator master authorization. Do not infer Pool body from AUX state alone.
2. On OFF observation, do not immediately reclaim authority. Require fresh, consecutive native OFF observations, no unavailable/unknown/stale samples, and no intervening ON. Include a short settling interval for native egg-timer shutdown.
3. During pending release, suppress competing ordinary schedule writes. Preserve safety preemption.
4. Once confirmed OFF, reconcile **current** state, not pre-cleaning snapshot: safety -> Spa/sanitation -> operator master authorization -> Solar/thermal eligibility -> remaining filtration debt -> OFF.
5. Trigger schedule and heating-preference reconciliation immediately on confirmed release, plus periodic reconciliation after restart/reload. Existing native heat-source preference must not override intentional operator manual ownership.
6. Verify post-release Pool body, pump RPM, heat source and helper state from fresh native observation. If verification fails, latch/report failure, avoid unbounded toggling or speed writes, and retry only within bounded safe recovery.
7. Restart/reload while AUX ON must reconstruct the session from fresh native observation; restart/reload after AUX OFF must not blindly replay equipment commands.
8. Native AUX OFF while HA Automatic Ownership OFF leaves normal equipment decisions with the operator; do not force HA ownership ON.

## Acceptance gates

- No AUX writes or RPM preset edits from the observer.
- ON: native cleaning 3000 RPM verified, with no schedule fighting it.
- ON with Solar: verify native delivery and actual pump RPM; do not assume simultaneous compatibility.
- OFF during Solar window: resume eligible Solar at appropriate native speed.
- OFF with filtration debt but no Solar: filtration resumes at ordinary configured RPM.
- OFF after debt complete and no heating: equipment stops if no higher-priority authority.
- OFF with operator master disabled: HA does not reclaim authority.
- OFF under Spa, sanitation, freeze, outage or service mode: higher-priority control remains authoritative.
- Early manual OFF, native three-hour egg timer OFF, and HA restart across both transitions pass.
- Unknown/stale AUX state fails closed for ordinary writes until fresh state is available.
- No changes to retired PoolOS.

## Existing gap

PR #140 adds only the read-only `binary_sensor.pool_cleaning_active`. Current HA schedule, heating preference and RPM Guardian automations have no AUX 9 guards or confirmed-release event. This document does not itself enforce any behavior. Implement and regression-test all authority guards and handoff logic before live commissioning.
