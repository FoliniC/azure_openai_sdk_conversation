"""Tests for more service logic paths."""
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
async def test_get_profile_data_invalid_prefix(profile_service, mock_storage_manager):
    """Test get_profile_data with a generic prefix."""
    result = await profile_service.get_profile_data("Default", "thermostat", global_prefix="cronostar_")
    assert result["profile_name"] == "Default"

@pytest.mark.anyio
async def test_register_card_missing_profile(hass, profile_service, mock_storage_manager):
    """Test register_card when profile is missing and fallback fails."""
    call = MagicMock()
    call.data = {"card_id": "c1", "preset": "thermostat", "global_prefix": "p1"}
    
    with patch.object(profile_service, 'get_profile_data', return_value={"error": "Not found"}):
        result = await profile_service.register_card(call)
        assert result["profile_data"] is None
        assert result["diagnostics"] == {"error": "Not found"}

@pytest.mark.anyio
async def test_ensure_controller_exists_custom_naming(hass, profile_service):
    """Test ensure_controller_exists with different prefix patterns."""
    hass.config_entries.async_entries.return_value = []
    hass.config_entries.flow.async_init = AsyncMock()
    
    await profile_service._ensure_controller_exists("prefix", "thermostat", {})
    args = hass.config_entries.flow.async_init.call_args[1]
    # "prefix" becomes "Prefix" in deriving name
    assert "Prefix" in args["data"]["name"]

@pytest.mark.anyio
async def test_validate_schedule_edge_cases(profile_service):
    """Test _validate_schedule with various inputs."""
    assert profile_service._validate_schedule(None) == []
    assert profile_service._validate_schedule(["not a dict"]) == []
    assert profile_service._validate_schedule([{"time": "08:00"}]) == []
    assert profile_service._validate_schedule([{"time": "8:00", "value": 20}]) == []

@pytest.mark.anyio
async def test_list_all_profiles_service(hass, mock_storage_manager):
    """Test list_all_profiles service handler from setup/services.py."""
    from custom_components.cronostar.setup.services import setup_services
    
    # Ensure hass.data is properly initialized
    hass.data[DOMAIN] = {
        "settings_manager": MagicMock()
    }
    
    await setup_services(hass, mock_storage_manager)
    
    handler = None
    for call in hass.services.async_register.call_args_list:
        if call[0][1] == "list_all_profiles":
            handler = call[0][2]
            break
    
    mock_storage_manager.list_profiles.return_value = ["f1.json"]
    mock_storage_manager.load_profile_cached.return_value = {
        "meta": {"preset_type": "thermostat", "global_prefix": "p1_"},
        "profiles": {"Default": {"schedule": [], "updated_at": "now"}}
    }
    
    call = MagicMock()
    call.data = {"force_reload": True}
    res = await handler(call)
    
    assert "thermostat" in res
    assert res["thermostat"]["files"][0]["filename"] == "f1.json"