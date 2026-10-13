# Pool & Spa / Family Home proxy commissioning configuration

Status: candidate configuration, not applied. Workflow: GitHub + Home Assistant Autonomous Engineering Workflow v3.2. This task authorizes implementation, mocked tests and PR/CI work only. Merge, add-on update, deployment, restart and equipment commissioning are prohibited. `CI GREEN` does not mean `HA OBSERVED` or `PHYSICALLY COMMISSIONED`.

## Read-only topology evidence, 2026-10-12

| Component | Observed topology |
| --- | --- |
| Nginx Proxy Manager | HA app 4.1.0, NPM upstream v2.16.0 per that app's Dockerfile; `a0d7b954-nginxproxymanager`, `172.30.33.4`; container networking; published 80/81/443. |
| Family Home | Installed 0.1.32, started; `9a6cd3cf-family-home`, `172.30.33.3`; container HTTP 8099 published as host 8102. |
| Pool & Spa Family | Installed 0.1.6, started; host networking, HTTP 8101. Supervisor reports host gateway `172.30.32.1`. |
| Cloudflared | Installed 7.0.17, started; `9074a9fa-cloudflared`, `172.30.33.5`; external hostname empty and additional hosts empty in app options. This does not reveal externally managed tunnel routes. |

NPM's documented `GET /api/nginx/proxy-hosts` was attempted through the HA app API and returned **403 Permission Denied**. Thus current proxy-host entries, access lists, generated nginx rules, certificates, tunnel dashboard routes, LAN/VLAN source preservation and router firewall rules are **not verified**. These are manual commissioning prerequisites, not presumed safe. No access controls were weakened to obtain this evidence. `192.168.1.125` is the HA host address referenced by the existing Family Home source; confirm it is current before applying the upstream configuration.

## Required host entries

| Setting | Pool local | Family Home local |
| --- | --- | --- |
| Domain | `pool-local.davidbuchmd.com` | `home-local.davidbuchmd.com` |
| Forward scheme | `http` | `http` |
| Forward host | `192.168.1.125` | `9a6cd3cf-family-home` |
| Forward port | `8101` | `8099` |
| TLS | Valid certificate for exact hostname; Force SSL | Same |
| Cache assets / websocket support | Off / off | Off / off |
| Custom locations | None | None |
| Public tunnel route | None | None |

Use private/split DNS that resolves local hostnames to the HA LAN address. Do not forward WAN 80/443/8101/8102 to a local family listener. Certificate issuance should use DNS validation; keep any DNS API credential private in NPM. A public DNS record alone does not establish household-local trust. Confirm guest/untrusted VLANs cannot reach the trusted household listener.

## Exact local proxy Advanced configuration

NPM v2.16.0 inserts Advanced text at **server** scope. Its default `location /` defines its own proxy headers, so adding a secret only at server scope can fail nginx header inheritance. Replace the default location explicitly, using the complete block below, rather than just appending header directives at server scope. NPM detects `location /` and suppresses its generated default location. Leave custom locations empty so they cannot introduce a bypass. Validate the generated configuration before any authorized future reload.

The following source check assumes **192.168.1.0/24 has been independently verified as the trusted household network**. If it includes guests or untrusted devices, use the approved household IP set/VLAN instead; keep all other sources denied. If NAT hides client source behind a router/gateway, do not allow the gateway as a substitute: correct source preservation or provide an independently authenticated local network boundary first. IPv6 is denied until an explicit household IPv6 policy is reviewed.

For `pool-local.davidbuchmd.com`:

```nginx
# $realip_remote_addr preserves the connection peer before real-IP rewriting.
# Never classify by X-Forwarded-For, X-Real-IP or CF-Connecting-IP.
if ($realip_remote_addr !~ "^192[.]168[.]1[.][0-9]{1,3}$") { return 403; }
if ($scheme != "https") { return 403; }
location / {
    proxy_set_header Host pool-local.davidbuchmd.com;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For "";
    proxy_set_header X-Real-IP "";
    proxy_set_header X-Family-Boundary local;
    proxy_set_header X-Family-Proxy-Secret "REPLACE_WITH_POOL_PROXY_SECRET";
    proxy_set_header Cf-Access-Jwt-Assertion "";
    proxy_set_header Cf-Access-Authenticated-User-Email "";
    proxy_pass http://192.168.1.125:8101;
}
```

