# Historical transition comparison — October 8, 2026

Home Assistant Recorder history was reviewed for 22:08–22:35 Pacific. This is an observation-only comparison of previously performed commissioning activity; no new equipment commands were issued.

| Observation | PoolOS native | Standalone integration |
|---|---|---|
| Spa ON | 22:14:37 | 22:14:36 |
| Spa OFF | 22:14:57 | 22:14:56 |
| Pool ON | 22:15:04 | 22:15:04 |
| Pool OFF | 22:15:27 | 22:15:27 |
| Jets ON | 22:14:52 | 22:14:52 |
| Jets OFF | 22:14:58 | 22:14:58 |
| Pump RPM: 698, 1800, 0, 934, 0 | Matching timestamps | Matching timestamps |
| Pool selected source Solar to Gas to Solar | 22:15:21, 22:15:30 | 22:15:22, 22:15:30 |
| Spa selected source Gas to Solar to Gas | 22:14:42, 22:14:46 | 22:14:42, 22:14:47 |

Recorded values match within about one second, but HA Recorder timestamps do not prove identical native delivery timing.

## Outstanding gates

- At 22:30:09 the PoolOS native entities became unavailable, recovering at 22:30:21. Standalone Pool/Spa and pump state-change history did not show equivalent unavailability. This may reflect independent connection continuity or recorder behavior and is **not** an accepted reconnect/freshness test.
- The standalone freeze sensor was unavailable at 22:30:04 before the FRZ discovery fix in PR #40; its later OFF-state parity is confirmed, but a post-fix reconnect test is still outstanding.
- Selected Gas/Solar sources do not establish actual heating delivery.
- Freeze ON, safety interlocks, and HomeKit identity cutover remain unverified.

PoolOS remains the sole physical writer. The standalone integration remains read-only. No authority or entity IDs were changed.