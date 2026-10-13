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

import jwt
try:
    from admin_handoff import AdminHandoff, HandoffError
except ModuleNotFoundError:
    from standalone.admin_handoff import AdminHandoff, HandoffError

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


# Every access assertion requires both an exact proxy peer and a shared secret.
# No private-subnet or forwarded-address heuristic establishes local trust.
TRUSTED_PROXIES = frozenset((value.strip() for value in setting("FAMILY_TRUSTED_PROXIES").split(",") if value.strip()))
PROXY_SECRET = setting("FAMILY_PROXY_SECRET")
PUBLIC_ORIGIN = setting("FAMILY_PUBLIC_ORIGIN").rstrip("/")
CF_ISSUER = setting("CF_ACCESS_ISSUER").rstrip("/")
CF_AUDIENCE = setting("CF_ACCESS_AUDIENCE")
CF_USERS = frozenset((value.strip() for value in setting("CF_ACCESS_USERS").split(",") if value.strip()))
CF_KEYS = (jwt.PyJWKClient(CF_ISSUER + "/cdn-cgi/access/certs", timeout=5)
           if CF_ISSUER.startswith("https://") and urlparse(CF_ISSUER).hostname
           and urlparse(CF_ISSUER).hostname.endswith(".cloudflareaccess.com")
           and urlparse(CF_ISSUER).path == "" else None)
try:
    ADMIN_HANDOFF = AdminHandoff(
        setting("FAMILY_ADMIN_HANDOFF_SECRET"),
        replay_file=os.environ.get("ADMIN_REPLAY_FILE", "/data/admin_used_tickets.json"))
except HandoffError:
    ADMIN_HANDOFF = None


def trusted_proxy(handler):
    try:
        peer = str(ipaddress.ip_address(handler.client_address[0]))
    except ValueError:
        return False
    supplied = single_header(handler, "X-Family-Proxy-Secret")
    return bool(peer in TRUSTED_PROXIES and len(PROXY_SECRET) >= 32
                and hmac.compare_digest(supplied.encode(), PROXY_SECRET.encode()))


def remote_identity_verified(handler):
    if (not trusted_proxy(handler) or single_header(handler, "X-Family-Boundary") != "remote"
            or not CF_KEYS or not CF_AUDIENCE or not CF_USERS):
        return False
    token = single_header(handler, "Cf-Access-Jwt-Assertion")
    if not token or len(token) > 16384:
        return False
    try:
        key = CF_KEYS.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=CF_AUDIENCE,
                            issuer=CF_ISSUER, options={"require": ["exp", "iat", "sub", "email"]})
        return bool(isinstance(claims["sub"], str) and claims["sub"]
                    and claims["email"] in CF_USERS)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return False


def consume_admin_handoff(ticket):
    if ADMIN_HANDOFF is None:
        raise HandoffError("Administrator handoff unavailable")
    try:
        return ADMIN_HANDOFF.exchange(ticket)
    except (UnicodeError, AttributeError, TypeError) as exc:
        raise HandoffError("Malformed ticket") from exc


ROOT = Path(__file__).resolve().parent
HA = os.environ.get("HA_URL", "http://supervisor/core").rstrip("/")
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
PORT = int(os.environ.get("PORT", "8101"))
PIN = ""
try:
    PIN = str(json.loads(Path("/data/options.json").read_text()).get("family_pin", ""))
except (OSError, ValueError, TypeError):
    PIN = os.environ.get("FAMILY_PIN", "")
SESSION_FILE = Path(os.environ.get("SESSION_FILE", "/data/trusted_devices.json"))
SESSION_DAYS = 180

def load_sessions():
    try:
        saved = json.loads(SESSION_FILE.read_text())
        if isinstance(saved, dict):
            return {key: value for key, value in saved.items()
                    if isinstance(key, str) and isinstance(value, (int, float))
                    and value > time.time()}
    except (OSError, ValueError, TypeError):
        pass
    return {}

SESSIONS = load_sessions()
LOGIN_ATTEMPTS = {}

