# IntelliCenter replacement — transport recovery commissioning gate

## Verified on October 8, 2026 (Pacific)

- Replacement integration remained read-only; PoolOS retained sole physical command authority.
- A controlled disable of only the replacement HA config entry made its entities unavailable. PoolOS's independent observer remained available.
- On re-enable, the replacement's native observation freshness was initially OFF and its telemetry unavailable. After a new native update, freshness became ON, observation age 14.9 seconds, freeze protection OFF, and pump RPM 0.
- PR #45 added isolated fault-injection regressions against real transport callback logic (using a stub protocol module), covering disconnect, retry, stale snapshot and reconnect requiring a new native update. GitHub CI passed.


## Second controlled reload verification — October 8, 2026, 23:23–23:24 PDT

- Baseline: replacement freshness ON, age 32.9 s, freeze OFF; PoolOS independent transport AVAILABLE.
- Replacement config entry `01M4F1DFGA4AH4F9E9M7MJCR5Q` disabled through the Home Assistant integration API without restarting Core. Replacement freshness, observation age, and freeze entities became unavailable; PoolOS remained AVAILABLE.
- Replacement entry re-enabled. Immediately afterward, freshness OFF, observation age unavailable, freeze unavailable, PoolOS AVAILABLE. This demonstrates fail-closed behavior before a trusted native update.
- At 23:24:01 PDT, replacement freshness returned ON and freeze returned OFF after a native observation. Subsequent observation age was 15.1 s and PoolOS remained AVAILABLE.
- Home Assistant system logs filtered for `intellicenter_manual` returned no entries after recovery.
- This second pass confirms **controlled unload/reload recovery**, not a forced or unexpected TCP socket drop. The isolated socket-interruption gate below remains **OPEN**. No physical commands, PoolOS changes, or HomeKit cutover were performed.

## Not yet verified

- An actual TCP socket interruption affecting only the replacement client, without disrupting PoolOS or the controller.
- Live reconnect timing, stale transition and subsequent reacquisition after such a socket interruption.

## Safety and acceptance criteria

Do not block the IntelliCenter host, restart the controller, disable its network interface, or disrupt PoolOS to simulate a replacement-only disconnect. Keep physical command delivery disabled and do not change HomeKit identity or entity IDs.

For a future isolated socket test, require evidence that (1) only the replacement client disconnected, (2) its health went OFF and telemetry became unavailable within the freshness boundary, (3) it did not report old values as valid on reconnect, (4) a new native update restored freshness and telemetry, and (5) PoolOS's independent observer stayed healthy throughout. Record timestamps and errors. This document does not claim that this test has occurred.
