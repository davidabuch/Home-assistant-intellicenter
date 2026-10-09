# Spa safety interlock stale-truth audit — 2026-10-08

**Status: read-only audit; NOT an authorization to modify Home Assistant or actuate pool equipment.**

## Live evidence

Home Assistant `ha_search(include_config=true)` returned `automation.pool_safety_spillway_and_jets_interlocks`, with `initial_state: true` and `mode: restart`. Its triggers are changes to `binary_sensor.poolos_native_intellicenter_spa_active`, Spillway turning ON, Jets turning ON, and HA startup. Its actions are an ordered `choose` with two branches:

1. When Spa truth is exactly `on` **and** legacy Spillway exactly `on`, issue `switch.turn_off` to `switch.poolos_native_intellicenter_spillway`.
2. When Spa truth is exactly `off` **and** legacy Jets exactly `on`, issue `switch.turn_off` to `switch.poolos_native_intellicenter_jets_bubbles`.

There is **no default branch** and no branch for Spa truth `unknown` or `unavailable`. This is a configuration-level stale-truth coverage gap; **not evidence of a real-world safety failure**. Because `choose` runs only the first matching branch, also verify expected behavior when both forbidden outputs are ON; the two branch conditions cannot both match for a single valid Spa state.

At read-only inspection, legacy Spa Active, Spillway and Jets were all `off`; automation was `on`. Native read-only bridge `binary_sensor.spa_active`, `switch.spillway`, and `switch.jets_bubbles` also showed `off`. State timestamps are observation timestamps, not freshness guarantees.

## Required regression scenarios before authority migration

| Spa truth | Spillway | Jets | Required evaluation |
|---|---|---|---|
| ON | ON | either | Spillway OFF command and verified readback |
| OFF | either | ON | Jets OFF command and verified readback |
| unknown | ON | ON | Explicitly defined safe policy; do not silently skip both |
| unavailable | ON | ON | Explicitly defined safe policy; do not silently skip both |
| stale ON/OFF | ON | ON | Freshness gate; never trust stale state merely because value remains on/off |
| ON→OFF | OFF | ON | Jets OFF within bounded verified interval |
| OFF→ON | ON | OFF | Spillway OFF within bounded verified interval |
| HA restart | forbidden combination | any | Startup reconciliation and bounded physical verification |

A proposed fail-closed response must be designed with the actual equipment and PoolOS ownership contract: do **not** blindly command both outputs or bypass PoolOS during a stale-state event. Retain the existing operational automation until a separately reviewed, physically commissioned replacement is authorized.

## Authority and rollback

- PoolOS remains sole controller; IntelliCenter Manual Bridge remains `allow_commands=False`.
- No HomeKit entity/identity edits, no registry swaps, no automation edits, and no physical commands were performed.
- Before any authorized modification: snapshot existing automation, backup HA, define safe unknown/unavailable behavior and verified readback timing, test transitions physically, and prove no dual writers.
- STOP on stale telemetry, an interlock failure, unexpected physical state, or conflicting authority.
