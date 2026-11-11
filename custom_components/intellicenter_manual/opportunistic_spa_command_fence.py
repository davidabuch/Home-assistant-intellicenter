"""Pure, no-hardware Spa command serialization and epoch fencing.

This serializes *one coordinator's* intents; it cannot serialize external
Pentair/PWA writers or existing HA automations. Never treat this as authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .opportunistic_spa_provenance import (
    CommandKind, Pending, Readback, ReceiptStatus, verify_readback,
)


class Gate(str, Enum):
    DENIED = "denied"
    RESERVED = "reserved"
    BUSY = "busy"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True)
class Reservation:
    epoch: str
    kind: CommandKind
    generation: int
    issued_at_s: float


class SpaCommandFence:
    """In-memory fail-closed single-flight state machine, no I/O methods."""

    def __init__(self) -> None:
        self._epoch = ""
        self._pending: Reservation | None = None
        self._recovery_required = True

    @property
    def recovery_required(self) -> bool:
        return self._recovery_required

    @property
    def pending(self) -> Reservation | None:
        return self._pending

    def start_epoch(self, epoch: str, *, externally_authorized: bool = False) -> Gate:
        # An HA restart does not prove ownership or authorize any command.
        self._pending = None
        self._epoch = epoch if epoch else ""
        self._recovery_required = True
        return Gate.RECOVERY_REQUIRED

    def reserve(
        self,
        kind: CommandKind,
        *,
        epoch: str,
        observed_generation: int,
        now_s: float,
        all_external_writers_excluded: bool = False,
        fresh_priority_gates: bool = False,
        native_fresh: bool = False,
    ) -> Gate:
        if self._recovery_required or not self._epoch or epoch != self._epoch:
            return Gate.RECOVERY_REQUIRED
        if self._pending is not None:
            return Gate.BUSY
        if (type(observed_generation) is not int or observed_generation < 0
                or type(now_s) not in (int, float) or not math.isfinite(now_s)):
            return Gate.DENIED
        if not (all_external_writers_excluded and fresh_priority_gates and native_fresh):
            return Gate.DENIED
        self._pending = Reservation(epoch, kind, observed_generation, now_s)
        return Gate.RESERVED

    def confirm(self, readback: Readback, *, epoch: str) -> ReceiptStatus:
        if self._pending is None:
            return ReceiptStatus.UNPROVEN
        pending = self._pending
        self._pending = None
        status = verify_readback(
            Pending(pending.epoch, pending.kind, pending.issued_at_s, pending.generation),
            readback, current_epoch=epoch,
        )
        if status != ReceiptStatus.VERIFIED:
            self._recovery_required = True
        return status

    def invalidate(self) -> None:
        self._pending = None
        self._recovery_required = True
