"""Test Profile Service."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.core import HomeAssistant
from custom_components.cronostar.services.profile_service import ProfileService
from custom_components.cronostar.const import DOMAIN

@pytest.fixture
def profile_service(hass, mock_storage_manager):
    """Create ProfileService instance."""
    settings_manager = MagicMock()
    settings_manager.load_settings = AsyncMock(return_value={})
    
    return ProfileService(hass, mock_storage_manager, settings_manager)

@pytest.mark.anyio
async def test_save_profile(hass, profile_service, mock_storage_manager):
    """Test saving a profile."""
    call = MagicMock()
    call.data = {
        "profile_name": "NewProfile",
        "preset_type": "thermostat",
        "schedule": [{"time": "08:00", "value": 21.0}],
        "global_prefix": "test_prefix",
        "meta": {"min_value": 10, "max_value": 30}
    }
    
    # Mock config entries
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.flow.async_init = AsyncMock()
    
    await profile_service.save_profile(call)
    
    mock_storage_manager.save_profile.assert_called_once()
    
    # Ensure controller creation was triggered
    hass.config_entries.flow.async_init.assert_called_once()

@pytest.mark.anyio
async def test_save_profile_metadata_only(hass, profile_service, mock_storage_manager):
    """Test updating only metadata."""
    call = MagicMock()
    call.data = {
        "profile_name": "Default",
        "preset_type": "thermostat",
        "schedule": None, # Metadata only
        "global_prefix": "prefix_",
        "meta": {"title": "New Title"}
    }
    
    # Mock existing profile
    profile_service.get_profile_data = AsyncMock(return_value={
        "schedule": [{"time": "12:00", "value": 20.0}]
    })
    hass.config_entries.async_entries = MagicMock(return_value=[])
    
    await profile_service.save_profile(call)
    
    args = mock_storage_manager.save_profile.call_args[1]
    assert args["profile_data"]["schedule"][0]["value"] == 20.0
    assert args["metadata"]["title"] == "New Title"

@pytest.mark.anyio
async def test_save_profile_update_existing_entry(hass, profile_service):
    """Test saving a profile when entry already exists."""
    call = MagicMock()
    call.data = {
        "profile_name": "Existing",
        "preset_type": "thermostat",
        "schedule": [],
        "global_prefix": "existing_prefix_",
        "meta": {"target_entity": "new.target"}
    }
    
    entry = MagicMock()
    entry.data = {"global_prefix": "existing_prefix_", "target_entity": "old.target"}
    entry.runtime_data = MagicMock()
    entry.runtime_data.async_refresh_profiles = AsyncMock()
    
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    hass.config_entries.async_update_entry = MagicMock()
    
    await profile_service.save_profile(call)
    
    assert hass.config_entries.async_update_entry.called
    assert entry.runtime_data.async_refresh_profiles.called

@pytest.mark.anyio
async def test_ensure_controller_exists_naming(hass, profile_service):
    """Test name derivation in controller creation."""
    # Prefix: cronostar_thermostat_living_room_ -> Name: Living Room
    meta = {"target_entity": "climate.living_room"}
    
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.flow.async_init = AsyncMock()
    
    await profile_service._ensure_controller_exists("cronostar_thermostat_living_room_", "thermostat", meta)
    
    args = hass.config_entries.flow.async_init.call_args[1]
    assert args["data"]["name"] == "Living Room"

@pytest.mark.anyio
async def test_save_profile_validation(hass, profile_service):
    """Test validation during save."""
    call = MagicMock()
    call.data = {
        "profile_name": "BadProfile",
        "preset_type": "thermostat",
        "schedule": [
            {"time": "25:00", "value": 20}, # Invalid time
            {"time": "08:00", "value": 100}, # Above max
            {"time": "09:00", "value": float('nan')} # NaN
        ],
        "meta": {"max_value": 30}
    }
    
    hass.config_entries.async_entries = MagicMock(return_value=[])
    
    await profile_service.save_profile(call)
    
    args = profile_service.storage.save_profile.call_args[1]
    schedule = args["profile_data"]["schedule"]
    
    assert len(schedule) == 1
    assert schedule[0]["time"] == "08:00"
    assert schedule[0]["value"] == 0.0

@pytest.mark.anyio
async def test_load_profile(hass, profile_service):
    """Test loading a profile."""
    call = MagicMock()
    call.data = {
        "profile_name": "Default",
        "preset_type": "thermostat",
        "global_prefix": "cronostar_thermostat_test_"
    }
    
    result = await profile_service.load_profile(call)
    
    assert result["profile_name"] == "Default"
    assert len(result["schedule"]) == 2

@pytest.mark.anyio
async def test_get_profile_data_fallbacks(hass, profile_service, mock_storage_manager):
    """Test fallbacks in get_profile_data."""
    # Mock storage to NOT have the requested profile but HAVE "Comfort"
    mock_storage_manager.get_cached_containers = AsyncMock(return_value=[
        ("file.json", {
            "meta": {},
            "profiles": {
                "Comfort": {"schedule": []}
            }
        })
    ])
    
    result = await profile_service.get_profile_data("Missing", "thermostat")
    assert result["profile_name"] == "Comfort"

@pytest.mark.anyio
async def test_get_profile_data_diagnostics(hass, profile_service, mock_storage_manager):
    """Test diagnostic info when profile not found."""
    mock_storage_manager.get_cached_containers = AsyncMock(side_effect=[
        [], # First call (matching)
        [("f1.json", {"meta": {"preset_type": "thermostat"}, "profiles": {"P1": {}}})]
    ])
    
    result = await profile_service.get_profile_data("Missing", "thermostat")
    assert "error" in result
    assert result["error"] == "Profile not found"
    assert len(result["available_in_storage"]) == 1

@pytest.mark.anyio
async def test_register_card(hass, profile_service):
    """Test register_card."""
    call = MagicMock()
    call.data = {
        "card_id": "test_card",
        "preset": "thermostat",
        "global_prefix": "cronostar_thermostat_test_"
    }
    
    # Mock states for entities
    def get_state(entity_id):
        m = MagicMock()
        m.state = "on"
        return m
    hass.states.get.side_effect = get_state
    
    # Mock preset defaults file
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.read_text", return_value='{"default_val": 1}'):
        
        result = await profile_service.register_card(call)
        
        assert result["success"] is True
        assert result["preset_defaults"]["default_val"] == 1
        assert result["entity_states"]["enabled"] == "on"

@pytest.mark.anyio
async def test_async_update_profile_selectors(hass, profile_service, mock_storage_manager):
    """Test updating profile selectors."""
    mock_storage_manager.list_profiles = AsyncMock(return_value=["f1.json"])
    mock_storage_manager.load_profile_cached = AsyncMock(return_value={
        "meta": {"global_prefix": "prefix_"},
        "profiles": {"P1": {}}
    })
    
    # Mock input_select entities
    s1 = MagicMock()
    s1.entity_id = "input_select.prefix_profiles"
    s1.attributes = {"options": []}
    hass.states.async_all = MagicMock(return_value=[s1])
    
    await profile_service.async_update_profile_selectors()
    
    assert hass.services.async_call.called
    args = hass.services.async_call.call_args[0]
    assert args[0] == "input_select"
    assert args[1] == "set_options"
    assert "P1" in args[2]["options"]

@pytest.mark.anyio
async def test_async_update_profile_selectors_error(hass, profile_service, mock_storage_manager):
    """Test error handling in update profile selectors."""
    mock_storage_manager.list_profiles = AsyncMock(return_value=["f1.json"])
    mock_storage_manager.load_profile_cached = AsyncMock(side_effect=Exception("load failed"))
    
    # Should not raise
    await profile_service.async_update_profile_selectors()