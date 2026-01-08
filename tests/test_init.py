"""Test Component Initialization."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar import async_setup, async_setup_entry, async_unload_entry, async_reload_entry
from custom_components.cronostar.const import DOMAIN

@pytest.mark.anyio
async def test_async_setup(hass):
    """Test YAML setup."""
    with patch("custom_components.cronostar.async_setup_integration", return_value=True):
        success = await async_setup(hass, {})
        assert success is True
        assert hass.data[DOMAIN]["_global_setup_done"] is True

@pytest.mark.anyio
async def test_async_setup_entry_global(hass):
    """Test global component setup entry."""
    entry = MagicMock()
    entry.data = {"component_installed": True}
    entry.version = "1.0.0"
    entry.options = {}
    
    with patch("custom_components.cronostar.async_setup_integration", return_value=True):
        success = await async_setup_entry(hass, entry)
        assert success is True

@pytest.mark.anyio
async def test_async_setup_entry_global_failure(hass):
    """Test global component setup entry failure."""
    entry = MagicMock()
    entry.data = {"component_installed": True}
    entry.options = {}
    
    # Global setup fails
    with patch("custom_components.cronostar.async_setup_integration", return_value=False):
        success = await async_setup_entry(hass, entry)
        assert success is False

@pytest.mark.anyio
async def test_async_setup_entry_controller(hass):
    """Test controller entry setup."""
    entry = MagicMock()
    entry.data = {"target_entity": "climate.test"}
    entry.title = "Test"
    entry.entry_id = "test_entry"
    entry.options = {}
    
    # Pre-mark global setup as done
    hass.data[DOMAIN] = {"_global_setup_done": True}
    
    # Ensure it's an AsyncMock
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    with patch("custom_components.cronostar.CronoStarCoordinator") as mock_coord_cls:
        mock_coord = mock_coord_cls.return_value
        mock_coord.async_initialize = AsyncMock()
        mock_coord.async_config_entry_first_refresh = AsyncMock()
        
        success = await async_setup_entry(hass, entry)
        assert success is True
        assert hasattr(entry, 'runtime_data')

@pytest.mark.anyio
async def test_async_setup_entry_controller_lazy_init(hass):
    """Test controller entry setup triggers lazy init if global missing."""
    entry = MagicMock()
    entry.data = {"target_entity": "climate.test"}
    entry.title = "Test"
    entry.options = {}
    
    hass.data[DOMAIN] = {} # Global missing
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    with patch("custom_components.cronostar.async_setup_integration", return_value=True):
        with patch("custom_components.cronostar.CronoStarCoordinator") as mock_coord_cls:
            mock_coord = mock_coord_cls.return_value
            mock_coord.async_initialize = AsyncMock()
            mock_coord.async_config_entry_first_refresh = AsyncMock()
            
            success = await async_setup_entry(hass, entry)
            assert success is True
            assert hass.data[DOMAIN]["_global_setup_done"] is True

@pytest.mark.anyio
async def test_async_unload_entry(hass):
    """Test unloading entry."""
    entry = MagicMock()
    entry.data = {"component_installed": True}
    entry.title = "Global"
    
    hass.data[DOMAIN] = {"_global_setup_done": True}
    
    # Mock unload platforms
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    
    with patch("custom_components.cronostar.setup.services.async_unload_services", return_value=AsyncMock()):
        success = await async_unload_entry(hass, entry)
        assert success is True
        assert "_global_setup_done" not in hass.data[DOMAIN]

@pytest.mark.anyio
async def test_async_reload_entry(hass):
    """Test reloading entry."""
    entry = MagicMock()
    entry.data = {"component_installed": True}
    
    with patch("custom_components.cronostar.async_unload_entry", return_value=True) as mock_unload, \
         patch("custom_components.cronostar.async_setup_entry", return_value=True) as mock_setup:
        
        await async_reload_entry(hass, entry)
        assert mock_unload.called
        assert mock_setup.called