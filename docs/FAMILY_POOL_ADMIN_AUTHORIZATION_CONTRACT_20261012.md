# Pool & Spa Family administrator authorization contract (2026-10-12)

Status: implementation candidate, NOT deployed. Authentication backend baseline was merged in PR #77; PIN-free frontend and integrated Family Home issuance continue on a new development PR and Family Home draft PR #10. No runtime or physical acceptance is claimed.

## Goal
All signed-in household members may view Pool status and control Spa, Jets/Bubbles, Spillway, and Water Slide. Only a verified Family Home administrator may send Pool ON/OFF or Pool setpoint commands. The Pool tile stays visible but its controls are disabled for family sessions.

## Current trust boundary
Family Home authenticates named users and persists role-bound sessions; Pool & Spa Family currently authenticates a shared PIN and persists bearer cookies. The Pool & Spa app cannot infer an administrator from the household PIN, a browser-supplied role, an email address, or a hidden/disabled UI control.

## Required changes before release
1. Establish a short-lived, single-use, server-verifiable handoff assertion issued by Family Home for its currently authenticated, enabled administrator, with audience `pool-spa-family`, expiry, nonce, and user/session binding. Never put Family Home session cookies or HA Supervisor credentials in a URL.
2. Pool & Spa verifies the assertion with a configured secret or authenticated backchannel, consumes the nonce once, and issues a separate, short-lived role-bound app session. Fail closed on expired/replayed/malformed assertions and missing configuration.
3. PIN-only sessions are family role. Persist session role server-side and preserve/revoke legacy sessions explicitly during migration.
4. Before any Home Assistant service call, reject `control=pool` for non-admin sessions with HTTP 403. Leave existing control allowlist, temperature bounds, grid safety, and PoolOS ownership untouched.
5. Expose the effective role through a read-only authenticated endpoint. Disable Pool power and target controls in the frontend for non-admin sessions while preserving status, current temperature, and target display.
6. Verify direct POST attempts are rejected for family sessions, replay and expiry fail, logout/revocation works, and no commands fire on login, refresh, or startup.
7. Validate local and remote URL/TLS routing; current Pool & Spa port 8101 is LAN-only and must not be exposed publicly without a secure authenticated route.
8. Release through CI and Home Assistant app update only after all gates pass, then perform read-only commissioning before any authorized physical commands.

## Deployment gate
Do not deploy a frontend-only restriction or remove the existing PIN gate without a complete replacement.
## Candidate implementation clarification

Verified local proxy access or a verified remote Access JWT establishes family authority; PINs and remembered-device cookies grant no boundary or administrator authority. The frontend removes the PIN screen and keeps all existing tiles/mappings. Family Home resolves its current named administrator session and issues a short-lived ticket only through a CSRF-checked POST. Tickets travel in JSON and origin/source-checked messages, never query strings. Pool exchanges them through `POST /api/admin/handoff`, persists consumed nonces, and grants the separate bounded administrator cookie. Pool ON/OFF/setpoint checks remain server-side.

[Proxy topology and commissioning prerequisites](../standalone/docs/NPM_POOL_FAMILY_CONFIGURATION.md) supersede outdated PIN migration statements above for this candidate. Household network and live NPM host rules remain unverified; no configuration, installation or equipment command is authorized in this task.
