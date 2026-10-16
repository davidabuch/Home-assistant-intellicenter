"""Family-only Pool & Spa web interface. Home Assistant remains the controller."""
import hmac
import ipaddress
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie, CookieError

from device_sessions import DeviceSessions
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    OPTIONS = json.loads(Path("/data/options.json").read_text())
    if not isinstance(OPTIONS, dict):
        OPTIONS = {}
except (OSError, ValueError):
    OPTIONS = {}


def setting(name):
    value = os.environ.get(name, OPTIONS.get(name.lower(), ""))
    return value if isinstance(value, str) else ""


def single_header(handler, name):
    values = handler.headers.get_all(name, [])
    return values[0] if len(values) == 1 else ""


PUBLIC_ORIGIN = setting("FAMILY_PUBLIC_ORIGIN").rstrip("/")
REMOTE_PUBLIC_ORIGIN = setting("FAMILY_REMOTE_PUBLIC_ORIGIN").rstrip("/")

ROOT = Path(__file__).resolve().parent
HA = os.environ.get("HA_URL", "http://supervisor/core").rstrip("/")
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
PORT = int(os.environ.get("PORT", "8101"))
FAMILY_PIN = setting("FAMILY_PIN")
ADMIN_PIN = setting("ADMIN_PIN")
SESSION_FILE = Path(os.environ.get("SESSION_FILE", "/data/role_sessions.json"))
SESSIONS = DeviceSessions(SESSION_FILE, FAMILY_PIN, ADMIN_PIN)
LOGIN_ATTEMPTS = {}

CONTROLS = {
    "pool": ("climate.pool_thermostat", "climate"),
    "spa": ("climate.hot_tub_thermostat", "climate"),
    "jets": ("switch.jets_bubbles", "switch"),
    "spillway": ("switch.spillway", "switch"),
    "slide": ("switch.water_slide", "switch"),
    "light": ("light.pool_light", "light"),
    "pool_sanitation": ("input_boolean.pool_sanitation_session", "input_boolean"),
    "spa_sanitation": ("input_boolean.spa_sanitation_session", "input_boolean"),
}
READ_ONLY = ["binary_sensor.solar_heating_active", "binary_sensor.gas_heater_active", "sensor.pool_temperature", "sensor.spa_temperature",
             "binary_sensor.1_powerwall_grid_status", "input_boolean.grid_outage_active"]
MAX_BODY = 1024

def ha_request(path, payload=None):
    if not TOKEN:
        raise RuntimeError("Home Assistant API token unavailable")
    headers = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(HA + path, data=data, headers=headers,
                                     method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)

def snapshot():
    result = {}
    for key, (entity, _) in CONTROLS.items():
        if key in ("light", "pool_sanitation", "spa_sanitation"):
            continue  # Light state and effect choices are administrator-only.
        result[key] = ha_request("/api/states/" + entity)
    for entity in READ_ONLY:
        try:
            result[entity] = ha_request("/api/states/" + entity)
        except (urllib.error.HTTPError, urllib.error.URLError):
            result[entity] = {"state": "unavailable"}
    return result

