# Family PWA photographic lawn — visual approval candidate

Scope: background only. Merge, release and deployment require explicit visual
approval. No equipment actuation is authorized or performed. PoolOS remains retired.

## Baseline and diagnosis

Repository main c050dc874cb6df495b3d2a39ca6150a5994b8650 and installed HA app
1f173f42_pool_spa_family both confirm v0.1.30. User Image A is authoritative for
controls; subsequently supplied Image B is the approved background-only target.
Its different buttons/icons/layout are deliberately ignored.

The old photograph is1024x1536. Phone CSS uses center top /100% auto without
repeating, so393px width paints589.5px of an852px viewport. The remaining lower
area was covered by repeated38px photographic strips, embedded JPEGs and a
separate lawnForeground element. Final CSS requested lawn-photo.svg; that URL
was absent from the server's static asset map. Fallback color and separate
stacking/texture layers could not produce the approved photographic foreground.

## Candidate

Built-in image_gen edited the approved photograph with Image B as background-only
reference, extending the deck/planting into natural dusk-lit foreground grass.
One finished836x1881 JPEG replaces backyard-final.jpg. Its full-width painted
height at393px is884.25px, covering the tested phone height without tiling or
stretching a texture strip. The unchanged CSS keeps existing top alignment and
full-width scene scaling. Sunset/pool/spa/landscape composition is visually
consistent; generated photograph pixels are not claimed identical to the source.

Removed only grass-specific body::after rules, lawnForeground element/rules,
embedded grass data URLs, lawn-photo.svg and its precache reference. Retained
existing main stacking so protected controls keep identical computed properties.
No new overlay was introduced. Existing scene grading and all tile gradients,
blur/translucency, artwork, power-state rules and safe-area rules are retained.

The original photo's public URL is retained, avoiding any server/API change.
Asset responses already use Cache-Control:no-store. New photographic-lawn-13
shell/CSS/JS cache keys replace lawn-asset-12; app.js content is unchanged.
The service worker still uses network-first shell fallback and excludes API/POST
requests. App release version remains0.1.30 pending visual approval; no tag or
release has been published and HA deployment remains unchanged.

## Verification

Baseline screenshot captured before background modifications at393x852,DPR3,
mobile/touch, with mocked API state. New comparison script serves both pinned
v0.1.30 files and candidate files in isolated browser contexts. Every browser
request is intercepted, restricted to a dummy localhost origin; commands mutate
only in-memory mocked state. There is no equipment/network path.

Chromium:12 before/after cases at375x812,393x852,430x932; PoolOFF/idle/heating
and Spa heating. Exact DOM geometry and computed control styles compare equal,
including borders, colors, gradients, blur, typography, padding, touch settings,
labels and SVG icons. Main geometry/padding compare equal as well. Screenshots
will differ within translucent tiles because their photographic backdrop changes;
this is expected and not an alteration of tile CSS.

Mocked touch tests preserve target increments, Pool/Spa power, Jets/Waterfall/
Slide, both sanitation controls, Pool Light toggle/effect navigation, restricted
permissions, PIN view/login and subsequent state polling. No horizontal overflow.
app.js is asserted byte-identical to baseline. Authentication/backend/entity maps
remain unchanged and their existing regression suites are exercised.

Local tests:46 standalone Python tests,236 controller tests,4 JS cache/handoff
tests,4 icon artwork tests pass. New static-handler test verifies actual JPEG
delivery/MIME/no-store, dimensions/viewport coverage, and obsolete grass removal.
Worker tests exercise install assets, old cache cleanup, offline photo fallback,
and API/command exclusion. Python/JS syntax and git diff checks pass.

CI additionally runs identical before/after comparisons in WebKit and Chromium,
and uploads all screenshots plus preservation-results.json. Live Safari hardware
safe-area/status-bar behavior is not inferred from a desktop engine; user iPhone
visual approval remains required. No pool equipment test is needed for this scope.

## Acceptance boundary

Actual candidate screenshots, not the image-editor output alone, must be reviewed
against Image A's protected interface and Image B's lawn/background appearance.
Green CI does not grant visual acceptance. Stop after CI/readback and present the
rendered candidate for explicit approval. Do not merge, publish or deploy early.

## Approval and release authorization

The operator explicitly approved the rendered candidate, merge, release and HA
deployment on2026-10-16. The photograph and protected UI are unchanged from
reviewed heada022f6c. Release metadata advances the app to0.1.31; rerun CI on
the resulting exact head before merging and deploy through Supervisor afterward.
No pool equipment actuation is part of this verification. Earlier pending-approval
statements above describe the pre-approval review stage and are superseded here.
