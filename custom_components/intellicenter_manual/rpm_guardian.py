"""Request-driven persistent RPM policy and durable outage transaction.

No timers, sockets, HA imports or equipment ON/OFF decisions live here. HA
automations request reconciliation. IO callbacks use the existing native gate.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import math
from uuid import uuid4

PROGRAMS = {"pool": ("p0102", "C0006"), "spa": ("p0101", "C0001"),
            "sanitation": ("p0105", "FTR02"), "heater": ("p0103", "X0051"),
            "solar": ("p0104", "X0052"), "pool_cleaning": ("p0106", "FTR03")}
# Only named operator/schedule/session requests discover ordinary drift.
# Unknown/legacy requests fail closed to recovery servicing, never broad scans.
ROUTINE_REASONS = frozenset({"manual", "manual_button", "apply", "startup",
    "before_filtration", "accounting_rollover", "spa_session", "sanitation_request",
    "spa_requested", "sanitation_requested", "heater_requested", "solar_requested",
    "solar_delivery_started", "cleaning_released", "08:00", "23:59"})

DEFAULTS = {"pool": 2600, "spa": 2600, "sanitation": 3200,
            "heater": 3000, "solar": 2900, "pool_cleaning": 3000, "outage": 1500}
# Conservative change floors from the commissioned configuration, not a claim
# that these are manufacturer-certified minimum flows. Lowering a floor is a
# separate supervised equipment-flow decision, never inferred from motor RPM.
FLOORS = dict(DEFAULTS)
BLOCKING = {"APPLYING_OUTAGE_SPEED", "OUTAGE_ACTIVE", "RESTORING_NORMAL_SPEED",
            "REEVALUATING_DEMAND", "RECOVERY_REQUIRED", "DEGRADED"}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def speed(value, minimum=600, maximum=3450):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("RPM must be numeric")
    if not math.isfinite(value) or int(value) != value or int(value) % 10:
        raise ValueError("RPM must be a finite integer in steps of 10")
    if not minimum <= value <= maximum:
        raise ValueError(f"RPM must be {minimum}..{maximum}")
    return int(value)


def native_speed(value, minimum=600, maximum=3450):
    """Validate observed native RPM without imposing operator target increments."""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("Native RPM must be numeric")
    if not math.isfinite(value) or int(value) != value:
        raise ValueError("Native RPM must be a finite integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"Native RPM must be {minimum}..{maximum}")
    return int(value)


@dataclass(frozen=True)
class Conditions:
    """Fresh evidence, not inferred operator intent. None means unknown."""
    fresh: bool = False
    qualified: bool | None = None
    raw_outage: bool | None = None
    restored: bool = False
    protection: bool | None = None
    bypass: bool | None = None
    authority: bool = False
    freeze_off: bool = False
    automatic_mode: bool = False
    pool: bool | None = None
    spa_off: bool = False
    sanitation_off: bool = False
    heat_off: bool = False
    sources_off: bool = False
    accessories_off: bool = False
    settled: bool = False
    actual_rpm: float | None = None
    minimum: int = 600
    maximum: int = 3450
    cleaning_active: bool | None = None

    @property
    def protected(self):
        return self.qualified is True and self.protection is True and self.bypass is False

    @property
    def known(self):
        return (self.qualified is not None and self.raw_outage is not None
                and self.protection is not None and self.bypass is not None)

    @property
    def safe(self):
        return self.fresh and self.authority and self.freeze_off and self.automatic_mode


class RPMGuardian:
    """One serialized policy writer with a write-ahead, verified recovery record."""
    def __init__(self, read, write, conditions, save, *, notify=lambda: None):
        self.read, self.write, self.conditions, self.save = read, write, conditions, save
        self.notify = notify
        self.lock = asyncio.Lock()
        self._permit = None
        self._generation = 0
        self.loaded = False
        self.data = {
            "version": 1, "draft": dict(DEFAULTS), "applied": dict(DEFAULTS),
            "floors": dict(FLOORS), "enabled": False, "running_pool_approved": False,
            "settling_seconds": 180, "state": "NORMAL", "epoch": 0,
            "session": None, "intent": None, "restoration_pending": False,
            "last_observed": {}, "last_verified": {}, "results": {},
            "last_reconciliation": None, "last_success": None,
            "last_corrected_program": None, "corrected": 0, "failed_writes": 0,
            "failure": None, "runtime_status": "NOT_RUN",
            "last_failure": None,
            "runtime_wait_until": None,
            "routine_scan_pending": False, "pending_routine": {},
            "pool_cleaning_commissioned": False,
        }

    @property
    def blocks_normal(self):
        # Disarmed staging does not claim equipment authority. A durable dirty
        # transaction remains blocking even after pause/restart.
        return bool(self.data["restoration_pending"] or
                    (self.data["enabled"] and self.data["state"] in BLOCKING))

    async def persist(self):
        await self.save(deepcopy(self.data))
        self.notify()

    def invalidate_authority(self):
        """An authority/grid transition invalidates queued permits immediately.

        Called on the HA event loop, including an OFF/ON flap whose final state
        otherwise looks unchanged. The next write-ahead save persists the epoch.
        """
        self._generation += 1
        self.data['epoch'] += 1
        self.notify()

    async def load(self, stored):
        if stored is not None:
            try:
                if stored.get("version") != 1:
                    raise ValueError("Unrecognized recovery version")
                for field in ("draft", "applied", "floors"):
                    if set(stored[field]) != set(DEFAULTS):
                        # Add the newly commissioned Pool Cleaning program to
                        # legacy records without losing outage recovery state.
                        if set(stored[field]) != set(DEFAULTS) - {"pool_cleaning"}:
                            raise ValueError("Incomplete RPM policy")
                        stored[field]["pool_cleaning"] = DEFAULTS["pool_cleaning"]
                    for value in stored[field].values(): speed(value)
                if stored.get("intent") is not None:
                    intent = stored["intent"]
                    if intent.get("program") != "p0102" or type(intent.get("epoch")) is not int:
                        raise ValueError("Invalid recovery intent")
                if type(stored.get("restoration_pending")) is not bool:
                    raise ValueError("Invalid recovery marker")
                if (type(stored.get("enabled")) is not bool
                        or type(stored.get("running_pool_approved")) is not bool
                        or type(stored.get("epoch")) is not int or stored['epoch'] < 0
                        or type(stored.get("settling_seconds")) is not int
                        or not 180 <= stored['settling_seconds'] <= 900):
                    raise ValueError("Invalid commissioning or epoch metadata")
                pending = stored.get("pending_routine", {})
                if (not isinstance(pending, dict) or not set(pending) <= set(PROGRAMS)
                        or type(stored.get("routine_scan_pending", False)) is not bool):
                    raise ValueError("Invalid pending routine work")
                for key, value in pending.items():
                    speed(value)
                    if value != stored["applied"][key]:
                        raise ValueError("Pending routine target differs from applied policy")
                self.data.update(deepcopy(stored))
                self.data.setdefault("pool_cleaning_commissioned", False)
                if self.data["intent"] or self.data["restoration_pending"]:
                    self.data["restoration_pending"] = True
                    self.data["state"] = "RECOVERY_REQUIRED"
            except (ValueError, KeyError, TypeError) as exc:
                # Do not overwrite an unreadable record with clean defaults.
                self.data["state"] = "RECOVERY_REQUIRED"
                self.data["restoration_pending"] = True
                self.data["failure"] = f"Recovery record invalid: {exc}"
                self.loaded = False
                self.notify()
                return
        self.loaded = True
        self.notify()

    async def queue_startup_scan(self):
        """Durable startup request; heartbeat completes it after HA initialization."""
        async with self.lock:
            if self.loaded:
                self.data["routine_scan_pending"] = True
                await self.persist()

    async def edit(self, key, value):
        if not self.loaded: raise RuntimeError("Resolve invalid recovery record first")
        if key not in DEFAULTS:
            raise ValueError("Unknown policy setting")
        value = speed(value)
        async with self.lock:
            self.data["draft"][key] = value
            await self.persist()  # editing is never a native write

    async def apply(self):
        if not self.loaded: raise RuntimeError("Resolve invalid recovery record first")
        async with self.lock:
            sample = self.conditions()
            for key, value in self.data["draft"].items():
                speed(value, max(sample.minimum, self.data["floors"][key]), sample.maximum)
            self.data["applied"] = dict(self.data["draft"])
            # Explicit Apply is the commissioning boundary for the new preset.
            self.data["pool_cleaning_commissioned"] = True
            # Supersede old approved corrections atomically with the new policy.
            self.data["pending_routine"] = {}
            self.data["routine_scan_pending"] = True
            await self.persist()
        return await self.reconcile("apply")

    async def enable(self, enabled, *, running_pool_approved=False):
        async with self.lock:
            if not self.loaded:
                raise RuntimeError("Valid durable state is required")
            self.data["enabled"] = bool(enabled)
            self.data["running_pool_approved"] = bool(running_pool_approved)
            await self.persist()

    async def reset(self):
        async with self.lock:
            if (self.data["restoration_pending"] or self.data["intent"]
                    or self.data['session'] is not None or self.conditions().protected):
                raise RuntimeError("Verified restoration required before recovery reset")
            self.data["failure"] = None
            self.data["state"] = "NORMAL"
            await self.persist()

    def permitted(self, object_id, target, token):
        """Called again INSIDE the native dispatch lock, never cached authority."""
        permit = self._permit
        if token is not permit or permit is None or not self.loaded or not self.data["enabled"]:
            return False
        key, expected, epoch, generation, phase = permit
        sample = self.conditions()
        if (object_id != PROGRAMS[key][0] or target != expected
                or epoch != self.data["epoch"] or generation != self._generation
                or not sample.known or not sample.safe
                 or (phase == 'normal' and sample.cleaning_active is not False)):
            return False
        floor_key = "outage" if phase == "outage" else key
        try: speed(target, max(sample.minimum, self.data["floors"][floor_key]), sample.maximum)
        except ValueError: return False
        if phase == "outage":
            return (key == "pool" and sample.protected and sample.raw_outage is True
                    and target == self.data["applied"]["outage"] and self.outage_flow_safe(sample))
        if phase == "restore":
            return (key == "pool" and sample.restored and sample.qualified is False
                    and sample.raw_outage is False and target == self.data["applied"]["pool"]
                    and self.pool_change_safe(sample))
        return (self.data["pending_routine"].get(key) == target
                and not sample.protected
                and (not self.blocks_normal or (
                    self.data.get("reason") in {"manual", "manual_button"}
                    and self.data["state"] == "DEGRADED"
                    and self.data.get("failure") == "Native RPM readback differs from ICP-confirmed settings; routine writes held"
                    and not self.data["restoration_pending"]
                    and self.data["session"] is None
                    and self.data["intent"] is None))
                and sample.bypass is False
                and sample.raw_outage is False and sample.actual_rpm is not None
                and sample.actual_rpm < 500 and sample.pool is False
                and sample.spa_off and sample.sanitation_off and sample.heat_off
                and sample.accessories_off and target == self.data["applied"][key])

    def pool_change_safe(self, sample):
        if not (sample.spa_off and sample.sanitation_off and sample.heat_off
                and sample.accessories_off and sample.actual_rpm is not None):
            return False
        if sample.pool is False:
            return sample.actual_rpm < 500
        return (sample.pool is True and sample.sources_off
                and sample.actual_rpm >= 500
                and self.data["running_pool_approved"] and sample.settled)

    def outage_flow_safe(self, sample):
        return self.pool_change_safe(sample) and sample.pool is True

    async def _change(self, key, target, phase):
        object_id = PROGRAMS[key][0]
        sample = self.conditions()
        token = (key, target, self.data["epoch"], self._generation, phase)
        self._permit = token
        try:
            if not self.permitted(object_id, target, token):
                self.data["results"][key] = "DEFERRED: safety, settling, flow or authority"
                return False
            if phase in {"outage", "restore"}:
                # Save BEFORE dispatch. ACK loss/restart must retain recovery.
                self.data["restoration_pending"] = True
                self.data["intent"] = {"session": self.data["session"], "epoch": self.data["epoch"],
                    "program": object_id, "normal": self.data["applied"]["pool"],
                    "temporary": self.data["applied"]["outage"], "target": target,
                    "phase": phase, "attempted": True, "verified": False, "at": timestamp()}
                await self.persist()
            await self.write(object_id, target, token)
            # Transport has already required a NEW native observation. Recheck
            # configuration and context; no ACK or old sample can clear recovery.
            observed = self.read(key)
            if observed != target:
                raise RuntimeError("Native readback mismatch")
            if not self.permitted(object_id, target, token):
                raise RuntimeError("Policy changed during write; re-observation required")
            self.data["last_observed"][key] = observed
            self.data["last_verified"][key] = timestamp()
            self.data["last_corrected_program"] = key
            self.data["corrected"] += 1
            self.data["results"][key] = "VERIFIED"
            if self.data["intent"]:
                self.data["intent"]["verified"] = True
            if phase == 'outage':
                self.data['runtime_wait_until'] = (datetime.now(timezone.utc) +
                    timedelta(seconds=self.data['settling_seconds'])).isoformat()
            await self.persist()
            return True
        except Exception as exc:
            self.data["failed_writes"] += 1
            self.data["failure"] = str(exc)
            self.data["last_failure"] = {"reason": str(exc), "at": timestamp()}
            self.data["results"][key] = f"FAILED: {exc}"
            if self.data["restoration_pending"]:
                self.data["state"] = "RECOVERY_REQUIRED"
            await self.persist()
            return False
        finally:
            self._permit = None

    async def reconcile(self, reason="manual"):
        async with self.lock:
            if not self.loaded:
                return deepcopy(self.data)
            self._generation += 1
            self.data["last_reconciliation"] = timestamp()
            self.data["reason"] = reason
            self.data["request_class"] = "routine" if reason in ROUTINE_REASONS else "recovery"
            if reason in ROUTINE_REASONS:
                # Persist before reads: stale startup/failed observations must
                # not lose this event or silently broaden every later heartbeat.
                self.data["routine_scan_pending"] = True
                await self.persist()
            sample = self.conditions()
            try:
                self.data['results'] = {key: 'UNKNOWN' for key in PROGRAMS}
                if not sample.fresh:
                    raise RuntimeError("Fresh native observations required")
                # Identity validation is in read(), never skipped for a match.
                actual = {}
                active_programs = [key for key in PROGRAMS
                    if key != "pool_cleaning" or self.data["pool_cleaning_commissioned"]]
                for key in active_programs:
                    try: actual[key] = self.read(key)
                    except Exception as exc:
                        self.data['results'][key] = f'FAILED: {exc}'
                        raise RuntimeError(f'{key} native identity/readback unavailable: {exc}') from exc
                self.data["last_observed"] = actual
                desired = {key: self.data["applied"][key] for key in active_programs}
                # Background reconciliation remains fail-closed for unusual native
                # values. An explicit operator request may repair confirmed
                # configured-circuit drift, but only through the existing
                # fresh-identity, safety, serialized-write and readback gates.
                explicit_repair = reason in {"manual", "manual_button", "apply"}
                if (not explicit_repair and not sample.protected
                        and not self.data["restoration_pending"]
                        and self.data["session"] is None
                        and any(actual[k] != desired[k] and actual[k] % 10 != 0
                                for k in active_programs)):
                    self.data["results"] = {
                        k: ("MATCH" if actual[k] == desired[k]
                            else f"READBACK_DISCREPANCY: native={actual[k]} expected={desired[k]}")
                        for k in active_programs}
                    if not self.data["pool_cleaning_commissioned"]:
                        self.data["results"]["pool_cleaning"] = "NOT_COMMISSIONED"
                    self.data["pending_routine"] = {}
                    self.data["routine_scan_pending"] = True
                    self.data["state"] = "DEGRADED"
                    self.data["failure"] = "Native RPM readback differs from ICP-confirmed settings; routine writes held"
                    await self.persist()
                    return deepcopy(self.data)
                if sample.protected:
                    desired["pool"] = desired["outage"]
                self.data["results"] = {key: "MATCH" if actual[key] == desired[key]
                    else "PENDING" for key in active_programs}
                if not self.data["pool_cleaning_commissioned"]:
                    self.data["results"]["pool_cleaning"] = "NOT_COMMISSIONED"
                for key in active_programs:
                    if actual[key] == desired[key]:
                        self.data["last_verified"][key] = timestamp()
                # Native persistent state wins over a clean/missing journal.
                # A stranded outage preset must not be treated as harmless
                # running drift while normal heating/start authority is released.
                if (sample.qualified is False and sample.raw_outage is False
                        and actual["pool"] == self.data["applied"]["outage"]
                        and actual["pool"] != self.data["applied"]["pool"]
                        and not self.data["restoration_pending"]):
                    self.data["restoration_pending"] = True
                    self.data["session"] = self.data["session"] or str(uuid4())
                    self.data["intent"] = {
                        "session": self.data["session"], "epoch": self.data["epoch"],
                        "program": "p0102", "normal": self.data["applied"]["pool"],
                        "temporary": self.data["applied"]["outage"],
                        "target": self.data["applied"]["pool"], "observed": actual["pool"],
                        "phase": "discovered", "attempted": False, "verified": False,
                        "at": timestamp()}
                    self.data["state"] = "RECOVERY_REQUIRED"
                    self.data["failure"] = "Unjournaled outage-speed Pool preset; verified restoration required"
                    await self.persist()
                pending = self.data["pending_routine"]
                if self.data["routine_scan_pending"]:
                    for key in active_programs:
                        # A protected Pool target belongs to safety recovery,
                        # not an ordinary correction to normal during outage.
                        if key == "pool" and sample.protected:
                            continue
                        if actual[key] != self.data["applied"][key]:
                            pending[key] = self.data["applied"][key]
                    self.data["routine_scan_pending"] = False
                for key in list(pending):
                    if actual[key] == pending[key]:
                        del pending[key]  # uncertain ACK/external correction: read first
                for key in active_programs:
                    if (actual[key] != desired[key] and key not in pending
                            and not (key == "pool" and (sample.protected or self.blocks_normal))):
                        self.data["results"][key] = "DRIFT: awaiting routine event"
                # These obligations are durable BEFORE any normal dispatch.
                await self.persist()
                if not self.data["enabled"]:
                    self.data["failure"] = (
                        "Recovery pending; authorize guarded restoration before normal control"
                        if self.data["restoration_pending"] else "Commissioning write gate disabled")
                    await self.persist()
                    return deepcopy(self.data)
                if not sample.known:
                    raise RuntimeError("Grid/protection/bypass evidence unknown")
                if sample.protected:
                    if self.data["session"] is None:
                        self.data["session"] = str(uuid4())
                        self.data["epoch"] += 1
                    self.data["state"] = "APPLYING_OUTAGE_SPEED"
                    # Block normal operation throughout the protected session,
                    # even if no Pool write is needed because Pool is OFF.
                    await self.persist()
                    if sample.pool is False:
                        self.data["results"]["pool"] = "DEFERRED: Pool OFF; no outage-only start"
                        self.data["state"] = "OUTAGE_ACTIVE"
                    elif not self.outage_flow_safe(sample):
                        self.data["state"] = "DEGRADED"
                        self.data["failure"] = "Higher flow, priming, heating or running-write approval pending"
                    elif actual["pool"] != desired["pool"]:
                        if await self._change("pool", desired["pool"], "outage"):
                            self.data["state"] = "OUTAGE_ACTIVE"
                    else:
                        # Matching value is useful evidence but not provenance
                        # that this session wrote it. Preserve any dirty record.
                        self.data["state"] = "OUTAGE_ACTIVE"
                    self.observe_runtime(self.conditions())
                elif self.data["restoration_pending"] or self.data["session"] is not None:
                    self.data["state"] = "RESTORING_NORMAL_SPEED"
                    await self.persist()
                    if not sample.restored or sample.raw_outage is not False or sample.qualified is not False:
                        self.data["failure"] = "Waiting for qualified restoration; bypass does not clear recovery"
                    else:
                        restored = actual["pool"] == desired["pool"]
                        if not restored:
                            restored = await self._change("pool", desired["pool"], "restore")
                        if restored and self.conditions().restored and not self.conditions().protected:
                            self.data["state"] = "REEVALUATING_DEMAND"
                            self.data["last_verified"]["pool"] = timestamp()
                            await self.persist()
                            self.data["restoration_pending"] = False
                            self.data["intent"] = None
                            self.data["session"] = None
                            self.data["state"] = "NORMAL"
                            self.data["failure"] = None
                elif sample.raw_outage is True:
                    self.data["state"] = "OUTAGE_QUALIFYING"
                    # Absolutely no persistent writes before the detector's
                    # existing five-minute qualified latch.
                else:
                    # Preserve the blocking state until an explicit repair has
                    # verified every mismatched circuit. Never release the HA
                    # schedule during a partial multi-program correction.
                    repairing = (explicit_repair and self.data["state"] == "DEGRADED"
                                 and not self.data["restoration_pending"])
                    if not repairing:
                        self.data["state"] = "NORMAL"
                    for key in list(self.data["pending_routine"]):
                        if actual[key] != desired[key]:
                            if await self._change(key, desired[key], "normal"):
                                del self.data["pending_routine"][key]
                if (explicit_repair and self.data["state"] == "DEGRADED"
                        and not self.data["restoration_pending"]
                        and not self.data["pending_routine"]
                        and all(v in {"MATCH", "VERIFIED", "NOT_COMMISSIONED"} for v in self.data["results"].values())):
                    self.data["state"] = "NORMAL"
                    self.data["failure"] = None
                if all(v in {"MATCH", "VERIFIED"} for v in self.data["results"].values()):
                    self.data["last_success"] = timestamp()
                    if (self.data['state'] == 'NORMAL' or
                            (self.data['state'] == 'OUTAGE_ACTIVE' and
                             self.data['runtime_status'] in {'SETTLING', 'VERIFIED'})):
                        self.data['failure'] = None
                await self.persist()
            except Exception as exc:
                self.data["failure"] = str(exc)
                self.data["last_failure"] = {"reason": str(exc), "at": timestamp()}
                if self.data["restoration_pending"]:
                    self.data["state"] = "RECOVERY_REQUIRED"
                elif self.data['enabled']:
                    self.data['state'] = 'DEGRADED'
                await self.persist()
            return deepcopy(self.data)

    def observe_runtime(self, sample):
        """Runtime mismatch is diagnostic only: never a configuration rewrite."""
        deadline = self.data.get('runtime_wait_until')
        waiting = deadline is not None and datetime.now(timezone.utc) < datetime.fromisoformat(deadline)
        if waiting or not sample.settled:
            self.data["runtime_status"] = "SETTLING"
        elif not self.outage_flow_safe(sample):
            self.data["runtime_status"] = "CONFLICT: higher flow, unavailable data or safety"
        elif sample.actual_rpm == self.data["applied"]["outage"]:
            self.data["runtime_status"] = "VERIFIED"
        else:
            self.data["runtime_status"] = "MISMATCH: operator review; configuration not rewritten"

    def ordinary_command_allowed(self, method, args):
        if not self.blocks_normal:
            return True
        sample = self.conditions()
        if sample.bypass is True or sample.protection is False:
            return True  # bypass releases equipment, not persistent recovery intent
        if method == 'set_heating_setpoint':
            return True  # changing intent is not an ON command; native outage gate still applies
        # During restoration/dirty recovery, no ordinary ON or heat command may
        # race with speed restoration. OFF remains available for safety.
        if method == "request_changes" and len(args) == 2:
            obj, changes = args
            if obj in {"B1101", "B1202"}:
                return all(str(v).upper() in {"OFF", "00000"} for v in changes.values())
            return obj in {p[0] for p in PROGRAMS.values()}  # separately permit-gated
        return method == "set_circuit_state" and args[1] is False
