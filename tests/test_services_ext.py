"""Test Profile Service Extensions."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.services.profile_service import ProfileService

@pytest.fixture
def profile_service(hass, mock_storage_manager):
    settings_manager = MagicMock()
    return ProfileService(hass, mock_storage_manager, settings_manager)

@pytest.mark.anyio
async def test_validate_schedule_out_of_range(profile_service):
    """Test value clamping in schedule validation."""
    schedule = [
        {"time": "08:00", "value": 5.0},  # Below min (10)
        {"time": "12:00", "value": 35.0}, # Above max (30)
    ]
    
    # 1. Clamping to min/max
    validated = profile_service._validate_schedule(schedule, min_val=10, max_val=30)
    assert validated[0]["value"] == 10.0
    assert validated[1]["value"] == 10.0 # Logic says reset to min_val if above max?
    # Wait, check logic in profile_service.py:558
    # elif max_val is not None and numeric_value > float(max_val):
    #     numeric_value = float(min_val) if min_val is not None else 0.0
    # Yes, it resets to min_val.

@pytest.mark.anyio
async def test_ensure_controller_exists_already_exists(hass, profile_service):
    """Test no action when controller already exists."""
    hass.config_entries.async_entries = MagicMock(return_value=[
        MagicMock(data={"global_prefix": "exists_"})
    ])
    hass.config_entries.flow.async_init = AsyncMock()
    
    await profile_service._ensure_controller_exists("exists_", "thermostat", {})
    assert not hass.config_entries.flow.async_init.called

@pytest.mark.anyio
async def test_get_profile_data_default_comfort_fallbacks(hass, profile_service, mock_storage_manager):
    """Test fallbacks to Default/Comfort names."""
    mock_storage_manager.get_cached_containers = AsyncMock(return_value=[
        ("file.json", {
            "meta": {},
            "profiles": {
                "Comfort": {"schedule": []}
            }
        })
    ])
    
    # Search for something else, should find Comfort
    result = await profile_service.get_profile_data("NonExistent", "thermostat")
    assert result["profile_name"] == "Comfort"

@pytest.mark.anyio
async def test_profile_service_save_exception(hass, profile_service, mock_storage_manager):
    """Test exception handling in save_profile."""
    call = MagicMock()
    call.data = {"profile_name": "Error"}
    mock_storage_manager.save_profile = AsyncMock(side_effect=Exception("Disk full"))
    
    from homeassistant.exceptions import HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await profile_service.save_profile(call)
