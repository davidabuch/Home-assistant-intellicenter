"""Pure source-arbitration decision for opportunistic Spa sessions.

This is not a command writer. Caller must prove a durable, fresh ownership
receipt and enforce the decision at *every* source-write path.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceDecision(str, Enum):
    DEFER = "defer"
    SOLAR_ONLY = "solar_only"
    NORMAL_PREFERENCE = "normal_preference"


@dataclass(frozen=True)
class SourceContext:
    spa_session_claimed: bool = False
    ownership_receipt_verified: bool = False
    telemetry_fresh: bool = False
    manual_override_seen: bool = False
    recovery_required: bool = True


def arbitrate_spa_source(context: SourceContext) -> SourceDecision:
    """Never return normal Gas/Eco authority when an unverified claim exists."""
    if not context.spa_session_claimed:
        return SourceDecision.NORMAL_PREFERENCE
    if context.manual_override_seen or context.recovery_required:
        return SourceDecision.DEFER
    if not context.ownership_receipt_verified or not context.telemetry_fresh:
        return SourceDecision.DEFER
    return SourceDecision.SOLAR_ONLY
