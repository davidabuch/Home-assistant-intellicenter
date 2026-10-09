# Deployment status — READ-ONLY LIVE; NOT CUTOVER-READY

Observed in Home Assistant on October 8, 2026 (PDT).

## Confirmed
- `intellicenter_manual` is installed and running in Home Assistant with command delivery disabled.
- Independent read-only observations exist and update for `binary_sensor.pool_active`, `binary_sensor.spa_active`, `binary_sensor.pool_heating_active`, `binary_sensor.spa_heating_active`, `binary_sensor.gas_heater_active`, `binary_sensor.solar_heating_active`, `sensor.pump_rpm`, and both body thermostats.
- After the existing PoolOS-native commissioning exercise, both independent body-active sensors were OFF, both heater-active sensors were OFF, and the independent pump sensor read 0 RPM.
- The legacy `poolos_native_intellicenter_*` entities remain owned by PoolOS. No registry migration or writer handoff has occurred.
- The Oct 8 physical commissioning report at `docs/PHYSICAL_COMMISSIONING_2026-10-08.md` exercised **PoolOS-native controls**, not this integration's command transport.

## Not yet established
- Accurate heater-active/Solar-active behavior during sustained physical heat delivery.
- Independent freeze-protection observation and its fail-closed behavior.
- Full parity of accessories, heat-source transitions, sanitization, pump topology and safety automations.
- HomeKit identity preservation, registry migration and rollback validation.
- Permission for this integration to send physical commands.

## Mandatory next gates
1. Compare independent native body, heater and Solar observation against PoolOS-native observations during permitted physical operation, including unknown/disconnected behavior.
2. Implement and regression-test freeze-protection parity if authoritative native status is available; otherwise remain unavailable, never infer OFF.
3. Finish exact-ID consumer inventory and HomeKit identity review.
4. Validate manual-command safety in offline tests; require separate approved reversible single-writer commissioning before enabling writes.
5. Preserve PoolOS as sole live writer until all safety, rollback and commissioning gates pass.

**Do not remove PoolOS or enable the new integration's commands based on these read-only observations.**