For `home-local.davidbuchmd.com`, use the same **server-level** peer and HTTPS checks and complete `location /`, with these exact substitutions:

```nginx
proxy_set_header Host home-local.davidbuchmd.com;
proxy_set_header X-Family-Proxy-Secret "REPLACE_WITH_FAMILY_HOME_PROXY_SECRET";
proxy_pass http://9a6cd3cf-family-home:8099;
```

All other lines remain the same. The literal `local` classification and secret replace client headers, including duplicate supplied headers. Keep these secrets distinct from each other and from the shared ticket-signing secret. Use a protected internal proxy-to-backend hop; do not expose the secret-bearing upstream publicly or log request/response bodies, cookies or secret headers.

With this topology, Pool's immediate peer is expected to be NPM `172.30.33.4`, not the LAN client. Family Home should use NPM's direct container route and observe that same peer. Do not broaden trust to the Supervisor gateway, all Docker peers, all private addresses, or a forwarded client address. If the observed peer differs, record and verify the actual route before configuring its exact address. Secrets are still required even from an allowlisted peer.

## App configuration prerequisites

Generate all secrets privately, at least 32 random characters each. Do not paste them into GitHub, chat transcripts or logs.

| Pool app option | Value |
| --- | --- |
| `family_trusted_proxies` | `172.30.33.4` after confirming actual backend peer |
| `family_proxy_secret` | Pool-specific secret matching the local NPM location |
| `family_public_origin` | `https://pool-local.davidbuchmd.com` |
| `family_home_origin` | `https://home-local.davidbuchmd.com` |
| `family_admin_handoff_secret` | Shared signing secret matching Family Home `pool_handoff_secret` |
| `family_remote_public_origin`, `family_remote_home_origin` | Empty until separately commissioned |
| `cf_access_issuer`, `cf_access_audience`, `cf_access_users` | Empty until separately commissioned |

`family_pin` is legacy backend compatibility only. No PIN input, PIN login call or PIN-dependent authorization remains in the Pool frontend.

| Family Home app option | Value |
| --- | --- |
| `proxy_secret` | Family Home-specific secret matching its NPM location |
| `trusted_proxy_ips` | `172.30.33.4`, or resolve the NPM container DNS with the existing startup mechanism |
| `public_origin` | `https://home-local.davidbuchmd.com` |
| `pool_local_origin` | `https://pool-local.davidbuchmd.com` |
| `pool_handoff_secret` | Shared signing secret matching Pool `family_admin_handoff_secret` |
| `remote_origin`, `pool_remote_origin` | Empty until separately commissioned |

The existing `session_secret` and administrator credentials remain private and unchanged. This candidate now requires the proxy secret on forwarded Family Home HTTPS transport; prepare the proxy and matching option before any future authorized installation to avoid locking out sign-in. Direct HTTP published ports cannot spoof HTTPS to create sessions. Network rules must additionally restrict backend 8101/8102 to NPM; the application guards reject missing/forged secrets independently. Removing published Family Home 8102 is preferable when all callers use the internal container route, but is a later authorized network change.

## Future remote Access hostname

Create a **separate** host `pool.davidbuchmd.com` and separate Access application; never publish or tunnel `pool-local.davidbuchmd.com`. The remote Pool proxy location must set `Host pool.davidbuchmd.com`, `X-Family-Boundary remote`, and the Pool proxy secret, and preserve `Cf-Access-Jwt-Assertion` from Access. Its tunnel must connect to this remote virtual host with the correct Host header, over a protected verified route. The local peer check above rejects Cloudflared `172.30.33.5`, router/NAT peers and forged forwarding even if someone targets the local Host header.

