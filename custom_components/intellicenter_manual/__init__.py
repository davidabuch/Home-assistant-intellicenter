"""Minimal manual IntelliCenter integration. No autonomous controller is imported."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do not claim readiness until a real transport is implemented and tested."""
    raise RuntimeError("IntelliCenter Manual Bridge transport not implemented; do not install yet")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
