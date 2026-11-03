"""Read-only Spa ownership collision detector.

HA's state history does not identify the actor that initiated a native command.
This module therefore treats any unexpected state change as a possible manual
takeover and never silently reclaims it. It does not subscribe or issue writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Collision(str, Enum):
    NONE = "none"
    YIELD = "yield"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True)
class Witness:
    epoch: str
    source: str | None
    spa_active: bool | None
    target_f: float | None
    generation: int
    fresh: bool


@dataclass(frozen=True)
class ExpectedTransition:
    epoch: str
    source: str | None = None
    spa_active: bool | None = None
    # Target writes are never authorized for opportunistic sessions.


def classify_transition(
    before: Witness,
    after: Witness,
    expected: ExpectedTransition | None,
) -> Collision:
    """Yield on unexplained native changes, including target changes."""
    if not before.fresh or not after.fresh:
        return Collision.RECOVERY_REQUIRED
    if not before.epoch or before.epoch != after.epoch:
        return Collision.RECOVERY_REQUIRED
    if after.generation <= before.generation:
        return Collision.RECOVERY_REQUIRED
    if before.target_f != after.target_f:
        return Collision.YIELD
    if before.source == after.source and before.spa_active == after.spa_active:
        return Collision.NONE
    if expected is None or expected.epoch != after.epoch:
        return Collision.YIELD
    if before.source != after.source and (expected.source is None or after.source != expected.source):
        return Collision.YIELD
    if before.spa_active != after.spa_active and (expected.spa_active is None or after.spa_active != expected.spa_active):
        return Collision.YIELD
    return Collision.NONE
