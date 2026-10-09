"""Source-level regression checks for the persistent command authority boundary."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'custom_components' / 'intellicenter_manual' / '__init__.py'


def test_native_authority_contract_compiles():
    ast.parse(SOURCE.read_text())


def test_persistent_authority_and_legacy_gate():
    source = SOURCE.read_text()
    assert 'hass.config_entries.async_entries("poolos")' in source
    assert 'if not legacy_entries:' in source
    assert 'native_command_authority' in source
    assert '_exclusive_manual_authority()' in source
    assert 'observation.observed_at is not None' in source
    assert 'transport.arm_manual_thermostats()' in source
    assert 'transport.disarm_manual_thermostats()' in source
    assert '_reacquire_native_authority()' in source
    assert 'timedelta(seconds=30)' in source
