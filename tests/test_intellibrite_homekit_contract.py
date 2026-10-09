"""Offline contract regressions for the audited IntelliBrite HomeKit button surface.

These tests do not call Home Assistant or command equipment. They verify that
the documented migration contract remains complete and internally consistent.
Live HA action parity must still be rechecked before an authorized cutover.
"""
from pathlib import Path
import re
import unittest

DOC = Path(__file__).resolve().parents[1] / "docs" / "INTELLIBRITE_HOMEKIT_BUTTON_PARITY_2026-10-08.md"
EXPECTED = {
    "sam_pool": ("poolos_pool_light_sam", "SAm"),
    "american_pool": ("american_pool", "American"),
    "blue_pool_light": ("blue_pool_light", "Blue"),
    "caribbean_pool": ("carribean_pool", "Caribbean"),
    "green_pool_light": ("green_pool_light", "Green"),
    "magenta_pool_light": ("turn_pool_light_magenta", "Magenta"),
    "party_mode_pool": ("party_pool", "Party Mode"),
    "red_pool_light": ("turn_pool_light_red", "Red"),
    "romance_pool": ("romance_pool", "Romance"),
    "royal_pool": ("turn_on_royal_pool", "Royal"),
    "sunset_pool": ("sunset_pool", "Sunset"),
    "white_pool_light": ("turn_on_white_pool_light", "White"),
}
ROW = re.compile(
    r"^\| `input_button\.([^\x60]+)` \| `automation\.([^\x60]+)`"
    r" \| legacy PoolOS pool light \| `([^\x60]+)` \|$",
    re.MULTILINE,
)


class TestIntelliBriteHomeKitContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.rows = ROW.findall(cls.text)

    def test_twelve_unique_buttons(self):
        self.assertEqual(len(self.rows), 12)
        self.assertEqual(len({button for button, _, _ in self.rows}), 12)

    def test_exact_live_audited_button_mapping(self):
        self.assertEqual(
            {button: (automation, effect) for button, automation, effect in self.rows},
            EXPECTED,
        )

    def test_party_alias_and_caribbean_spelling_are_preserved(self):
        actual = {button: (automation, effect) for button, automation, effect in self.rows}
        self.assertEqual(actual["party_mode_pool"][1], "Party Mode")
        self.assertEqual(actual["caribbean_pool"], ("carribean_pool", "Caribbean"))
        self.assertEqual(actual["sam_pool"][1], "SAm")

    def test_hardware_registration_delay_not_removed(self):
        self.assertIn("20 seconds", self.text)
        self.assertIn("controller to register", self.text)
        self.assertIn("30 seconds", self.text)

    def test_no_authorized_control_handoff_in_contract(self):
        self.assertIn("allow_commands=False", self.text)
        self.assertIn("No physical scene-button tests were performed", self.text)
        self.assertIn("light.poolos_native_intellicenter_pool_light", self.text)


if __name__ == "__main__":
    unittest.main()
