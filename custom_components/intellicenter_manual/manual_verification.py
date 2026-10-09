"""Offline-only manual-command verification contract.

No physical delivery, timers, retries, or authority acquisition. This is an
independent evidence predicate for a future explicitly commissioned writer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Literal

from .observation import ReadObservation


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PENDING = "pending"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True)
class ExpectedChange:
    kind: Literal["body_active", "circuit_active", "target", "pump_rpm", "heater_id"]
    native_id: str
    value: bool | float | str
    accepted_at: datetime


def verify_change(
    expected: ExpectedChange,
    observation: ReadObservation,
    *,
    rpm_tolerance: float = 25.0,
) -> VerificationStatus:
    """Verify only a fresh, post-acceptance, uniquely identified observation.

    PENDING means a trusted observation disagrees, not permission to retry.
    UNTRUSTED means no reliable verification claim can be made.
    """
    if (
        expected.accepted_at.tzinfo is None
        or not observation.connected
        or observation.observed_at.tzinfo is None
        or observation.observed_at <= expected.accepted_at
    ):
        return VerificationStatus.UNTRUSTED

    kind = expected.kind
    if kind in {"body_active", "target", "heater_id"}:
        if expected.native_id not in {"B1101", "B1202"}:
            return VerificationStatus.UNTRUSTED
        body = observation.body(expected.native_id)
        if body is None:
            return VerificationStatus.UNTRUSTED
        actual = (
            body.active if kind == "body_active"
            else body.target_temperature if kind == "target"
            else body.heat_source
        )
    elif kind == "circuit_active":
        if expected.native_id not in {"C0002", "C0003", "C0004", "FTR01"}:
            return VerificationStatus.UNTRUSTED
        circuit = observation.circuit(expected.native_id)
        if circuit is None:
            return VerificationStatus.UNTRUSTED
        actual = circuit.active
    elif kind == "pump_rpm":
        if expected.native_id != "PMP01":
            return VerificationStatus.UNTRUSTED
        actual = observation.measurement("pump_rpm")
    else:
        return VerificationStatus.UNTRUSTED

    if actual is None:
        return VerificationStatus.UNTRUSTED
    if kind in {"body_active", "circuit_active"}:
        if type(expected.value) is not bool or type(actual) is not bool:
            return VerificationStatus.UNTRUSTED
        matches = actual is expected.value
    elif kind in {"target", "pump_rpm"}:
        if (
            isinstance(expected.value, bool)
            or isinstance(actual, bool)
            or not isinstance(expected.value, (float, int))
            or not isinstance(actual, (float, int))
            or not isfinite(expected.value)
            or not isfinite(actual)
        ):
            return VerificationStatus.UNTRUSTED
        tolerance = rpm_tolerance if kind == "pump_rpm" else 0.0
        if not isfinite(tolerance) or tolerance < 0:
            return VerificationStatus.UNTRUSTED
        matches = abs(actual - expected.value) <= tolerance
    else:
        if expected.value not in {"00000", "H0001", "H0002"} or not isinstance(actual, str):
            return VerificationStatus.UNTRUSTED
        matches = actual == expected.value
    return VerificationStatus.VERIFIED if matches else VerificationStatus.PENDING
