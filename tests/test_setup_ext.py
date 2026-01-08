"""Tests for more setup and validator paths."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.setup import async_setup_integration
from custom_components.cronostar.setup.validators import validate_environment, _check_required_components
from pathlib import Path

@pytest.mark.anyio
async def test_validate_environment_all_checks(hass):
    """Test full environment validation success."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_dir", return_value=True), \
         patch("pathlib.Path.touch"), \
         patch("pathlib.Path.unlink"):
        
        success = await validate_environment(hass)
        assert success is True

@pytest.mark.anyio
async def test_check_required_components_missing(hass):
    """Test check_required_components with missing dependencies."""
    hass.config.components = [] # None loaded
    # Should log warning but return True (as per code logic which is non-fatal)
    assert _check_required_components(hass) is True

@pytest.mark.anyio
async def test_setup_integration_preload_failure(hass):
    """Test setup continues even if preload fails."""
    config = {"version": "1.0.0"}
    with patch("custom_components.cronostar.setup.validate_environment", return_value=True), \
         patch("custom_components.cronostar.setup._setup_static_resources", return_value=True), \
         patch("custom_components.cronostar.setup.StorageManager") as mock_sm_cls, \
         patch("custom_components.cronostar.setup.SettingsManager"), \
         patch("custom_components.cronostar.setup.setup_services"), \
         patch("custom_components.cronostar.setup.setup_event_handlers"):
        
        mock_sm = mock_sm_cls.return_value
        mock_sm.list_profiles.return_value = ["f1.json"]
        mock_sm.load_profile_cached.side_effect = Exception("Preload error")
        mock_sm.get_cached_containers = AsyncMock(return_value=[])
        
        success = await async_setup_integration(hass, config)
        assert success is True

@pytest.mark.anyio
async def test_setup_static_resources_http_missing(hass):
    """Test resource setup when http is not loaded."""
    hass.config.components = ["frontend"] # No http
    from custom_components.cronostar.setup import _setup_static_resources
    
    integration = MagicMock()
    integration.version = "1.0.0"
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("homeassistant.loader.async_get_integration", return_value=integration):
        
        success = await _setup_static_resources(hass)
        assert success is True
        # Should skip http registration
