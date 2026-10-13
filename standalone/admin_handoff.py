"""Standalone administrator ticket verification for Pool & Spa Family.

This module is deliberately independent of the running controller and never
issues Home Assistant service calls. Integration into server.py is pending.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time


class HandoffError(ValueError):
    pass


class AdminHandoff:
    def __init__(self, shared_secret, clock=time.time):
        if not isinstance(shared_secret, str) or len(shared_secret) < 32:
            raise HandoffError("Administrator handoff secret must be configured")
        self.secret = shared_secret.encode("utf-8")
        self.clock = clock
        self.used = {}
        self.sessions = {}

    def exchange(self, ticket):
        if not isinstance(ticket, str) or len(ticket) > 2048 or ticket.count(".") != 1:
            raise HandoffError("Malformed ticket")
        payload, signature = ticket.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(
            self.secret, payload.encode("ascii"), hashlib.sha256
        ).digest()).rstrip(b"=").decode("ascii")
        if not hmac.compare_digest(signature, expected):
            raise HandoffError("Invalid signature")
        try:
            claims = json.loads(base64.urlsafe_b64decode(
                payload + "=" * (-len(payload) % 4)))
            now = self.clock()
            nonce = claims["nonce"]
            expiry = claims["exp"]
            if (claims.get("aud") != "pool-spa-family"
                    or claims.get("role") != "admin"
                    or not isinstance(claims.get("sub"), str)
                    or not claims["sub"]
                    or not isinstance(nonce, str) or len(nonce) != 48
                    or not isinstance(expiry, int)
                    or not now < expiry <= now + 60):
                raise HandoffError("Invalid claims")
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise HandoffError("Invalid claims") from exc
        for used_nonce, deadline in list(self.used.items()):
            if deadline <= now:
                del self.used[used_nonce]
        if nonce in self.used:
            raise HandoffError("Ticket already used")
        self.used[nonce] = expiry
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = now + 900
        return sid

    def is_admin(self, sid):
        return bool(sid and self.sessions.get(sid, 0) > self.clock())
