# Reversible IntelliCenter cutover and rollback contract

**Status: design only — NOT authorized for execution.** PoolOS remains installed and authoritative. Bridge remains hard-locked read-only.

## Preconditions

1. HA full backup, validated recovery procedure, export of current entity registry metadata (entity_id, unique_id, platform, config_entry_id, custom name/icon, aliases, exposure, device assignment) and copies of affected automation/dashboard configurations.
2. Full read-only reference audit including config-entry groups, HomeKit bridges, helpers, HLM lighting ownership, notifications, and external consumers. Three automation configurations found by search are still inaccessible to direct automation retrieval; treat as blockers.
3. Resolve functional gaps: native heat-mode semantics (PoolOS `Solar Preferred` != bridge `Solar`), Spa/Pool HVAC attribute parity, IntelliBrite effect readback, safety interlocks, and any needed freeze/solar telemetry.
4. CI tests green; verified live observation freshness, availability, and command lockout; approval of a physical commissioning window and stop conditions.

## Planned transaction (do NOT run automatically)

- Take a fresh backup and snapshot both old and new entity registry records immediately before changes.
- Keep the existing PoolOS config entry and its automation ownership intact until a single planned controller handoff. Avoid dual writers at all times.
- Per entity, record old `unique_id` and its exact `entity_id`, new bridge `unique_id` and temporary `entity_id`. Preserve the old `entity_id` only through supported HA entity registry APIs and only after old ownership has been safely released. Never rewrite `.storage` directly.
- Restore icon, display name, aliases, exposure and all consumer references as needed; inspect HomeKit entity selection and device bindings separately. Verify no `_2` suffix duplicates.
- Apply changes in dependency order with safety interlocks and lighting ownership protected. Verify readback, consumer traces, and physical outcome after each authorized action.
- STOP on unexpected physical actuation, stale telemetry, missing safety interlock, dual authority, entity collision, unrecognized heat mode, or automation failure.

## Rollback

- Immediately cease bridge commands; stop further migration.
- Re-establish the previously verified PoolOS controller authority before re-enabling automation-driven actuation; avoid simultaneous writers.
- Reverse registry renames through supported APIs using saved old/new `unique_id` mapping, restore consumer configs and exposure/icon metadata, verify legacy entity IDs and automation traces.
- Restore HA backup if atomic reversal is not reliable. Verify Pool/Spa OFF-safe state, equipment interlocks, lighting ownership and expected filtration policy before resuming autonomous operation.
- Do not uninstall PoolOS until all commissioned functions and recovery scenarios have passed.

## Verified architectural constraints

- Bridge transport instantiated with `allow_commands=False` and `_CommissioningController` rejects protocol mutations independently.
- Existing PoolOS and bridge entities belong to different config entries and have distinct stable unique IDs.
- PoolOS legacy heat-source `Solar Preferred` is not equivalent to manual bridge `Solar`.
- No HA automation, registry entry, or physical equipment was modified by this document.
