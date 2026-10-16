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
            "sanitation": ("p0103", "FTR02"), "heater": ("p0104", "X0051"),
            "solar": ("p0105", "X0052")}
DEFAULTS = {"pool": 2600, "spa": 2600, "sanitation": 3200,
            "heater": 3000, "solar": 2900, "outage": 1500}
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
                        raise ValueError("Incomplete RPM policy")
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
                self.data.update(deepcopy(stored))
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
                or not sample.known or not sample.safe):
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
        return (not sample.protected and not self.blocks_normal
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
            sample = self.conditions()
            try:
                self.data['results'] = {key: 'UNKNOWN' for key in PROGRAMS}
                if not sample.fresh:
                    raise RuntimeError("Fresh native observations required")
                # Identity validation is in read(), never skipped for a match.
                actual = {}
                for key in PROGRAMS:
                    try: actual[key] = self.read(key)
                    except Exception as exc:
                        self.data['results'][key] = f'FAILED: {exc}'
                        raise RuntimeError(f'{key} native identity/readback unavailable: {exc}') from exc
                self.data["last_observed"] = actual
                desired = dict(self.data["applied"])
                if sample.protected:
                    desired["pool"] = desired["outage"]
                self.data["results"] = {key: "MATCH" if actual[key] == desired[key]
                    else "PENDING" for key in PROGRAMS}
                for key in PROGRAMS:
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
                    self.data["state"] = "NORMAL"
                    for key in PROGRAMS:
                        if actual[key] != desired[key]:
                            await self._change(key, desired[key], "normal")
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
