"""Structural regression gates for the staged, NOT DEPLOYED Cleaning idle-start candidate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "ha_automations/fixtures/cleaning_20261024/schedule.original.json"
CANDIDATE = ROOT / "ha_automations/pool_simple_solar_and_filtration_cleaning_idle_start_CANDIDATE.json"


def test_cleaning_start_is_only_added_trigger_and_normal_scheduler_unchanged():
    original = json.loads(ORIGINAL.read_text())
    candidate = json.loads(CANDIDATE.read_text())
    # Original fixture is the captured HA configuration, with the same trigger/action shape.
    original = original.get("config", original)
    assert candidate["triggers"][:-1] == original["triggers"]
    assert candidate["actions"][2:] == original["actions"]
    assert candidate["mode"] == original["mode"] == "queued"
    assert candidate["triggers"][-1] == {
        "trigger": "state", "entity_id": "binary_sensor.pool_cleaning_active",
        "from": "off", "to": "on", "for": "00:00:02", "id": "cleaning_idle_start",
    }


def test_cleaning_path_is_on_only_and_fail_closed():
    c = json.loads(CANDIDATE.read_text())
    startup, stop = c["actions"][:2]
    assert startup["then"] == [{
        "action": "climate.set_hvac_mode",
        "target": {"entity_id": "climate.pool_thermostat"},
        "data": {"hvac_mode": "heat"},
    }]
    assert stop["if"] == [{"condition": "trigger", "id": "cleaning_idle_start"}]
    assert "stop" in stop["then"][0]
    conditions = startup["if"]
    required = {
        ("binary_sensor.pool_cleaning_active", "on"),
        ("climate.pool_thermostat", "off"),
        ("climate.hot_tub_thermostat", "off"),
        ("input_boolean.pool_automatic_ownership", "on"),
        ("input_boolean.grid_outage_active", "off"),
        ("sensor.system_mode", "AUTO"),
        ("binary_sensor.freeze_protection_active", "off"),
        ("binary_sensor.rpm_guardian_blocks_normal_control", "off"),
    }
    actual = {(x.get("entity_id"), x.get("state")) for x in conditions if x.get("condition") == "state"}
    assert required <= actual
    assert any(x.get("entity_id") == "sensor.native_observation_age" and x.get("below") == 30 for x in conditions)
    assert not any(x.get("action") == "switch.turn_on" for x in startup["then"])


def test_cleaning_trigger_never_falls_through_and_unsafe_states_block_start():
    candidate = json.loads(CANDIDATE.read_text())
    start, terminator = candidate["actions"][:2]
    assert terminator["if"] == [{"condition": "trigger", "id": "cleaning_idle_start"}]
    assert "stop" in terminator["then"][0]
    required = {x["entity_id"]: x["state"] for x in start["if"] if x["condition"] == "state"}
    assert len(required) == 14
    for entity, expected in required.items():
        assert expected in ("on", "off", "AUTO")
        # Any changed, missing or unknown safety state must prevent startup.
        assert "unknown" != expected, entity
    assert all(x.get("action") != "climate.set_hvac_mode" or x["data"]["hvac_mode"] != "off" for x in start["then"])
    assert candidate["actions"][2:] == json.loads(ORIGINAL.read_text())["actions"]
