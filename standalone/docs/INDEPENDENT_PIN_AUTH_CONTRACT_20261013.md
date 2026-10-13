# Pool & Spa Family — independent device PIN authorization contract

Status: approved behavior, implementation in progress; NOT deployed.

## Scope

Pool & Spa Family remains a separate application. Family Home may link to it, but MUST NOT grant or transfer Pool privileges. The existing Nginx proxy hosts are intentionally left without custom advanced directives. Family Music is out of scope.

## Device roles

- Family: enter the existing family PIN once, retain a server-side revocable, HttpOnly Secure SameSite session cookie for 180 days. May read all current pool/spa status and operate Spa, Jets/Bubbles, Spillway and Water Slide. Pool ON/OFF and Pool target temperature are displayed, visibly disabled, and rejected by the server with HTTP 403.
- Administrator: enter a **different** administrator PIN (at least four digits) once, retain an independently tracked revocable administrator session on that device. May use all currently available controls including Pool ON/OFF and target temperature. Admin PIN must be separately configured and must never be embedded in code, browser storage, URLs, logs or frontend bundles.
- Sessions must be bound to the role issued on authentication. Existing family sessions must never be silently upgraded to administrator. Rotating the administrator PIN must invalidate administrator sessions. Invalid or missing PIN configuration must fail closed for admin privileges.

## Trust boundaries

- Do not use Family Home login, cross-origin popup messages, proxy-injected shared secrets or admin handoff tickets as authorization.
- A local/vpn route must not rely on client-supplied forwarded headers to determine trust. The HTTPS reverse proxy, DNS, tunnel and Cloudflare Access configuration must be independently verified before any remote publication.
- Cloudflare protection of the away address is an **additional** boundary, not a replacement for server-side device role enforcement. Do not accept an unverified Cloudflare identity header from a direct client.
- Do not publish HTTP 8101 or a bypass route to the public internet.

## Required automated acceptance tests

1. No PIN, invalid PIN, and missing admin PIN fail closed; rate-limit failed login attempts.
2. Family PIN creates family-only session; restart retains role; session expires and logout revokes it.
3. Family session can read state and operate spa/features; all Pool on/off/setpoint POSTs return 403 without any Home Assistant service call.
4. Administrator PIN creates administrator session; Pool on/off/setpoint passes existing command validation and invokes the expected HA service exactly once.
5. Family PIN cannot become administrator via cookies, request JSON, headers, role tampering or cross-origin handoff.
6. Admin PIN rotation invalidates existing admin sessions; a family PIN rotation does not elevate or preserve invalid sessions.
7. Frontend Pool controls are disabled for family but readable; administrator controls are enabled only after server-provided permissions.
8. Preserve equipment command validation, CSRF/origin checks for authenticated mutations, session persistence, and a tested rollback to currently installed 0.1.6.
9. No physical pool commands during CI or mock tests; physical commissioning requires a separately authorized envelope.

## Release gate

Do not deploy the currently offered 0.1.7 proxy-auth release. Prepare a subsequent version only after backend/frontend tests, code review, CI, local proxy verification, and a rollback backup. Preserve running Family Home 0.1.30, Pool & Spa 0.1.6, Family Music 0.2.23 until then.
