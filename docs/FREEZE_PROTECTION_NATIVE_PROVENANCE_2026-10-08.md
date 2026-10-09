# Native freeze-protection observation — source discovery

## Observed evidence (2026-10-08 PDT)
Home Assistant currently exposes `binary_sensor.poolos_native_intellicenter_freeze_protection_active`, observed **off**, with attributes `canonical_concept=freeze.active`, `quality=good`, `available=true`, `read_only=true`, and source identity `intellicenter_native:poolos.independent_intellicenter:_FEA2`. This proves PoolOS has an observed source, **not** that the replacement integration can yet decode it.

In `davidabuch/poolos` `poolos/intellicenter_readonly.py`, `_freeze_circuit` requires exactly one native circuit whose subtype normalizes to `frz`; `_freeze_active` recognizes only native status `on` or `off`, otherwise returns unknown. This source is read-only and is not a mandate to import PoolOS.

## Replacement integration gap
`custom_components/intellicenter_manual/transport.py` currently publishes a fixed subset of circuits `C0002`, `C0003`, `C0004`, `FTR01` and does not surface the native `_FEA2` freeze feature or a corresponding HA binary sensor. A hardcoded `off` default would be unsafe.

## Implementation acceptance gates
1. Verify actual `_FEA2` object type, subtype, status field, and freshness from **this integration's own native model**, without relying on PoolOS-derived entity state as the data source.
2. Select exactly one native subtype `FRZ` feature; reject zero/duplicates, stale, disconnected, malformed, and unknown native status as **unavailable**, not OFF.
3. Publish a distinct read-only `binary_sensor.freeze_protection_active` with a stable unique ID. Never reuse or rename the PoolOS legacy ID before cutover.
4. Add offline tests for ON, OFF, unknown, duplicate, disconnected, stale, and mismatched identity; keep physical writes disabled.
5. Validate simultaneous read-only HA parity with PoolOS's `freeze.active` including a genuine native ON event when safely available. Do not simulate cold weather by changing physical equipment settings.

## Authority
No change to PoolOS sole-writer status, HomeKit exposure, safety automations, or registry IDs is authorized by this discovery document.
