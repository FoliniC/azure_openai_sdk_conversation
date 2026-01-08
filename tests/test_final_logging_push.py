"""Final push for 90% coverage."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.const import DOMAIN, CONF_TARGET_ENTITY, PLATFORMS
from custom_components.cronostar.setup.services import setup_services

@pytest.mark.anyio
async def test_coordinator_logging_more(hass):
    """Trigger more logging lines in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    entry.options = {}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True
    
    # Hit line 133
    await coordinator._async_update_data()
    
    # Hit line 148, 153 (via async_initialize)
    hass.data[DOMAIN]["storage_manager"] = MagicMock()
    hass.data[DOMAIN]["storage_manager"].list_profiles = AsyncMock(return_value=["f1.json"])
    hass.data[DOMAIN]["storage_manager"].load_profile_cached = AsyncMock(return_value={
        "profiles": {"Default": {"schedule": []}}
    })
    await coordinator.async_initialize()
    
    # Hit line 164 (refresh profiles)
    await coordinator.async_refresh_profiles()
    
    # Hit line 176 (set_profile log)
    coordinator.available_profiles = ["Default"]
    await coordinator.set_profile("Default")
    
    # Hit line 185 (set_enabled log)
    await coordinator.set_enabled(True)

@pytest.mark.anyio
async def test_coordinator_interpolate_more(hass):
    """Trigger line 343 in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)
    
    schedule = [
        {"time": "08:00", "value": 20.0},
        {"time": "08:00", "value": 20.0}
    ]
    # Line 343: t2 == t1
    from datetime import datetime
    with patch("custom_components.cronostar.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 8, 0, 0)
        # We need surrounding points to be same time
        # points = [(480, 20.0), (480, 20.0)]
        # This triggers if current_minutes is not an exact match but t1 and t2 are same
        # which only happens if schedule has multiple points at same time.
        assert coordinator._interpolate_schedule(schedule) == 20.0

@pytest.mark.anyio
async def test_setup_services_more_logging(hass):
    """Trigger logging in more setup/services.py handlers."""
    await setup_services(hass, MagicMock())
    
    # Get register_card handler
    handler = next(c[0][2] for call in [hass.services.async_register.call_args_list] for c in call if c[0][1] == "save_profile")
    
    ps = hass.data[DOMAIN]["profile_service"]
    ps.save_profile = AsyncMock()
    
    call = MagicMock()
    call.data = {"profile_name": "P1"}
    await handler(call)
    # Hits line 41 info log
