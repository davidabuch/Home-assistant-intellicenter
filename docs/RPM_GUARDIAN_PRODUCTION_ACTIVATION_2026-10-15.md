# RPM Guardian production activation — October 15, 2026

Production enabled at **18:00:09 PDT**, following the operator's explicit approval
for unattended Guardian operation and ongoing guarded running-Pool writes.
No simulated outage, fault injection, restart or native RPM write was performed
during activation.

## Preflight and source

Fresh live preflight passed: normal healthy grid; simulation/outage OFF;
real-sensor mode/protection ON; bypass OFF; no session, intent, restoration,
pending edits or unverified write. Native identity and all five presets matched.
Pool/Spa OFF, pump0, actual heat OFF, AUTO, no freeze/sanitation/accessories active.
Master automatic authority ON, schedule claim OFF. Ledger475/480.

Installed component revision: 5d463dfd59ac1290c47f5f579d399b4935ecb2ab (PR106).
Approved main at activation: c684f63c81ad6cb9424a55b8eeee93e7f89ff481 (PR107).
Component files are identical; PR107 changes only documentation/dashboard wording.
[PR106 CI](https://github.com/davidabuch/Home-assistant-intellicenter/actions/runs/38831421930)
and [PR107 CI](https://github.com/davidabuch/Home-assistant-intellicenter/actions/runs/38832089576)
passed. Test F suite remains214 passing tests; no runtime code changed for activation.

## Guarded activation and persistence

Used only intellicenter_manual.configure_rpm_guardian with the exact config entry,
required confirmation, enabled=true and approve_running_pool_write=true.
Preserved all floors, applied/draft values and180-second settling.

Both flags verified true in live HA and by a read-only projection of the actual
HA Store file after the service returned. Store version1, mtime1792112409.625958,
journal session/intent null, restoration_pending false. No storage editing or
restart was used to establish persistence.

The running flag is an ongoing scoped production permission. It permits the
existing guarded Pool outage/restoration exception when all other gates pass;
ordinary configuration correction still requires safe idle equipment.
No second native writer or broad native commissioning bypass was enabled.

## Native readbacks and automatic verification

| Program | Native identity | Applied normal | Native readback |
|---|---|---:|---:|
| Pool | p0102 / C0006 / PMP01 / RPM |2600|2600|
| Spa | p0101 / C0001 / PMP01 / RPM |2600|2600|
| Sanitation | p0103 / FTR02 / PMP01 / RPM |3200|3200|
| Heater | p0104 / X0051 / PMP01 / RPM |3000|3000|
| Solar | p0105 / X0052 / PMP01 / RPM |2900|2900|

Temporary outage policy1500 applies to existing Pool p0102. Removed native
Grid Outage circuit/program was not recreated. PoolOS remains retired.

First enabled automatic minute reconciliation at **18:01:00 PDT**:
trace0bcd9d989b726770faa0f3483d0f8bd5, time-pattern trigger, service
reconcile_pump_speeds(reason=ha_policy_request), finished without error at
18:01:00.063831. Native verification timestamps refreshed for all five programs.
State NORMAL, all MATCH, active failure null, no pending edits, no recovery,
normal-control interlock OFF. Prior correction count6 and failed-write count0
unchanged. The disarmed status cleared naturally after successful reconciliation;
historical startup guard and prior outage verification remain historical evidence.

Pool/Spa remained OFF and pump0 through activation and the automatic run, with
their last_changed timestamps unchanged. Roof81°F, actual76°F/target90°F, selected
source Solar but actual heating OFF. Ledger475/480 and masterON/claimOFF unchanged.
No unintended circuit or pump start, conflicting native writes or normal-control
block appeared.

## Controller and dashboard

Solar/filtration, heating-preference and reconciliation automations remain ON.
Grid detection/rearm, Pool safety supervisor, bypass preservation, safety alert,
sanitation two-stage outage shutdown and Pool/Spa sanitation session manager all
read back ON, with no active queue. Freeze/native AUTO state and existing
Spa/manual/sanitation guards are preserved. They were inspected and regression
tested, not physically stimulated again during this activation.

Dashboard visually verified: enabled gate, NORMAL, five MATCH values, pump0,
outageOFF, no restoration, no current failure, last scheduled success,6/0 writes,
no pending changes. Historical outage runtime result clearly labeled last observed.

## Production status and limits

**PRODUCTION ENABLED.** Real-grid sensing ON, simulation OFF, protection ON,
bypass OFF, both required RPM flags true and durably saved. Ready to handle a
qualified real-grid outage through the existing five-minute loss qualification,
guarded1500 override, two-minute return qualification and verified normal2600
restoration before independent demand reevaluation. Future execution remains
conditional on fresh observations, authority and equipment safety; unsafe writes
defer visibly.

Evidence levels:214 code tests; Test F offline fault scenarios; actual normal HA
restart F2; earlier physical B–E native write/1500/restoration/Solar2900 proof;
this activation and first enabled automatic reconciliation verified in HA.
No additional physical outage occurred. A real unattended outage cycle has not
yet been observed. Midnight catch-up/completion, next08:00 rollover and next
eligible Solar restart remain pending natural observation.

Residual limits: host/storage corruption may require operator recovery;
Pentair power-cycle persistence and quantitative flow certification not physically
tested; pre-existing missed08:00 rollover across HA downtime remains outside scope.
No claim of future operational events passing is made.

Local evidence bundle: rpm-guardian-production-evidence.json; durable-storage and
production-dashboard screenshots in the commissioning deliverables.

