"""Request-level authentication tests: no sockets or equipment requests."""
import base64
import hashlib
import hmac
import importlib.util
import io
import json
import time
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family_server_acceptance", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
SECRET = "test-only-shared-secret-not-used-in-production-1234"
ORIGIN = "https://family.example.test"
ISSUER = "https://test.cloudflareaccess.com"


def ticket(**updates):
    claims = {"aud": "pool-spa-family", "role": "admin", "sub": "home-admin",
              "exp": int(time.time()) + 45, "nonce": "a" * 48}
    claims.update(updates)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return payload + "." + signature


class AuthenticationAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.replay_file = Path(directory.name) / "used.json"
        self.auth = server.AdminHandoff(SECRET, replay_file=self.replay_file)
        self.keys = Mock()
        self.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.key.public_key())
        self.settings = patch.multiple(server, TRUSTED_PROXIES=frozenset({"127.0.0.1"}),
                                      PROXY_SECRET=SECRET, PUBLIC_ORIGIN=ORIGIN, REMOTE_PUBLIC_ORIGIN=ORIGIN,
                                      FAMILY_HOME_ORIGIN="https://home-local.davidbuchmd.com",
                                      REMOTE_FAMILY_HOME_ORIGIN="https://home.davidbuchmd.com",
                                      CF_ISSUER=ISSUER, CF_AUDIENCE="family-aud",
                                      CF_USERS=frozenset({"family@example.test"}),
                                      CF_KEYS=self.keys, ADMIN_HANDOFF=self.auth, PIN="")
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.ha = patch.object(server, "ha_request", return_value={"state": "off"}).start()
        self.addCleanup(patch.stopall)
        # Fail immediately if any path escapes the HA/JWKS mocks.
        patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("Network forbidden")).start()

    def request(self, path="/api/control", body=None, headers=None, peer="127.0.0.1", method="POST"):
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.client_address = (peer, 12345)
        handler.headers = Message()
        defaults = {"X-Family-Proxy-Secret": SECRET, "X-Family-Boundary": "local",
                    "Origin": ORIGIN, "Content-Type": "application/json"}
        defaults.update(headers or {})
        raw = json.dumps(body if body is not None else {"control": "spa", "operation": "on"}).encode()
        defaults.setdefault("Content-Length", str(len(raw)))
        for key, value in defaults.items():
            if value is not None:
                handler.headers[key] = value
        handler.rfile = io.BytesIO(raw)
        handler.send_json = Mock()
        getattr(handler, "do_" + method)()
        args, kwargs = handler.send_json.call_args
        return (args[1] if len(args) > 1 else kwargs.get("code", 200)), args[0], kwargs.get("cookie")

    def remote_token(self, **updates):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": "family-aud", "exp": now + 300,
                  "iat": now, "sub": "family-user", "email": "family@example.test"}
        claims.update(updates)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test"})

    def admin_cookie(self):
        status, _, cookie = self.request("/api/admin/handoff", {"ticket": ticket()})
        self.assertEqual(status, 200)
        for flag in ["HttpOnly", "Secure", "SameSite=Strict", "Max-Age=900"]:
            self.assertIn(flag, cookie)
        self.ha.assert_not_called()
        return cookie.split(";", 1)[0]

    def test_pin_free_verified_local_family_controls(self):
        for key, entity, domain in [("spa", "climate.hot_tub_thermostat", "climate"),
                                     ("jets", "switch.jets_bubbles", "switch"),
                                     ("spillway", "switch.spillway", "switch"),
                                     ("slide", "switch.water_slide", "switch")]:
            for op in ["on", "off"]:
                with self.subTest(key=key, operation=op):
                    status, result, _ = self.request(body={"control": key, "operation": op})
                    self.assertEqual(status, 200)
                    self.assertEqual(result, {"accepted": True, "pending_verification": True})
                    if domain == "climate":
                        service, payload = "set_hvac_mode", {"entity_id": entity, "hvac_mode": "heat" if op == "on" else "off"}
                    else:
                        service, payload = "turn_" + op, {"entity_id": entity}
                    self.ha.assert_called_with(f"/api/services/{domain}/{service}", payload)
        self.assertEqual(self.request(body={"control": "spa", "operation": "temperature", "value": 100})[0], 200)
        self.ha.assert_called_with("/api/services/climate/set_temperature", {"entity_id": "climate.hot_tub_thermostat", "temperature": 100})

    def test_direct_port_and_forged_headers_rejected(self):
        cases = [("192.168.1.20", {}), ("127.0.0.1", {"X-Family-Proxy-Secret": None}),
                 ("127.0.0.1", {"X-Family-Proxy-Secret": "forged"}),
                 ("127.0.0.1", {"X-Family-Boundary": None}),
                 ("127.0.0.1", {"X-Family-Boundary": "unknown"})]
        for peer, headers in cases:
            headers.update({"X-Forwarded-For": "127.0.0.1", "X-Forwarded-Proto": "https",
                            "Cf-Access-Authenticated-User-Email": "family@example.test",
                            "Cookie": "session=remembered; family_admin=forged"})
            with self.subTest(peer=peer, headers=headers):
                for path, method in [("/api/control", "POST"), ("/api/login", "POST"),
                                     ("/api/admin/handoff", "POST"), ("/api/state", "GET"),
                                     ("/api/permissions", "GET"), ("/api/handoff/config", "GET"),
                                     ("/admin-handoff.html", "GET"), ("/admin-handoff.js", "GET")]:
                    self.assertEqual(self.request(path, headers=headers, peer=peer, method=method)[0], 401)
        self.ha.assert_not_called()

    def test_missing_boundary_configuration_fails_closed(self):
        for setting, value in [("TRUSTED_PROXIES", frozenset()), ("PROXY_SECRET", ""), ("PROXY_SECRET", "short")]:
            with self.subTest(setting=setting), patch.object(server, setting, value):
                self.assertEqual(self.request()[0], 401)
        self.ha.assert_not_called()

    def test_remote_requires_signed_allowlisted_identity(self):
        headers = {"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": self.remote_token()}
        self.assertEqual(self.request(headers=headers)[0], 200)
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[1], {"pool_control": False})

    def test_invalid_remote_tokens_fail_closed(self):
        tokens = [None, "forged", self.remote_token(exp=int(time.time()) - 1),
                  self.remote_token(aud="wrong"), self.remote_token(iss="https://evil.test"),
                  self.remote_token(email="outsider@example.test"), self.remote_token(sub=""),
                  self.remote_token(iat=int(time.time()) + 300),
                  jwt.encode({"email": "family@example.test"}, SECRET, algorithm="HS256")]
        for token in tokens:
            with self.subTest(token=token):
                self.assertEqual(self.request(headers={"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": token})[0], 401)
        for setting, value in [("CF_KEYS", None), ("CF_AUDIENCE", ""), ("CF_USERS", frozenset())]:
            with patch.object(server, setting, value):
                self.assertEqual(self.request(headers={"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": self.remote_token()})[0], 401)
        self.keys.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError("offline")
        self.assertEqual(self.request(headers={"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": self.remote_token()})[0], 401)
        self.ha.assert_not_called()

    def test_pool_all_operations_require_admin_even_with_pin_cookie(self):
        with patch.object(server, "PIN", "1234"), patch.dict(server.SESSIONS, {"remembered": time.time() + 500}):
            for op in ["on", "off", "temperature"]:
                self.assertEqual(self.request(body={"control": "pool", "operation": op, "value": 80},
                                              headers={"Cookie": "session=remembered"})[0], 403)
        self.ha.assert_not_called()

    def test_admin_handoff_enables_pool_commands_and_permissions(self):
        headers = {"Cookie": self.admin_cookie()}
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[1], {"pool_control": True})
        for op in ["on", "off", "temperature"]:
            self.assertEqual(self.request(body={"control": "pool", "operation": op, "value": 80}, headers=headers)[0], 200)
            service = "set_temperature" if op == "temperature" else "set_hvac_mode"
            payload = {"entity_id": "climate.pool_thermostat"}
            payload.update({"temperature": 80} if op == "temperature" else {"hvac_mode": "heat" if op == "on" else "off"})
            self.ha.assert_called_with("/api/services/climate/" + service, payload)

    def test_expired_admin_session_and_direct_access_rejected(self):
        headers = {"Cookie": self.admin_cookie()}
        self.assertEqual(self.request(headers=headers, peer="192.168.1.20")[0], 401)
        self.auth.clock = lambda: time.time() + 901
        self.assertEqual(self.request(body={"control": "pool", "operation": "on"}, headers=headers)[0], 403)
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[1], {"pool_control": False})
        self.ha.assert_not_called()

    def test_handoff_invalid_expired_and_replayed_tickets(self):
        signed = ticket()
        self.assertEqual(self.request("/api/admin/handoff", {"ticket": signed})[0], 200)
        invalid = [signed, ticket(exp=int(time.time()) - 1), ticket(exp=int(time.time()) + 120),
                   ticket(role="family"), ticket(aud="wrong"), ticket(sub=""), ticket(nonce="short"),
                   None, [], "é.x", "a.é", signed[:-2] + "xx"]
        for value in invalid:
            with self.subTest(ticket=value):
                self.assertEqual(self.request("/api/admin/handoff", {"ticket": value})[0], 403)
        with patch.object(server, "ADMIN_HANDOFF", None):
            self.assertEqual(self.request("/api/admin/handoff", {"ticket": ticket(nonce="b" * 48)})[0], 403)
        self.ha.assert_not_called()

    def test_cross_origin_and_non_json_writes_rejected(self):
        for headers in [{"Origin": None}, {"Origin": "https://evil.test"},
                        {"Sec-Fetch-Site": "cross-site"}, {"Content-Type": "text/plain"}]:
            for path in ["/api/control", "/api/admin/handoff", "/api/login"]:
                self.assertIn(self.request(path, headers=headers)[0], [403, 415])
        self.ha.assert_not_called()

    def test_restart_preserves_consumed_tickets_and_revokes_sessions(self):
        cookie = self.admin_cookie()
        restarted = server.AdminHandoff(SECRET, replay_file=self.replay_file)
        with patch.object(server, "ADMIN_HANDOFF", restarted):
            self.assertEqual(self.request("/api/admin/handoff", {"ticket": ticket()})[0], 403)
            self.assertEqual(self.request(body={"control": "pool", "operation": "on"}, headers={"Cookie": cookie})[0], 403)
        self.ha.assert_not_called()

    def test_replay_ledger_errors_deny_authority(self):
        with patch.object(Path, "mkdir", side_effect=OSError("read only")):
            self.assertEqual(self.request("/api/admin/handoff", {"ticket": ticket()})[0], 403)
        self.assertFalse(self.auth.sessions)
        self.replay_file.write_text("invalid json")
        with self.assertRaises(server.HandoffError):
            server.AdminHandoff(SECRET, replay_file=self.replay_file)
        self.ha.assert_not_called()

    def test_concurrent_handoff_replay_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        signed = ticket()
        def exchange(_):
            try:
                server.consume_admin_handoff(signed)
                return True
            except server.HandoffError:
                return False
        with ThreadPoolExecutor(max_workers=8) as executor:
            self.assertEqual(sum(executor.map(exchange, range(16))), 1)
        self.ha.assert_not_called()

    def test_remote_admin_still_requires_current_remote_identity(self):
        headers = {"Cookie": self.admin_cookie(), "X-Family-Boundary": "remote",
                   "Cf-Access-Jwt-Assertion": self.remote_token()}
        self.assertEqual(self.request(body={"control": "pool", "operation": "on"}, headers=headers)[0], 200)
        self.ha.reset_mock()
        headers["Cf-Access-Jwt-Assertion"] = self.remote_token(exp=int(time.time()) - 1)
        self.assertEqual(self.request(body={"control": "pool", "operation": "off"}, headers=headers)[0], 401)
        self.ha.assert_not_called()

    def test_duplicate_security_headers_are_not_assertions(self):
        handler = object.__new__(server.Handler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.headers = Message()
        handler.headers["X-Family-Proxy-Secret"] = SECRET
        handler.headers["X-Family-Boundary"] = "local"
        handler.headers["X-Family-Boundary"] = "remote"
        self.assertFalse(handler.family_authorized())
        handler.headers["X-Family-Proxy-Secret"] = SECRET
        self.assertFalse(server.trusted_proxy(handler))
        self.ha.assert_not_called()

    def test_handoff_config_requires_family_boundary_and_separates_remote_origin(self):
        self.assertEqual(self.request("/api/handoff/config", method="GET")[1], {"home_origin": "https://home-local.davidbuchmd.com"})
        self.assertEqual(self.request("/api/handoff/config", method="GET", peer="192.168.1.20")[0], 401)
        headers={"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": self.remote_token()}
        self.assertEqual(self.request("/api/handoff/config", method="GET", headers=headers)[1], {"home_origin": "https://home.davidbuchmd.com"})
        with patch.object(server, "REMOTE_FAMILY_HOME_ORIGIN", ""):
            self.assertEqual(self.request("/api/handoff/config", method="GET", headers=headers)[0], 503)
        self.ha.assert_not_called()

    def test_remote_origin_never_falls_back_to_local_post_origin(self):
        headers={"X-Family-Boundary": "remote", "Cf-Access-Jwt-Assertion": self.remote_token()}
        with patch.object(server, "REMOTE_PUBLIC_ORIGIN", "https://pool.davidbuchmd.com"):
            self.assertEqual(self.request(headers=headers)[0], 403)
            self.assertEqual(self.request(headers={**headers, "Origin": "https://pool.davidbuchmd.com"})[0], 200)
        self.ha.reset_mock()
        with patch.object(server, "REMOTE_PUBLIC_ORIGIN", ""):
            self.assertEqual(self.request(headers=headers)[0], 403)
        self.ha.assert_not_called()

    def test_frontend_has_no_pin_dependency_and_preserves_control_layout(self):
        html=(ROOT / "web/index.html").read_text()
        script=(ROOT / "web/app.js").read_text()
        for value in ['id="pin"', 'id="signin"', 'Household PIN']:
            self.assertNotIn(value, html)
        for value in ['$("pin")', '$("signin")', 'api("login"']:
            self.assertNotIn(value, script)
        for name in ['pool', 'spa', 'features', 'controls']:
            self.assertIn(f'id="{name}"', html)
        self.assertIn('key==="pool"&&!permissions.pool_control', script)

    def test_request_logs_never_include_ticket_query_strings(self):
        handler=object.__new__(server.Handler)
        handler.client_address=("127.0.0.1", 1234)
        handler.command="GET"
        handler.path="/api/admin-handoff?ticket=secret-mock-ticket"
        with patch("builtins.print") as output:
            handler.log_message('"%s"', "GET " + handler.path)
        self.assertNotIn("secret-mock-ticket", str(output.call_args))

    def test_family_home_real_signer_matches_pool_request_verifier(self):
        import os, subprocess
        source=os.environ.get("FAMILY_HOME_SOURCE")
        if not source:
            self.skipTest("Set FAMILY_HOME_SOURCE for cross-repository signing verification")
        module=(Path(source)/"lib/pool-handoff.js").resolve().as_uri()
        script="""const {issuePoolTicket}=await import(process.argv[1]);
const session={id:'mock-session-hash',expires:Date.now()+300000,user:{id:'home-admin',role:'admin',enabled:true}};
process.stdout.write(issuePoolTicket(session,process.argv[2]));"""
        signed=subprocess.run([os.environ.get("NODE_BINARY", "node"), "--input-type=module", "-e", script, module, SECRET],
                              check=True, capture_output=True, text=True).stdout
        status, _, cookie=self.request("/api/admin/handoff", {"ticket":signed})
        self.assertEqual(status,200)
        self.assertEqual(self.request(body={"control":"pool","operation":"on"}, headers={"Cookie":cookie.split(";",1)[0]})[0],200)
        self.ha.assert_called_once_with("/api/services/climate/set_hvac_mode", {"entity_id":"climate.pool_thermostat","hvac_mode":"heat"})
        self.ha.reset_mock()
        self.assertEqual(self.request("/api/admin/handoff", {"ticket":signed})[0],403)
        self.ha.assert_not_called()

    def test_allowlist_and_command_validation(self):
        self.assertEqual(server.CONTROLS, {"pool": ("climate.pool_thermostat", "climate"),
                         "spa": ("climate.hot_tub_thermostat", "climate"), "jets": ("switch.jets_bubbles", "switch"),
                         "spillway": ("switch.spillway", "switch"), "slide": ("switch.water_slide", "switch")})
        bodies = [{"control": "switch.arbitrary", "operation": "on"}, {"control": [], "operation": "on"},
                  {"control": "jets", "operation": "temperature", "value": 80},
                  {"control": "spa", "operation": "toggle"}]
        bodies += [{"control": "spa", "operation": "temperature", "value": v} for v in [True, "80", 69, 105, float("nan"), float("inf")]]
        for body in bodies:
            self.assertEqual(self.request(body=body)[0], 400)
        self.ha.assert_not_called()

    def test_state_reads_only_allowlisted_entities(self):
        self.assertEqual(self.request("/api/state", method="GET")[0], 200)
        self.assertEqual([call.args[0] for call in self.ha.call_args_list],
                         ["/api/states/" + entity for entity, _ in server.CONTROLS.values()] +
                         ["/api/states/" + entity for entity in server.READ_ONLY])

    def test_ha_failure_retains_existing_error_behavior(self):
        self.ha.side_effect = RuntimeError("unavailable")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.request("/api/state", method="GET")[0], 503)


if __name__ == "__main__":
    unittest.main()
