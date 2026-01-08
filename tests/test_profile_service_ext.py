"""Extreme tests for ProfileService coverage."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.services.profile_service import ProfileService
from custom_components.cronostar.const import DOMAIN

@pytest.fixture
def profile_service(hass, mock_storage_manager):
    settings_manager = MagicMock()
    settings_manager.load_settings = AsyncMock(return_value={})
    return ProfileService(hass, mock_storage_manager, settings_manager)

@pytest.mark.anyio
async def test_get_profile_data_diagnostics_extended(hass, profile_service, mock_storage_manager):
    """Trigger lines 276-330 in get_profile_data."""
    mock_storage_manager.get_cached_containers = AsyncMock(side_effect=[
        [], # requested not found
        [("f1.json", {"meta": {"preset_type": "thermostat", "global_prefix": "p1"}, "profiles": {"P1": {}}})] # available
    ])
    
    res = await profile_service.get_profile_data("Missing", "thermostat", global_prefix="p1")
    assert "available_in_storage" in res

@pytest.mark.anyio
async def test_register_card_entity_states_error(hass, profile_service, mock_storage_manager):
    """Hit line 442-443 in register_card (exception in state populating)."""
    call = MagicMock()
    call.data = {"card_id": "c1", "preset": "thermostat", "global_prefix": "p1"}
    
    # We want the exception to happen inside the try block starting at line 418
    # But get is also called at line 386.
    # We use side_effect with a function to only raise for specific entities
    def side_effect(entity_id):
        if entity_id == "light.test":
            raise Exception("State lookup failed")
        return MagicMock(state="on")
    
    hass.states.get.side_effect = side_effect
    
    # Mock get_profile_data to return something valid with the target entity that triggers exception
    with patch.object(profile_service, 'get_profile_data', return_value={
        "profile_name": "Default", "schedule": [], "meta": {"target_entity": "light.test"}
    }):
        res = await profile_service.register_card(call)
        assert res["success"] is True

@pytest.mark.anyio
async def test_save_profile_update_entry_fields(hass, profile_service, mock_storage_manager):
    """Hit lines 108-109 in save_profile (updating entry with new meta)."""
    call = MagicMock()
    call.data = {
        "profile_name": "P1", "preset_type": "thermostat", 
        "global_prefix": "p1_", "meta": {"target_entity": "new.target", "preset_type": "fan"}
    }
    
    entry = MagicMock()
    entry.data = {"global_prefix": "p1_", "target_entity": "old.target", "preset_type": "thermostat"}
    entry.runtime_data = None
    
    hass.config_entries.async_entries.return_value = [entry]
    hass.config_entries.async_update_entry = MagicMock()
    
    await profile_service.save_profile(call)
    assert hass.config_entries.async_update_entry.called

@pytest.mark.anyio
async def test_validate_schedule_clamping(profile_service):

    """Hit more clamping branches in _validate_schedule."""

    schedule = [{"time": "08:00", "value": 5.0}]

    res = profile_service._validate_schedule(schedule, min_val=10.0)

    assert res[0]["value"] == 10.0

    

    schedule = [{"time": "08:00", "value": 50.0}]

    res = profile_service._validate_schedule(schedule, max_val=30.0, min_val=5.0)

    assert res[0]["value"] == 5.0



def test_validate_schedule_deduplication(profile_service):

    """Test sound logic: deduplicate points with same timestamp."""

    schedule = [

        {"time": "08:00", "value": 20.0},

        {"time": "08:00", "value": 22.0}, # Duplicate, last wins

        {"time": "10:00", "value": 18.0}

    ]

    res = profile_service._validate_schedule(schedule)

    assert len(res) == 2

    assert res[0]["time"] == "08:00"

    assert res[0]["value"] == 22.0

    assert res[1]["time"] == "10:00"