def save_sessions():
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SESSION_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(SESSIONS))
    os.chmod(temporary, 0o600)
    temporary.replace(SESSION_FILE)
CONTROLS = {
    "pool": ("climate.pool_thermostat", "climate"),
    "spa": ("climate.hot_tub_thermostat", "climate"),
    "jets": ("switch.jets_bubbles", "switch"),
    "spillway": ("switch.spillway", "switch"),
    "slide": ("switch.water_slide", "switch"),
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

    def family_authorized(self):
        return bool(trusted_proxy(self) and (
            single_header(self, "X-Family-Boundary") == "local"
            or remote_identity_verified(self)))

    def admin_authorized(self):
        if not self.family_authorized() or ADMIN_HANDOFF is None:
            return False
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            sid = cookies.get("family_admin")
            return ADMIN_HANDOFF.is_admin(sid.value if sid else "")
        except CookieError:
            return False

    def authorized(self):
        return self.family_authorized()

    def valid_origin(self):
        return bool(PUBLIC_ORIGIN.startswith("https://")
                    and single_header(self, "Origin") == PUBLIC_ORIGIN
                    and self.headers.get("Sec-Fetch-Site") != "cross-site")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"ok": True, "configured": bool(TOKEN and TRUSTED_PROXIES and len(PROXY_SECRET) >= 32 and PUBLIC_ORIGIN.startswith("https://"))})
        if path == "/api/permissions":
            if not self.authorized():
                return self.send_json({"error": "Sign in required"}, 401)
            return self.send_json({"pool_control": self.admin_authorized()})
        if path == "/api/state":
            if not self.authorized():
                return self.send_json({"error": "Sign in required"}, 401)
            try:
                return self.send_json(snapshot())
            except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                return self.send_json({"error": "Home Assistant unavailable"}, 503)
        assets = {"/": ("web/index.html", "text/html"), "/app.js": ("web/app.js", "text/javascript"),
                  "/style.css": ("web/style.css", "text/css"), "/manifest.webmanifest": ("web/manifest.webmanifest", "application/manifest+json"), "/icon.svg": ("web/icon.svg", "image/svg+xml"), "/sw.js": ("web/sw.js", "text/javascript")}
        if path not in assets:
            return self.send_json({"error": "Not found"}, 404)
        filename, content_type = assets[path]
        content = (ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.family_authorized():
            return self.send_json({"error": "Sign in required"}, 401)
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
        if path == "/api/admin/handoff":
            try:
                sid = consume_admin_handoff(body.get("ticket"))
            except HandoffError:
                return self.send_json({"error": "Invalid administrator handoff"}, 403)
            return self.send_json({"ok": True}, cookie=(
                f"family_admin={sid}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=900"))
        if path == "/api/login":
            supplied = str(body.get("pin", ""))
            client = self.client_address[0]
            now = time.monotonic()
            attempts = [t for t in LOGIN_ATTEMPTS.get(client, []) if now - t < 300]
            if len(attempts) >= 5:
                return self.send_json({"error": "Too many attempts; try again later"}, 429)
            if len(PIN) < 4 or not hmac.compare_digest(supplied.encode(), PIN.encode()):
                attempts.append(now)
                LOGIN_ATTEMPTS[client] = attempts
                return self.send_json({"error": "Incorrect PIN"}, 401)
            LOGIN_ATTEMPTS.pop(client, None)
            sid = secrets.token_urlsafe(32)
            SESSIONS[sid] = time.time() + SESSION_DAYS * 86400
            save_sessions()
            return self.send_json({"ok": True}, cookie=f"session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_DAYS * 86400}" + "; Secure")
        if not self.authorized():
            return self.send_json({"error": "Sign in required"}, 401)
        if path != "/api/control":
            return self.send_json({"error": "Not found"}, 404)
        key, operation = body.get("control"), body.get("operation")
        if not isinstance(key, str):
            return self.send_json({"error": "Unknown control"}, 400)
        if key not in CONTROLS:
            return self.send_json({"error": "Unknown control"}, 400)
        if key == "pool":
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
        print("%s %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
