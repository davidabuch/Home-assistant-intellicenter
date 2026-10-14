"""Request-level role authorization regression tests. No sockets or physical commands."""
import importlib.util
import io
import json
import tempfile
import time
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family_server_acceptance", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
ORIGIN = "https://pool-local.example.test"
REMOTE = "https://pool.example.test"


class AuthenticationAcceptance(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.sessions = server.DeviceSessions(Path(directory.name) / "sessions.json", "1234", "9876")
        self.settings = patch.multiple(server, SESSIONS=self.sessions, PUBLIC_ORIGIN=ORIGIN,
                                       REMOTE_PUBLIC_ORIGIN=REMOTE, LOGIN_ATTEMPTS={})
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.ha_patch = patch.object(server, "ha_request", return_value={"state": "off"})
        self.ha = self.ha_patch.start()
        self.addCleanup(self.ha_patch.stop)
        self.network = patch.object(server.urllib.request, "urlopen",
                                    side_effect=AssertionError("Network forbidden")).start()
        self.addCleanup(patch.stopall)

    def request(self, path="/api/control", body=None, headers=None, method="POST", peer="127.0.0.1"):
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.client_address = (peer, 12345)
        handler.headers = Message()
        defaults = {"Host": "pool-local.example.test", "Origin": ORIGIN,
                    "Content-Type": "application/json"}
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

    def login(self, pin):
        status, data, cookie = self.request("/api/login", {"pin": pin})
        self.assertEqual(status, 200, data)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Max-Age=", cookie)
        self.ha.assert_not_called()
        return {"Cookie": cookie.split(";", 1)[0]}

    def test_unauthenticated_state_and_commands_rejected(self):
        for path, method in [("/api/state", "GET"), ("/api/permissions", "GET"),
                             ("/api/control", "POST"), ("/api/logout", "POST")]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path, method=method)[0], 401)
        self.ha.assert_not_called()

    def test_family_can_use_spa_and_features(self):
        headers = self.login("1234")
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[1],
                         {"pool_control": False, "light_control": False})
        for key, entity, domain in [("spa", "climate.hot_tub_thermostat", "climate"),
                                     ("jets", "switch.jets_bubbles", "switch"),
                                     ("spillway", "switch.spillway", "switch"),
                                     ("slide", "switch.water_slide", "switch")]:
            for operation in ("on", "off"):
                with self.subTest(key=key, operation=operation):
                    self.assertEqual(self.request(body={"control": key, "operation": operation},
                                                  headers=headers)[0], 200)
                    if domain == "climate":
                        expected = ("set_hvac_mode", {"entity_id": entity,
                                    "hvac_mode": "heat" if operation == "on" else "off"})
                    else:
                        expected = ("turn_" + operation, {"entity_id": entity})
                    self.ha.assert_called_with("/api/services/" + domain + "/" + expected[0],
                                               expected[1])
        self.assertEqual(self.request(body={"control": "spa", "operation": "temperature",
                                            "value": 100}, headers=headers)[0], 200)

    def test_family_pool_mutations_denied_before_ha(self):
        headers = self.login("1234")
        for operation in ("on", "off", "temperature"):
            with self.subTest(operation=operation):
                status, data, _ = self.request(body={"control": "pool", "operation": operation,
                                                     "value": 80}, headers=headers)
                self.assertEqual(status, 403)
                self.assertIn("Administrator", data["error"])
        self.ha.assert_not_called()

    def test_admin_controls_and_permissions(self):
        headers = self.login("9876")
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[1],
                         {"pool_control": True, "light_control": True})
        for operation in ("on", "off", "temperature"):
            status, _, _ = self.request(body={"control": "pool", "operation": operation,
                                              "value": 80}, headers=headers)
            self.assertEqual(status, 200)
            service = "set_temperature" if operation == "temperature" else "set_hvac_mode"
            payload = {"entity_id": "climate.pool_thermostat"}
            payload.update({"temperature": 80} if operation == "temperature"
                           else {"hvac_mode": "heat" if operation == "on" else "off"})
            self.ha.assert_called_with("/api/services/climate/" + service, payload)

    def test_light_effect_permissions_and_validation(self):
        family = self.login("1234")
        for operation in ("on", "off", "effect"):
            self.assertEqual(self.request(body={"control": "light", "operation": operation, "value": "Blue"}, headers=family)[0], 403)
        self.ha.assert_not_called()
        status, data, _ = self.request("/api/state", headers=family, method="GET")
        self.assertEqual(status, 200)
        self.assertNotIn("light", data)
        self.ha.reset_mock()
        admin = self.login("9876")
        self.ha.return_value = {"state": "off", "attributes": {"effect_list": ["Blue", "Party Mode"]}}
        status, data, _ = self.request("/api/state", headers=admin, method="GET")
        self.assertEqual(status, 200)
        self.assertIn("light", data)
        self.ha.reset_mock()
        self.assertEqual(self.request(body={"control": "light", "operation": "effect", "value": "Not Listed"}, headers=admin)[0], 400)
        self.assertEqual(self.request(body={"control": "light", "operation": "effect", "value": "Blue"}, headers=admin)[0], 200)
        self.ha.assert_called_with("/api/services/light/turn_on", {"entity_id": "light.pool_light", "effect": "Blue"})

    def test_no_role_escalation_via_headers_or_body(self):
        headers = self.login("1234")
        headers.update({"X-Family-Boundary": "local", "X-Family-Proxy-Secret": "forged",
                        "Cf-Access-Authenticated-User-Email": "admin@example.test",
                        "X-Forwarded-For": "127.0.0.1", "X-Role": "admin"})
        self.assertEqual(self.request(body={"control": "pool", "operation": "on",
                                             "role": "admin"}, headers=headers)[0], 403)
        self.assertEqual(self.request("/api/admin/handoff", {"ticket": "forged"},
                                      headers=headers)[0], 404)
        self.ha.assert_not_called()

    def test_login_errors_and_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.request("/api/login", {"pin": "wrong"})[0], 401)
        self.assertEqual(self.request("/api/login", {"pin": "9876"})[0], 429)
        self.ha.assert_not_called()

    def test_origin_and_host_enforcement(self):
        headers = self.login("1234")
        for bad in [{"Origin": None}, {"Origin": "https://evil.test"},
                    {"Host": "evil.test"}, {"Sec-Fetch-Site": "cross-site"},
                    {"Origin": REMOTE}, {"Host": "pool.example.test"}]:
            with self.subTest(bad=bad):
                self.assertEqual(self.request(headers={**headers, **bad})[0], 403)
        self.assertEqual(self.request(headers={**headers, "Origin": REMOTE,
                                                "Host": "pool.example.test"})[0], 200)

    def test_logout_and_expiry(self):
        headers = self.login("9876")
        self.assertEqual(self.request("/api/logout", {}, headers=headers)[0], 200)
        self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[0], 401)
        headers = self.login("9876")
        with patch.object(server.time, "time", return_value=10**12):
            self.assertEqual(self.request("/api/permissions", headers=headers, method="GET")[0], 401)
        self.ha.assert_not_called()

    def test_restart_and_pin_rotation(self):
        headers = self.login("9876")
        sid = headers["Cookie"].split("=", 1)[1]
        restarted = server.DeviceSessions(self.sessions.path, "1234", "9876")
        self.assertEqual(restarted.role(sid), "admin")
        self.assertIsNone(server.DeviceSessions(self.sessions.path, "1234", "new-admin").role(sid))
        self.ha.assert_not_called()

    def test_allowlist_and_command_validation(self):
        headers = self.login("1234")
        bodies = [{"control": "switch.arbitrary", "operation": "on"},
                  {"control": [], "operation": "on"},
                  {"control": "jets", "operation": "temperature", "value": 80},
                  {"control": "spa", "operation": "toggle"}]
        bodies += [{"control": "spa", "operation": "temperature", "value": v}
                   for v in (True, "80", 69, 105, float("nan"), float("inf"))]
        for body in bodies:
            self.assertEqual(self.request(body=body, headers=headers)[0], 400)
        self.ha.assert_not_called()

    def test_state_reads_allowlisted_entities(self):
        headers = self.login("1234")
        self.assertEqual(self.request("/api/state", headers=headers, method="GET")[0], 200)
        self.assertEqual([call.args[0] for call in self.ha.call_args_list],
                         ["/api/states/" + entity for key, (entity, _) in server.CONTROLS.items() if key not in ("light", "pool_sanitation", "spa_sanitation")] +
                         ["/api/states/" + entity for entity in server.READ_ONLY])

    def test_sanitation_is_admin_only(self):
        family = self.login("1234")
        status, state, _ = self.request("/api/state", headers=family, method="GET")
        self.assertEqual(status, 200)
        for key in ("pool_sanitation", "spa_sanitation"):
            self.assertNotIn(key, state)
            for operation in ("on", "off"):
                self.ha.reset_mock()
                self.assertEqual(self.request(body={"control": key, "operation": operation}, headers=family)[0], 403)
                self.ha.assert_not_called()
        admin = self.login("9876")
        status, state, _ = self.request("/api/state", headers=admin, method="GET")
        self.assertEqual(status, 200)
        for key in ("pool_sanitation", "spa_sanitation"):
            self.assertIn(key, state)
            for operation in ("on", "off"):
                self.assertEqual(self.request(body={"control": key, "operation": operation}, headers=admin)[0], 200)
                self.ha.assert_called_with("/api/services/input_boolean/turn_" + operation,
                                           {"entity_id": server.CONTROLS[key][0]})

    def test_ha_unavailable_returns_503(self):
        headers = self.login("1234")
        self.ha.side_effect = RuntimeError("offline")
        self.assertEqual(self.request(headers=headers)[0], 503)
        self.assertEqual(self.request("/api/state", headers=headers, method="GET")[0], 503)

    def test_frontend_role_permissions_and_login(self):
        html = (ROOT / "web/index.html").read_text()
        script = (ROOT / "web/app.js").read_text()
        self.assertIn('id="pinForm"', html)
        self.assertIn('id="pinInput"', html)
        self.assertIn('api("login"', script)
        self.assertIn('key==="pool"&&!permissions.pool_control', script)
        for name in ("pool", "spa", "features", "controls"):
            self.assertIn(f'id="{name}"', html)

    def test_request_logs_hide_query_secrets(self):
        handler = object.__new__(server.Handler)
        handler.client_address = ("127.0.0.1", 1234)
        handler.command = "GET"
        handler.path = "/api/login?pin=never-log-me"
        with patch("builtins.print") as output:
            handler.log_message("%s", handler.path)
        self.assertNotIn("never-log-me", str(output.call_args))


if __name__ == "__main__":
    unittest.main()
