# Pool & Spa family app

The standalone backend exposes only the existing Home Assistant Pool, Spa, Jets/Bubbles, Spillway and Waterslide entities. It does not connect to equipment directly. Spa and features are available to authorized family users; every Pool ON/OFF and temperature request requires a separate Family Home administrator session. Missing authentication configuration denies access.

## Verified family boundary

Use an HTTPS reverse proxy with an isolated backend connection. Configure these app options (or their uppercase environment equivalents):

| Option | Purpose |
| --- | --- |
| `family_trusted_proxies` | Comma-separated exact backend peer IPs, e.g. `127.0.0.1`; no subnet trust or forwarded-address inference. |
| `family_proxy_secret` | Random secret of at least 32 characters known only to proxy and backend. |
| `family_public_origin` | Exact browser HTTPS origin, e.g. `https://pool.example.com`; required on all POST requests. |
| `cf_access_issuer` | Remote-access team issuer, `https://TEAM.cloudflareaccess.com`. |
| `cf_access_audience` | Cloudflare Access application AUD tag. |
| `cf_access_users` | Comma-separated allowed family email identities, matched exactly. |
| `family_admin_handoff_secret` | Separate random secret of at least 32 characters shared only with the Family Home server that authenticates administrators. |

The proxy must remove client-supplied `X-Family-Proxy-Secret` and `X-Family-Boundary` headers and set exactly one of each. It sends the configured secret and `X-Family-Boundary: local` **only** on a listener restricted to verified household local clients. That listener must not be accessible through a remote tunnel or public route. Evaluate actual transport peers or an independently authenticated network boundary, never client-provided forwarding headers. Remote listeners always use `X-Family-Boundary: remote`, preserve the Access application JWT in `Cf-Access-Jwt-Assertion`, and cannot route through the local listener.

The backend checks the actual proxy peer and secret on every API request. Remote requests also require a signed RS256 Cloudflare JWT with the configured issuer, audience, expiry, issued-at, subject, and allowed email. Email/forwarding headers alone grant no access. JWT keys come only from the configured team's certificate endpoint; lookup or verification failures deny access. See [Cloudflare token validation](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/).

Port 8101 remains a backend port: restrict it to the designated proxy with network rules and use loopback or an isolated protected network for the secret-bearing hop. Direct-port API requests without the authenticated proxy boundary are denied even with a remembered PIN or administrator cookie. Static assets and health remain public and issue no controller requests. No network configuration is applied by this code.

Verified local clients need no PIN. Remote clients must authenticate with Cloudflare Access each time their Access session requires it. The legacy PIN endpoint is retained for compatibility, but PIN and remembered-device cookies grant neither family-boundary access nor administrator authority.

## Family Home administrator handoff

Family Home must first authenticate the administrator on its server. It creates the existing `admin_handoff.py` ticket format: base64url JSON payload without padding, a dot, and base64url HMAC-SHA256 signature without padding over the encoded payload. Claims are `aud: pool-spa-family`, `role: admin`, a nonempty `sub`, integer `exp` within the next 60 seconds, and a random 48-character `nonce`. The handoff secret never goes to the browser.

The Pool app's browser at `family_public_origin` exchanges the ticket with `POST /api/admin/handoff`, JSON `{"ticket": "..."}`, through the verified family boundary. Transport tickets in a POST body, never URLs or logs. Family Home's external issuer/UI is not modified here; it must deliver the ticket to the Pool app to complete this exchange. The endpoint rejects invalid, expired and reused tickets and returns a separate 15-minute `family_admin` cookie with HttpOnly, Secure and SameSite=Strict. `/api/permissions` reports current Pool authority; Pool commands check it again server-side. An administrator cookie never bypasses family authentication or POST origin checks.

Administrator sessions are process-local and invalidated when the backend process stops. Consumed nonces are persisted before a session is granted in `/data/admin_used_tickets.json` (override with `ADMIN_REPLAY_FILE` for isolated testing). Replay is rejected across process restarts, and corrupt or unwritable replay data denies handoff access. Run one backend process per replay ledger; its thread lock serializes concurrent exchanges.

## Validation

Install `standalone/requirements.txt` and run `python -m unittest discover -s standalone/tests -v`. Request tests instantiate handlers in memory, use locally generated signing keys, mock every Home Assistant call and prohibit external network requests. They never send equipment commands. The underlying IntelliCenter integration, entity allowlist, service payloads, 70–104°F setpoint bounds, and pending-verification response remain unchanged.

## Integrated Family Home flow

The PIN-free frontend retains the existing Pool/Spa and feature layout. Family Home's administrator Pool link opens a fixed handoff page, obtains a ticket with a CSRF-protected POST, and transfers it with source-window and exact-origin checks. The page exchanges it using the existing same-origin JSON `POST /api/admin/handoff`, then detaches its opener and navigates to the app. Tickets are never URL parameters or browser storage. Configure `family_home_origin`; optional future remote origins use `family_remote_public_origin` and `family_remote_home_origin` and never fall back to the local origins.

See [exact NPM topology/configuration and manual prerequisites](docs/NPM_POOL_FAMILY_CONFIGURATION.md). No proxy, add-on or equipment changes were applied. For full cross-application tests set `FAMILY_HOME_SOURCE` to the Family Home checkout and run the Python suite plus `node --test standalone/tests/js/*.cjs`. Run Family Home tests with `POOL_SOURCE` pointing to this checkout and `PYTHON_BINARY` pointing to Python with the Pool dependencies installed.