class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, code=200, cookie=None):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def session_id(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie["session"].value if "session" in cookie else None
        except CookieError:
            return None

    def authorized(self):
        return SESSIONS.role(self.session_id()) in ("family", "admin")

    def admin_authorized(self):
        return SESSIONS.role(self.session_id()) == "admin"

    def valid_origin(self):
        origin = single_header(self, "Origin")
        host = single_header(self, "Host")
        if not host or not origin or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        # Never trust a client-supplied Host header to authorize cross-site writes.
        allowed = {value for value in (PUBLIC_ORIGIN, REMOTE_PUBLIC_ORIGIN)
                   if value.startswith("https://")}
        return origin in allowed and origin == f"https://{host}"

    def admin_snapshot(self):
        result = snapshot()
        if self.admin_authorized():
            try:
                result["light"] = ha_request("/api/states/" + CONTROLS["light"][0])
            except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
                result["light"] = {"state": "unavailable", "attributes": {"effect_list": []}}
            for key in ("pool_sanitation", "spa_sanitation"):
                try:
                    result[key] = ha_request("/api/states/" + CONTROLS[key][0])
                except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
                    result[key] = {"state": "unavailable"}
        return result

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"ok": True, "configured": bool(TOKEN and len(FAMILY_PIN) >= 4)})
        if path == "/api/permissions":
            if not self.authorized():
                return self.send_json({"error": "Sign in required"}, 401)
            return self.send_json({"pool_control": self.admin_authorized(), "light_control": self.admin_authorized()})
        if path == "/api/state":
            if not self.authorized():
                return self.send_json({"error": "Sign in required"}, 401)
            try:
                return self.send_json(self.admin_snapshot())
            except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                return self.send_json({"error": "Home Assistant unavailable"}, 503)
        assets = {"/": ("web/index.html", "text/html"), "/app.js": ("web/app.js", "text/javascript"),
                  "/style.css": ("web/style.css", "text/css"), "/backyard-scene.svg": ("web/backyard-scene.svg", "image/svg+xml"), "/manifest.webmanifest": ("web/manifest.webmanifest", "application/manifest+json"), "/sw.js": ("web/sw.js", "text/javascript")}
        assets.update({f"/icons/approved-v2/icon-{size}.png":
                       (f"web/icons/approved-v2/icon-{size}.png", "image/png")
                       for size in (16, 32, 180, 192, 512)})
        assets["/favicon.ico"] = ("web/icons/approved-v2/favicon.ico", "image/x-icon")
        for alias in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
            assets[alias] = ("web/icons/approved-v2/icon-180.png", "image/png")
        if path not in assets:
            return self.send_json({"error": "Not found"}, 404)
        filename, content_type = assets[path]
        content = (ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.valid_origin():
            return self.send_json({"error": "Invalid origin"}, 403)
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return self.send_json({"error": "JSON required"}, 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY:
                return self.send_json({"error": "Invalid request"}, 400)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                return self.send_json({"error": "Invalid request"}, 400)
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"error": "Invalid JSON"}, 400)
        if path == "/api/login":
            supplied = body.get("pin", "")
            client = self.client_address[0]
            now = time.monotonic()
            attempts = [t for t in LOGIN_ATTEMPTS.get(client, []) if now - t < 300]
            if len(attempts) >= 5:
                return self.send_json({"error": "Too many attempts; try again later"}, 429)
            result = SESSIONS.login(supplied)
            if result is None:
                attempts.append(now)
                LOGIN_ATTEMPTS[client] = attempts
                return self.send_json({"error": "Incorrect PIN"}, 401)
            LOGIN_ATTEMPTS.pop(client, None)
            sid, role = result
            return self.send_json({"ok": True, "role": role}, cookie=(
                f"session={sid}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age={180 * 86400}"))
        if path == "/api/logout":
            if not self.authorized():
                return self.send_json({"error": "Sign in required"}, 401)
            SESSIONS.logout(self.session_id())
            return self.send_json({"ok": True}, cookie="session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0")
        if not self.authorized():
            return self.send_json({"error": "Sign in required"}, 401)
        if path != "/api/control":
            return self.send_json({"error": "Not found"}, 404)
        key, operation = body.get("control"), body.get("operation")
        if not isinstance(key, str):
            return self.send_json({"error": "Unknown control"}, 400)
        if key not in CONTROLS:
            return self.send_json({"error": "Unknown control"}, 400)
        if key in ("pool", "light", "pool_sanitation", "spa_sanitation"):
            if not self.admin_authorized():
                return self.send_json({"error": "Administrator authorization required"}, 403)
        entity, domain = CONTROLS[key]
        if operation in ("on", "off"):
            if domain == "climate":
                service = "set_hvac_mode"
                payload = {"entity_id": entity, "hvac_mode": "heat" if operation == "on" else "off"}
            else:
                service = "turn_on" if operation == "on" else "turn_off"
                payload = {"entity_id": entity}
        elif operation == "effect" and key == "light":
            value = body.get("value")
            if not isinstance(value, str):
                return self.send_json({"error": "Invalid light effect"}, 400)
            try:
                current = ha_request("/api/states/" + entity)
            except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
                return self.send_json({"error": "Pool light unavailable"}, 503)
            if value not in current.get("attributes", {}).get("effect_list", []):
                return self.send_json({"error": "Unsupported light effect"}, 400)
            service, payload = "turn_on", {"entity_id": entity, "effect": value}
        elif operation == "temperature" and domain == "climate":
            value = body.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 70 <= value <= 104:
                return self.send_json({"error": "Temperature out of range"}, 400)
            service, payload = "set_temperature", {"entity_id": entity, "temperature": value}
        else:
            return self.send_json({"error": "Unsupported operation"}, 400)
        try:
            ha_request(f"/api/services/{domain}/{service}", payload)
            return self.send_json({"accepted": True, "pending_verification": True})
        except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
            return self.send_json({"error": "Command rejected or Home Assistant unavailable"}, 503)

    def log_message(self, fmt, *args):
        # Never log query strings or body data, including legacy ticket URLs.
        print("%s %s %s" % (self.address_string(), getattr(self, "command", ""),
                              urlparse(getattr(self, "path", "")).path), flush=True)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
