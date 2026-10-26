"""Conservative read-only Home Assistant gate inspection for Spa Solar.

This is a *shadow* evidence collector, not an authority oracle. Pool demand,
filtration due, manual intent, AUX9 release and competing-writer provenance
are not safely derivable from these helper states alone; those remain blocked.
"""
from __future__ import annotations

from dataclasses import dataclass

from .opportunistic_spa_native_adapter import HASafety

REQUIRED_OFF = (
    "input_boolean.grid_outage_active",
    "input_boolean.pool_sanitation_session",
    "input_boolean.spa_sanitation_session",
    "input_boolean.pool_simple_manual_circulation",
    "switch.pool_cleaning",
    "binary_sensor.pool_cleaning_active",
    "binary_sensor.rpm_guardian_blocks_normal_control",
    "binary_sensor.freeze_protection_active",
    "switch.water_slide",
    "switch.spillway",
    "switch.jets_bubbles",
)
REQUIRED_ON = ("input_boolean.pool_automatic_ownership",)
REQUIRED_KNOWN = (
    "counter.pool_simple_filtration_minutes",
    "sensor.pool_daily_filtration_target",
    "sensor.pool_temperature",
    "sensor.pool_target_temperature",
    "sensor.system_mode",
)


@dataclass(frozen=True)
class GateEvidence:
    safety: HASafety
    blockers: tuple[str, ...]


def inspect_ha_gates(states) -> GateEvidence:
    """Accept hass.states or an object with .get(entity_id). No writes."""
    blockers: list[str] = []
    for entity in REQUIRED_OFF:
        state = states.get(entity)
        if state is None or getattr(state, "state", None) != "off":
            blockers.append(entity + ":not_confirmed_off")
    for entity in REQUIRED_ON:
        state = states.get(entity)
        if state is None or getattr(state, "state", None) != "on":
            blockers.append(entity + ":not_confirmed_on")
    for entity in REQUIRED_KNOWN:
        state = states.get(entity)
        if state is None or getattr(state, "state", None) in (None, "", "unknown", "unavailable"):
            blockers.append(entity + ":unknown")
    # This observer deliberately does not infer actual service mode from an
    # arbitrary non-empty string; native commissioning must validate it.
    blockers.extend((
        "pool_demand:unproven",
        "filtration_due:unproven",
        "manual_spa_authority:unproven",
        "aux9_release_delay:unproven",
        "competing_writer_provenance:unproven",
        "ownership_receipt:unproven",
    ))
    return GateEvidence(
        safety=HASafety(
            enabled=False,
            recovery_required=True,
            manual_lockout=True,
            pool_demand=True,
            filtration_due=True,
            automatic_ownership=False,
            higher_priority_active=True,
            owned_receipt_verified=False,
            manual_override_seen=False,
        ),
        blockers=tuple(blockers),
    )
