"""Ultra final tests for coverage."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import sys
from custom_components.cronostar.const import DOMAIN
from custom_components.cronostar.storage.storage_manager import StorageManager
from custom_components.cronostar.setup.services import setup_services, async_unload_services
from pathlib import Path

@pytest.mark.anyio
async def test_unload_services(hass):
    """Test unloading services."""
    await async_unload_services(hass)
    assert hass.services.async_remove.called

@pytest.mark.anyio
async def test_storage_list_profiles_complex_prefix(hass):
    """Test list_profiles with complex prefix fallback logic."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    
    p1 = MagicMock(spec=Path)
    p1.name = "cronostar_myprefix_thermostat_data.json"
    
    with patch("pathlib.Path.glob", return_value=[p1]):
        manager.load_profile_cached = AsyncMock(return_value={
            "meta": {} # No prefix, no preset in meta
        })
        
        # This hits line 261-269 fallback
        res = await manager.list_profiles(prefix="myprefix_thermostat")
        assert len(res) == 1

@pytest.mark.anyio
async def test_storage_load_all_profiles_exception(hass):
    """Test load_all_profiles with a file that causes exception."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    
    # Mock FileChecker module manually
    mock_checker_mod = MagicMock()
    mock_checker_cls = mock_checker_mod.FileChecker
    mock_checker = mock_checker_cls.return_value
    mock_checker._validate_profile_file = AsyncMock(return_value={"valid": True})
    
    with patch.dict(sys.modules, {"custom_components.cronostar.deep_checks.file_checker": mock_checker_mod}):
        with patch("pathlib.Path.glob") as mock_glob:
            p1 = MagicMock(spec=Path)
            p1.name = "cronostar_error.json"
            mock_glob.return_value = [p1]
            
            # Force load_container to raise
            manager._load_container = AsyncMock(side_effect=Exception("Load error"))
            
            res = await manager.load_all_profiles()
            # If load_container raises outside the loop context, res will be empty
            assert res == {}

@pytest.mark.anyio
async def test_apply_now_handler_unsupported_domain(hass):
    """Test apply_now handler with unsupported domain."""
    await setup_services(hass, MagicMock())
    handler = next(c[0][2] for call in [hass.services.async_register.call_args_list] for c in call if c[0][1] == "apply_now")
    
    ps = hass.data[DOMAIN]["profile_service"]
    ps.get_profile_data = AsyncMock(return_value={
        "schedule": [{"time": "00:00", "value": 20.0}]
    })
    
    call = MagicMock()
    call.data = {"target_entity": "unsupported.entity", "profile_name": "Default"}
    await handler(call)

@pytest.mark.anyio
async def test_storage_list_profiles_exception(hass):
    """Test list_profiles exception path."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    with patch("pathlib.Path.glob", side_effect=Exception("Glob error")):
        res = await manager.list_profiles()
        assert res == []

@pytest.mark.anyio
async def test_storage_get_profile_list_exception(hass):
    """Test get_profile_list exception path."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    with patch("custom_components.cronostar.storage.storage_manager.build_profile_filename", side_effect=Exception("Error")):
        res = await manager.get_profile_list("thermostat", "p1")
        assert res == []