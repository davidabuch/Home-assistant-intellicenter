"""Read-only RPM demand explanation, never a motor or configuration writer.

Pentair selects the highest simultaneous RPM assignment (GPM and freeze need
separate native evidence). An incomplete circuit inventory cannot prove a sole
Solar demand. Body/source heating evidence is reported separately from X0052.
"""
import math


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def explain(programs, *, fresh, solar_delivery, actual_rpm, settled,
            freeze_off, automatic_mode, desired_solar):
    """programs contains every PMP01 assignment, including unknown extras."""
    rows = [dict(row) for row in programs]
    active = [r for r in rows if r.get('active') is True]
    unknown = [r['id'] for r in rows if type(r.get('active')) is not bool
        or r.get('mode') != 'RPM' or finite(r.get('rpm')) is None]
    rpms = [finite(r.get('rpm')) for r in active if r.get('mode') == 'RPM']
    known_max = max((v for v in rpms if v is not None), default=None)
    effective = known_max if rows and not unknown else None
    solar = [r for r in rows if r.get('circuit_id') == 'X0052']
    actual = finite(actual_rpm)
    result = dict(programs=rows, unknown_programs=unknown,
        solar_delivery=solar_delivery, actual_rpm=actual,
        known_active_max_rpm=known_max, effective_rpm=effective,
        approved_solar_rpm=desired_solar, runtime_write=False)
    if not fresh:
        result.update(status='STALE', effective_rpm=None, known_active_max_rpm=None)
    elif not freeze_off or not automatic_mode:
        result['status'] = 'SAFETY_PREEMPTED'
    elif solar_delivery is not True:
        result['status'] = 'NO_CONFIRMED_SOLAR_DELIVERY'
    elif len(solar) != 1 or solar[0].get('active') is False:
        # Native heating delivery and actual motor RPM can agree with the
        # commissioned Solar preset even when X0052 is not reported active.
        # Record that independent evidence, but NEVER infer the winning pump
        # program or claim Solar-circuit RPM verification from an RPM match.
        result['solar_runtime_rpm_matches'] = (
            actual is not None and abs(actual - desired_solar) <= 50)
        result['solar_circuit_active'] = (
            solar[0].get('active') if len(solar) == 1 else None)
        result['effective_rpm'] = None
        result['status'] = ('SOLAR_DELIVERY_RPM_MATCH_CIRCUIT_UNCONFIRMED'
            if result['solar_runtime_rpm_matches']
            else 'SOLAR_CIRCUIT_UNCONFIRMED')
    elif not settled:
        result['status'] = 'SETTLING'
    elif effective is None or actual is None or solar[0].get('active') is not True:
        result['status'] = 'INCOMPLETE_NATIVE_DEMAND'
    elif abs(actual - effective) > 50:
        result['status'] = 'RUNTIME_MISMATCH_REVIEW_REQUIRED'
    elif effective > desired_solar:
        result['status'] = 'HIGHER_PROGRAM_DEMAND'
    elif abs(effective - desired_solar) > 50:
        result['status'] = 'SOLAR_CONFIGURATION_MISMATCH'
    else:
        result['status'] = 'SOLAR_RPM_VERIFIED'
    return result
