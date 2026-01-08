"Tests for setup preload and resource registration."
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.setup import _preload_profile_cache, _setup_static_resources
from pathlib import Path

@pytest.mark.anyio
async def test_preload_profile_cache_with_files(hass):
    """Test preloading cache with actual profile files."""
    storage_manager = MagicMock()
    storage_manager.list_profiles = AsyncMock(return_value=["f1.json", "f2.json"])
    storage_manager.load_profile_cached = AsyncMock(side_effect=[
        {"meta": {"global_prefix": "p1"}},
        None # Failed load
    ])
    storage_manager.get_cached_containers = AsyncMock(return_value=[
        ("f1.json", {"meta": {"global_prefix": "p1"}, "profiles": {"P1": {}}})
    ])
    
    await _preload_profile_cache(hass, storage_manager)
    assert storage_manager.load_profile_cached.called

@pytest.mark.anyio
async def test_preload_profile_cache_empty(hass):
    """Test preloading cache when no files exist."""
    storage_manager = MagicMock()
    storage_manager.list_profiles = AsyncMock(return_value=[])
    await _preload_profile_cache(hass, storage_manager)
    # Should log and return

@pytest.mark.anyio
async def test_setup_static_resources_full(hass):
    """Test full static resource setup with all components."""
    from custom_components.cronostar.setup import _setup_static_resources
    
    integration = MagicMock()
    integration.version = "1.0.0"
    hass.config.components = ["http", "frontend"]
    
    # Mocking HAS_STATIC_PATH_CONFIG
    with patch("custom_components.cronostar.setup.HAS_STATIC_PATH_CONFIG", True), \
         patch("custom_components.cronostar.setup.StaticPathConfig", MagicMock()), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("homeassistant.loader.async_get_integration", return_value=integration), \
         patch("custom_components.cronostar.setup.add_extra_js_url") as mock_add_js:
        
        hass.http.async_register_static_paths = AsyncMock()
        
        success = await _setup_static_resources(hass)
        assert success is True
        assert hass.http.async_register_static_paths.called
        assert mock_add_js.called

@pytest.mark.anyio
async def test_setup_static_resources_old_ha(hass):
    """Test resource setup for older HA versions (without StaticPathConfig)."""
    from custom_components.cronostar.setup import _setup_static_resources
    
    integration = MagicMock()
    integration.version = "1.0.0"
    hass.config.components = ["http", "frontend"]
    
    with patch("custom_components.cronostar.setup.HAS_STATIC_PATH_CONFIG", False), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("homeassistant.loader.async_get_integration", return_value=integration), \
         patch("custom_components.cronostar.setup.add_extra_js_url"):
        
        hass.http.async_register_static_path = MagicMock()
        
        success = await _setup_static_resources(hass)
        assert success is True
        assert hass.http.async_register_static_path.called

