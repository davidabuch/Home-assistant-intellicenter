"""Native controller remains fail-closed until explicit authority cutover."""
import pytest
from unittest.mock import AsyncMock, patch
from custom_components.intellicenter_manual.transport import _CommissioningController, ManualCommandError


@pytest.mark.asyncio
async def test_controller_rejects_write_by_default():
    controller = object.__new__(_CommissioningController)
    controller.manual_writes_enabled = False
    with pytest.raises(ManualCommandError):
        await controller.request_changes("B1101", {"STATUS": "ON"})
    with pytest.raises(ManualCommandError):
        await controller._queue_property_change("B1202", {"LOTMP": "99"})
    with pytest.raises(ManualCommandError):
        await controller.send_cmd("SetParamList", {})


@pytest.mark.asyncio
async def test_controller_delegates_only_when_explicitly_armed():
    controller = object.__new__(_CommissioningController)
    controller.manual_writes_enabled = True
    with patch("pyintellicenter.ICModelController.request_changes", new_callable=AsyncMock) as mock:
        await controller.request_changes("B1101", {"STATUS": "ON"})
        mock.assert_awaited_once()
