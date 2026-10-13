"""Role-scoped, revocable, persistent device sessions for Pool & Spa Family."""
import hmac
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path


class DeviceSessions:
    def __init__(self, path, family_pin, admin_pin, ttl_days=180):
        self.path = Path(path)
        self.family_pin = family_pin if isinstance(family_pin, str) else ""
        self.admin_pin = admin_pin if isinstance(admin_pin, str) else ""
        self.ttl = ttl_days * 86400
        self.lock = threading.RLock()
        self.sessions = {}
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return
            now = time.time()
            for sid, entry in data.items():
                if (isinstance(sid, str) and isinstance(entry, dict)
                    and entry.get("role") in ("family", "admin")
                    and isinstance(entry.get("pin_digest"), str)
                    and type(entry.get("expires")) in (int, float)
                    and entry["expires"] > now):
                    self.sessions[sid] = entry
        except (OSError, ValueError, TypeError):
            pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with temp.open("w") as stream:
                json.dump(self.sessions, stream)
            os.chmod(temp, 0o600)
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)

    def _digest(self, role):
        pin = self.admin_pin if role == "admin" else self.family_pin
        return hashlib.sha256((role + ":" + pin).encode()).hexdigest()

    def login(self, supplied):
        if not isinstance(supplied, str):
            return None
        # An absent/identical administrator PIN can never grant elevated rights.
        admin_valid = (len(self.admin_pin) >= 6 and self.admin_pin != self.family_pin
                       and hmac.compare_digest(supplied, self.admin_pin))
        family_valid = len(self.family_pin) >= 4 and hmac.compare_digest(supplied, self.family_pin)
        role = "admin" if admin_valid else "family" if family_valid else None
        if role is None:
            return None
        with self.lock:
            sid = secrets.token_urlsafe(32)
            self.sessions[sid] = {"role": role, "expires": time.time() + self.ttl, "pin_digest": self._digest(role)}
            self._save()
            return sid, role

    def role(self, sid):
        if not isinstance(sid, str):
            return None
        with self.lock:
            entry = self.sessions.get(sid)
            if not entry:
                return None
            if entry["expires"] <= time.time():
                self.sessions.pop(sid, None)
                self._save()
                return None
            # Revoking or changing a PIN invalidates its role's old sessions.
            if entry["role"] == "admin" and (len(self.admin_pin) < 6 or self.admin_pin == self.family_pin):
                return None
            if not hmac.compare_digest(entry["pin_digest"], self._digest(entry["role"])):
                self.sessions.pop(sid, None)
                self._save()
                return None
            return entry["role"]

    def logout(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)
            self._save()

    def rotate(self, role, new_pin):
        if role not in ("family", "admin") or not isinstance(new_pin, str):
            raise ValueError("Invalid role or PIN")
        if len(new_pin) < (6 if role == "admin" else 4):
            raise ValueError("PIN too short")
        other = self.family_pin if role == "admin" else self.admin_pin
        if new_pin == other:
            raise ValueError("PINs must differ")
        with self.lock:
            if role == "admin":
                self.admin_pin = new_pin
            else:
                self.family_pin = new_pin
            self.sessions = {sid: entry for sid, entry in self.sessions.items()
                             if entry["role"] != role}
            self._save()
