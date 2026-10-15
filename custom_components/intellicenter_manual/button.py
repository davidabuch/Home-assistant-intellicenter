"""Explicit operator actions; never apply drafts merely because they changed."""
from homeassistant.components.button import ButtonEntity


class GuardianAction(ButtonEntity):
    def __init__(self, entry, apply):
        self._guardian = entry.runtime_data.guardian
        self._apply = apply
        key = "apply_configuration_changes" if apply else "reconcile_pump_speeds"
        self._attr_name = "Apply Configuration Changes" if apply else "Reconcile Pump Speeds"
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_press(self):
        if self._apply: await self._guardian.core.apply()
        else: await self._guardian.reconcile("manual_button")


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([GuardianAction(entry, True), GuardianAction(entry, False)])
