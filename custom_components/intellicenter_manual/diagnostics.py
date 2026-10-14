"""Read-only diagnostics for native IntelliCenter feature discovery.

No network commands, writes, or physical actuation.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .transport import CIRCUIT_TYPE, SNAME_ATTR, STATUS_ATTR, SUBTYP_ATTR, _native_status


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    transport = entry.runtime_data.transport
    observation = transport.read_observation()
    circuits = []
    for obj in transport.model.get_by_type(CIRCUIT_TYPE):
        native_id = str(obj.objnam)
        raw_name = obj.properties.get(SNAME_ATTR)
        # Restrict diagnostic payload to the Sanitation feature and omit other equipment.
        if native_id != "FTR02" and str(raw_name or "").strip().casefold() != "sanitation":
            continue
        raw_status = obj.properties.get(STATUS_ATTR)
        circuits.append({
            "native_id": native_id,
            "native_type": str(obj.objtype),
            "native_subtype": str(obj.subtype),
            "name": str(raw_name),
            "status_present": STATUS_ATTR in obj.properties,
            "raw_status": str(raw_status) if raw_status is not None else None,
            "interpreted_status": _native_status(raw_status),
            "attribute_keys": sorted(str(key) for key in obj.properties),
        })
    selected = transport.sanitation_circuit_id()
    circuit = observation.circuit(selected) if selected else None
    return {
        "connected": transport.connected,
        "observation_connected": observation.connected,
        "selected_sanitation_id": selected,
        "observed_sanitation_active": circuit.active if circuit else None,
        "candidate_circuits": circuits,
    }
