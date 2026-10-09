# Live read-only entity parity — 2026-10-08, 22:43 PDT

## Scope
Point-in-time Home Assistant `ha_get_state` comparison of **32 matched legacy PoolOS versus standalone IntelliCenter entity pairs**. No equipment was operated and no entity was renamed.

## Result
**32/32 current values agree** after numeric equivalence and case normalization. This is a state comparison, **not** a physical-command, event-timing, source-provenance, or cutover acceptance test.

| Category | Pairs | Result |
|---|---:|---|
| Freeze, body, accessories and solar-active binary observations | 8 | 8 agree |
| Temperatures, pump, chemistry, firmware, system mode, body setpoints | 17 | 17 agree |
| Pool/Spa climate | 2 | 2 agree |
| Pool light | 1 | 1 agree |
| Pool/Spa heat source selection | 2 | 2 agree |
| IntelliChlor output numbers | 2 | 2 agree |
| **Total** | **32** | **32 agree** |

Observed: freeze OFF on both; Pool OFF; Spa OFF; Pool Light ON; pump 0 RPM; Pool Solar selected, Spa Gas selected. Solar heating active OFF on both. `sensor.system_mode` was `AUTO` versus `auto`; salt/output numeric values were equivalent.

## Important caveats
- The replacement's entity `last_updated` can remain unchanged when values remain stable. Do not infer transport freshness from HA `last_updated` alone; check `last_reported`, native snapshot age and disconnection behavior.
- PoolOS exposes 50 legacy IntelliCenter-prefixed entities, while only 32 matched pairs were sampled. Some are PoolOS command/derived concepts without exact standalone equivalents.
- No active heating, freeze ON, live pump ramp, disconnect, reconnect, accessory interlock or outage transition was exercised in this comparison.
- A 32/32 match does **not** authorize changing control ownership or HomeKit IDs.
- Existing PoolOS native parity diagnostics (`sensor.poolos_control_center_native_intellicenter_mismatches`) measure a different PoolOS-internal comparison and must not be conflated with this 32-pair bridge check.

## Next engineering gates
1. Verify native observation freshness and fail-closed behavior under stale/disconnected conditions using offline regression tests and a controlled read-only reconnect test.
2. Establish active Pool/Spa, pump ramp, heater firing, Solar firing, light effects, and accessory transition parity during separately approved commissioning.
3. Resolve semantic differences for the remaining 18 legacy entities; identify exact automation, dashboard, HomeKit and external consumers.
4. Design and rehearse exact-ID migration/rollback with a single writer. PoolOS remains sole writer; standalone integration remains read-only.
