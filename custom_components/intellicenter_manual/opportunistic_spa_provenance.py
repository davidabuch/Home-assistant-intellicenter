"""Fail-closed command provenance for a future Spa Solar HA adapter.

A native state transition is not evidence of who caused it. In particular, an
ON/OFF or source change seen after a service call may have been issued by the
PWA, Pentair panel, another automation, or a concurrent actor. This module
only records locally dispatched intent and verifies the expected readback.
It never establishes exclusive physical ownership by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandKind(str, Enum):
    SOURCE_SOLAR = "source_solar"
    SPA_ON = "spa_on"
    SPA_OFF = "spa_off"


@dataclass(frozen=True)
class Pending:
    epoch: str
    command: CommandKind
    issued_at_s: float
    observed_generation: int


@dataclass(frozen=True)
class Readback:
    observed_at_s: float
    generation: int
    source: str | None
    spa_active: bool | None
    native_fresh: bool
    competing_writer_seen: bool = False


class ReceiptStatus(str, Enum):
    VERIFIED = "verified"
    UNPROVEN = "unproven"
    EXPIRED = "expired"
    CONFLICT = "conflict"


def verify_readback(
    pending: Pending,
    readback: Readback,
    *,
    current_epoch: str,
    max_ack_delay_s: float = 15.0,
) -> ReceiptStatus:
    """Confirm matching readback; never infer unique writer from matching state."""
    if not pending.epoch or pending.epoch != current_epoch:
        return ReceiptStatus.CONFLICT
    if readback.competing_writer_seen:
        return ReceiptStatus.CONFLICT
    if not readback.native_fresh or readback.generation <= pending.observed_generation:
        return ReceiptStatus.UNPROVEN
    elapsed = readback.observed_at_s - pending.issued_at_s
    if elapsed < 0:
        return ReceiptStatus.CONFLICT
    if elapsed > max_ack_delay_s:
        return ReceiptStatus.EXPIRED
    expected = {
        CommandKind.SOURCE_SOLAR: readback.source == "Solar",
        CommandKind.SPA_ON: readback.spa_active is True,
        CommandKind.SPA_OFF: readback.spa_active is False,
    }[pending.command]
    return ReceiptStatus.VERIFIED if expected else ReceiptStatus.UNPROVEN
