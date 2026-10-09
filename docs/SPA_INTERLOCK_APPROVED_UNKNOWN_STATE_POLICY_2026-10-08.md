# Approved Spa interlock unknown-state policy — 2026-10-08

**Policy approval:** The operator explicitly selected the first option: if `binary_sensor.poolos_native_intellicenter_spa_active` is `unknown` or `unavailable`, command **both** legacy Spillway and Jets/Bubbles OFF via the existing PoolOS actuator entities. Preserve normal rules (Spa ON => Spillway OFF; Spa OFF => Jets OFF).

**Implementation status: BLOCKED, NOT DEPLOYED.** A direct HA automation update was attempted and blocked by a tool safety check. A subsequent read confirmed the original configuration hash `485b4ba9ca1e7509` unchanged. Do not circumvent the tool safety boundary or claim live HA implementation.

## Target behavior for an authorized deployment

- Preserve the original Spa-state-change, Spillway-ON, Jets-ON and HA-start triggers and `mode: restart`.
- Add a first `choose` branch requiring Spa state in `['unknown','unavailable']`, then `switch.turn_off` both `switch.poolos_native_intellicenter_spillway` and `switch.poolos_native_intellicenter_jets_bubbles`.
- Preserve both existing ON and OFF branches unchanged, with PoolOS as sole writer. No commands from `intellicenter_manual` and no HomeKit changes.
- Verify no unexpected actions when Spa is known and both outputs are already OFF; verify no duplicate writers.
- Before applying: ensure backup/rollback of exact original automation, verify current entity states, and confirm the blocked write path has been legitimately restored.
- After applying: read automation back, verify both branch and original branches, observe safe runtime state, and physically commission the unavailable/unknown transitions only in an authorized controlled test window. Do not simulate telemetry faults against operating equipment without a safety plan.
- Unknown/unavailable state **value** is different from stale-but-still-`on`/`off` data. This approved rule does not solve stale freshness detection; that remains a separate engineering gate.

## Provenance

Live HA audit: `docs/SPA_INTERLOCK_STALE_TRUTH_AUDIT_2026-10-08.md`. User approval was explicit in conversation. This file is a policy/implementation handoff, not proof of deployment or physical acceptance.
