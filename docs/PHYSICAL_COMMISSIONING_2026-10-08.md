# Physical commissioning evidence — 2026-10-08 (PDT)

## Scope and provenance
Commissioning used **existing PoolOS-native IntelliCenter HA entities**, not the new `intellicenter_manual` integration. The new bridge remained read-only; no single-writer cutover occurred. HA service responses and native readback were observed during the session. This is not proof of actual sustained thermal delivery or proof of replacement-bridge command parity.

## Spa
- Starting state OFF, Gas selected, pump 0 RPM, Spillway and Jets OFF.
- Set `climate.poolos_native_intellicenter_hot_tub_thermostat` to heat: confirmed Spa active ON and automation triggered on Spa transition.
- Set `select.poolos_native_intellicenter_hot_tub_heat_mode` to Solar: observed `sensor.poolos_native_intellicenter_spa_heater_id=H0002` and effective native heater ID H0002. HVAC action was idle at an observed point; actual Solar heat transfer **not proven**.
- Set Spa heat mode Gas: observed native heater ID `H0001`.
- Turned `switch.poolos_native_intellicenter_jets_bubbles` ON while Spa ON, then Spa OFF: Jets automatically returned OFF with HA automation triggering on Spa OFF; pump returned to 0 RPM.
- Final Spa OFF; Gas selected, matching initial configuration.

## Pool
- Set `climate.poolos_native_intellicenter_pool_thermostat` to heat: native Pool active ON.
- Selected Solar: native heater ID `H0002`; select service returned a partial timeout because value was already Solar, but subsequent readback confirmed Solar.
- Selected Gas: native heater ID `H0001`.
- Turned Pool OFF, then restored Solar selection (initial setting). Pool active OFF, pump 0 RPM.

## Safety automation
`automation.pool_safety_spillway_and_jets_interlocks` was edited earlier to trigger on actual Spa state transitions, switch ON, HA startup and switch unknown/unavailable recovery, instead of attribute refresh every minute. HA readback confirmed enabled and no periodic trigger during passive observation. Physical Spa OFF with Jets ON caused automatic Jets OFF.

## Final verified states
- Spa OFF; Pool OFF; pump 0 RPM; Jets OFF; Spillway OFF.
- Spa source Gas; Pool source Solar.
- No equipment intentionally left running.

## Outstanding gates (NOT passed)
1. **Spa ON + Spillway ON attempt**: verify fail-closed rejection or automatic OFF without violating parent-equipment requirements.
2. **Unknown/unavailable and recovery**: safely inject simulated entity-state transitions or use a non-actuating test harness; do not disconnect native IntelliCenter or suppress protections just to test.
3. **Physical heat delivery**: native heater selection is not proof of gas firing or solar flow/heat transfer.
4. **Replacement bridge**: all commands were through PoolOS-native entities; `intellicenter_manual` remains read-only, with incomplete parity.
5. **Outage, freeze, and HomeKit identity continuity**: not tested in this session.

## Safety/ownership
No PoolOS removal, HA registry migration, second command writer, or autonomous cutover authorized. Preserve legacy entity IDs and rollback route.
