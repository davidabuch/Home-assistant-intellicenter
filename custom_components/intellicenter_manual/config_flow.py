"""Explicit host configuration for the manual IntelliCenter bridge."""
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class IntelliCenterManualConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            host = user_input["host"].strip()
            if not host:
                return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required("host"): str}), errors={"base": "invalid_host"})
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"IntelliCenter ({host})", data={"host": host})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required("host"): str}))
