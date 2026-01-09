"""Absolute final tests."""

from unittest.mock import MagicMock

import pytest
from custom_components.cronostar.const import CONF_TARGET_ENTITY
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.services.profile_service import ProfileService
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.anyio
async def test_profile_service_missing_name_save(hass):
    """Trigger line 59 in profile_service."""
    ps = ProfileService(hass, MagicMock(), MagicMock())
    call = MagicMock()
    call.data = {"profile_name": ""}  # Missing
    with pytest.raises(HomeAssistantError):
        await ps.save_profile(call)


@pytest.mark.anyio
async def test_profile_service_missing_name_load(hass):
    """Trigger line 187 in profile_service."""
    ps = ProfileService(hass, MagicMock(), MagicMock())
    call = MagicMock()
    call.data = {"profile_name": ""}  # Missing
    res = await ps.load_profile(call)
    assert "error" in res


@pytest.mark.anyio
async def test_coordinator_target_missing_logging(hass):
    """Trigger lines 119, 122 in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True

    hass.states.get.return_value = None
    res = await coordinator._async_update_data()
    assert res is not None
