# Pool & Spa photographic scene — release acceptance

Status: **IN PROGRESS** — clean OFF candidate uploaded and wired on development branch; geometric calibration and physical-state confirmation still pending.

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

## Approved visual reference — 2026-10-16

The user approved the latest two-panel **All Features OFF / Features ON** mockup, including the shortened dry waterslide exit (no tongue-shaped fiberglass protrusion), sunset scene, visible spa spillway and bottom-anchored glass console.

**Important:** The mockup is a visual specification, **not a shippable background image**: both halves contain baked-in temperature cards and control buttons, and the ON half depicts a different water state. Never set a full mockup as the CSS scene background; doing so would duplicate the interactive controls and produce a false equipment-state display.

Asset extraction requirements:
1. Derive a clean portrait OFF background with **no text or controls** and the corrected dry slide outlet. Match the approved perspective and composition.
2. Keep the pool/spa water, lights and landscape consistent with the OFF reference; eliminate running-water evidence at slide and spillway.
3. Generate or render independent transparent slide-water, spa-spillway and jet effects aligned to **that same clean background**; do not use a complete ON photograph as an overlay.
4. Verify slide OFF / ON and spillway OFF / ON against confirmed state in a browser at iPhone viewport dimensions. Confirm no ghost water when OFF.
5. Preserve the existing lower control layout and PIN/permissions; test on the same installed add-on only after CI and release.

Approval is for the visual direction, not for an unverified release.

## Asset integration checkpoint — 2026-10-16

- Clean candidate `web/backyard-off.jpg` committed at `2af9c85` by user via Mac Terminal.
- Development CSS background now points to `backyard-off.jpg`, with SVG fallback.
- Static server whitelist includes `/backyard-off.jpg`; service worker precaches it.
- **Not yet production ready**: visually calibrate masks/placement at actual iPhone crop and verify motion vs observed HA states before merging.