Set Pool `family_remote_public_origin=https://pool.davidbuchmd.com`, the **remote** `family_remote_home_origin` matching the independently reviewed remote Family Home HTTPS address, issuer `https://TEAM.cloudflareaccess.com`, the Pool application's exact audience, and explicit allowed family emails. Verify RS256 signature, issuer, audience, expiry, issued-at and identity. Remote identity headers alone are never sufficient. Missing remote settings cannot fall back to local POST or handoff origins.

For future remote Home, configure Family Home `remote_origin` and `pool_remote_origin=https://pool.davidbuchmd.com`, plus an independently Access-protected Home host that sets `X-Family-Boundary remote`, forwarded HTTPS and its own proxy secret. Enable `remote_access` only for explicitly approved administrators; Pool has its own Access email allowlist. A remote route cannot mint a ticket for the local destination. Review Home's remote access policy for all other Home endpoints before exposure; this change gates remote Pool-ticket issuance, not every unrelated Home API.

## Administrator browser flow and limits

The signed-in Family Home administrator clicks the existing Pool link. It opens the fixed `/admin-handoff.html` page without ticket data. The Pool page announces readiness to its configured Home origin. Home checks both source window and exact origin, then POSTs with its session CSRF token to `/api/pool-admin-handoff`. Home resolves the current enabled administrator session, checks origin, JSON, proxy boundary and remote eligibility, and returns a no-store JSON ticket. Home sends it only to that Pool window/origin using `postMessage`.

Pool checks both opener and exact Home origin, exchanges the ticket via same-origin JSON `POST /api/admin/handoff`, detaches its opener, and replaces the page with `/`. It never navigates with a ticket, writes one to storage, or logs one. Keep the two HTTPS sites within the same `davidbuchmd.com` site so Strict cookies work; do not add a Cross-Origin-Opener-Policy that severs this explicitly used popup connection. Popup blocking, missing configuration, expired Home sessions or Access sessions fail with a recoverable message. A family member opens the ordinary Pool URL with `noopener noreferrer` and never receives an administrator ticket.

The existing verifier consumes each nonce once, persists consumption before granting a session, and rejects expired, concurrent or restart replay. The Pool administrator cookie lasts at most 15 minutes and is host-scoped, HttpOnly, Secure and SameSite=Strict. Home logout/revocation stops new ticket issuance; already-issued Pool sessions retain only their bounded 15-minute lifetime and do not become indefinite Home sessions. Every Pool command rechecks current family identity and administrator expiry; family sessions retain Spa and feature commands only. No startup, refresh, handoff or login sends equipment commands.

## Manual read-only commissioning gate

After a separate authorized merge/configuration/deployment phase, verify certificates, split DNS, household network membership, actual peer IPs, generated location rules, and tunnel routes. From LAN verify family status and disabled Pool controls without issuing commands. From a non-household/tunnel connection targeting the local Host header expect 403. Direct 8101/8102 requests with forged forwarding/role/email headers or existing cookies must not grant family or administrator access. Validate the popup on the target Safari/iOS/browser setup, including blocked-popup recovery, and verify expiry with read-only `/api/permissions`. Remote Access tests are a separate future gate; never send real equipment commands merely to prove authentication.

Sources: [HA NPM 4.1.0 Dockerfile](https://github.com/hassio-addons/app-nginx-proxy-manager/blob/v4.1.0/proxy-manager/Dockerfile), [NPM 2.16.0 host template](https://github.com/NginxProxyManager/nginx-proxy-manager/blob/v2.16.0/backend/templates/proxy_host.conf), [NPM proxy include](https://github.com/NginxProxyManager/nginx-proxy-manager/blob/v2.16.0/docker/rootfs/etc/nginx/conf.d/include/proxy.conf), [nginx real-IP module](https://nginx.org/en/docs/http/ngx_http_realip_module.html).

The paired [Family Home acceptance record](https://github.com/davidabuch/Family_Home/blob/feature/pool-spa-profile-permission-20261012/docs/POOL_HANDOFF_ACCEPTANCE.md) distinguishes CODE TESTED, current-head CI GREEN, metadata-only HA OBSERVED, and unrun runtime/physical commissioning.
