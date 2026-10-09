"""Family-only Pool & Spa web interface. Home Assistant remains the controller."""
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http import HTTPStatus
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
HA = os.environ.get("HA_URL", "http://supervisor/core").rstrip("/")
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
PORT = int(os.environ.get("PORT", "8101"))
PIN = ""
try:
    PIN = str(json.loads(Path("/data/options.json").read_text()).get("family_pin", ""))
except (OSError, ValueError, TypeError):
    PIN = os.environ.get("FAMILY_PIN", "")
SESSIONS = {}
CONTROLS = {
    "pool": ("climate.pool_thermostat", "climate"),
    "spa": ("climate.hot_tub_thermostat", "climate"),
    "jets": ("switch.jets_bubbles", "switch"),
    "spillway": ("switch.spillway", "switch"),
    "slide": ("switch.water_slide", "switch"),
}
READ_ONLY = ["sensor.pool_temperature", "sensor.spa_temperature",
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

    def authorized(self):
        cookie = self.headers.get("Cookie", "")
        token = next((v.strip() for p in cookie.split(";") if (v := p.strip()).startswith("session=")), "")
        sid = token.removeprefix("session=")
        expiry = SESSIONS.get(sid, 0)
        return bool(PIN and expiry > time.monotonic())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"ok": True, "configured": bool(PIN and TOKEN)})
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
            supplied = str(body.get("pin", ""))
            if not PIN or not hmac.compare_digest(supplied, PIN):
                return self.send_json({"error": "Incorrect PIN"}, 401)
            sid = secrets.token_urlsafe(32)
            SESSIONS[sid] = time.monotonic() + 86400
            return self.send_json({"ok": True}, cookie=f"session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400")
        if not self.authorized():
            return self.send_json({"error": "Sign in required"}, 401)
        if path != "/api/control":
            return self.send_json({"error": "Not found"}, 404)
        key, operation = body.get("control"), body.get("operation")
        if key not in CONTROLS:
            return self.send_json({"error": "Unknown control"}, 400)
        entity, domain = CONTROLS[key]
        if operation in ("on", "off"):
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
