# Pool & Spa photographic scene — release acceptance

Status: **BLOCKED** for production animation release until the clean background exists.

The installed sunset photograph (`web/backyard-final.jpg`) has baked-in flowing water at the slide and spa spillway and visible spa turbulence. It cannot represent equipment OFF accurately, regardless of CSS animation.

## Required image assets

- `backyard-off.jpg`: clean **dry** slide chute, **dry** spa spillway, still spa surface, same composition/camera/lighting and same pool geometry as the approved image. No controls, labels, or text baked into the photo.
- Water effect layers for slide and spillway aligned to the actual final asset in portrait orientation.
- The user-approved lower-third glass controls must remain untouched.

## Scene behavior and evidence gates

| Case | Expected visual | Evidence |
| --- | --- | --- |
| Slide OFF | Dry slide; no animated flow | BLOCKED — base photo still wet |
| Slide ON | Flow following chute, splash at outlet | NOT RUN |
| Spillway OFF | Dry tile face, no falling water | BLOCKED — base photo still wet |
| Spillway ON | Falling water over spa edge | NOT RUN |
| Jets OFF | Calm spa surface | BLOCKED — base photo shows turbulence |
| Jets ON | Spa surface bubbles | NOT RUN |
| Pool active | Subtle moving pool ripples | CODE TESTED (static only) |
| Spa active | Subtle surface movement | CODE TESTED (static only) |
| Pool light ON | Underwater light effect | CODE TESTED (static only) |
| Unknown/unavailable | No false active animation | CODE TESTED (static only) |
| Reduced motion / hidden tab | Effects stop | CODE TESTED (static only) |
| Existing control/PIN/RPM Guardian | Unchanged | CI REQUIRED |

Do not mark this document PASS based only on CI or a screenshot of static water. Validate animation on iPhone against real observed HA state without forcing physical equipment solely for a cosmetic test.

## Technical approach

Use a **single** clean background image, with independently toggled decorative water layers. Do not overlay an all-off image over a flowing background: that creates mismatched geometry and ghost water. Do not animate a feature merely because the user tapped its button; wait for the existing authenticated state refresh to confirm it.

Current PR #120 only restores the glass appearance and introduces acceptance checks. Keep the release unmerged until the scene asset and behavior are complete.
