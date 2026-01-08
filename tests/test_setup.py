"""Test Component Setup."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.setup import async_setup_integration
from custom_components.cronostar.setup.events import setup_event_handlers
from homeassistant.core import CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_START

@pytest.mark.anyio
async def test_async_setup_integration(hass):
    """Test full integration setup."""
    config = {
        "version": "1.0.0",
        "enable_backups": True,
        "logging_enabled": True
    }
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_dir", return_value=True), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.touch"), \
         patch("pathlib.Path.unlink"):
        
        with patch("custom_components.cronostar.setup.StorageManager") as mock_storage_mgr_cls, \
             patch("custom_components.cronostar.setup.SettingsManager"):
            
            mock_storage = mock_storage_mgr_cls.return_value
            mock_storage.list_profiles = AsyncMock(return_value=[])
            mock_storage.get_cached_containers = AsyncMock(return_value=[])
            
            success = await async_setup_integration(hass, config)
            
            assert success is True
            assert "cronostar" in hass.data

@pytest.mark.anyio
async def test_setup_event_handlers_running(hass):
    """Test events setup when HA is already running."""
    storage_manager = MagicMock()
    storage_manager.list_profiles = AsyncMock(return_value=["f1.json"])
    storage_manager.load_profile_cached = AsyncMock()
    
    hass.state = CoreState.running
    await setup_event_handlers(hass, storage_manager)
    
    assert hass.async_create_task.called
    
    # Extract the coro
    handler = hass.async_create_task.call_args[0][0]
    await handler
    
    assert storage_manager.list_profiles.called

@pytest.mark.anyio
async def test_setup_event_handlers_starting(hass):
    """Test events setup when HA is starting."""
    storage_manager = MagicMock()
    storage_manager.list_profiles = AsyncMock(return_value=[])
    
    hass.state = CoreState.starting
    await setup_event_handlers(hass, storage_manager)
    
    assert hass.bus.async_listen_once.called
    args = hass.bus.async_listen_once.call_args[0]
    assert args[0] == EVENT_HOMEASSISTANT_START
    
    # Call the handler manually
    handler = args[1]
    await handler(None)
    assert storage_manager.list_profiles.called