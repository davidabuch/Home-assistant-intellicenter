# Changelog

## 0.1.33

- Prevent native iOS text selection and callouts during administrator heat-preference long press.
- Register one long-press handler per persistent Pool/Hot Tub tile to avoid duplicate timers.


## 0.1.32

- Add administrator-only Pool/Hot Tub long-press heating preference selector (Solar, Gas, Eco Heat, Off).
- Server enforces administrator session and validates Home Assistant helper options; heating Off does not stop circulation.
- Preserve existing controls and pass browser visual/security regression checks.


## 0.1.31

- Replace failed lawn overlays with the user-approved finished sunset pool/lawn photograph.
- Preserve all control geometry, glass styling, state handling, authentication and equipment behavior.
- Retire obsolete grass textures and refresh the PWA shell cache; verify Chromium/WebKit UI preservation.

## 0.1.11

- Crop approved originals to full-bleed squares without borders, padding, pre-rounded corners or distortion.
- Add public Apple touch and precomposed icon routes, versioned v2 references, and refreshed PWA/favicons.
- Verify unchanged originals, pixels, dimensions, local/remote handler equality and existing security regressions.

## 0.1.10

- Use the verified approved artwork for Apple touch icons, browser favicons and 192/512px PWA icons.
- Serve identical icon bytes on local and remote origins; preserve authentication and controls.
