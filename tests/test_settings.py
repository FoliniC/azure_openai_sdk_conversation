"""Test Settings Manager."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import json
from custom_components.cronostar.storage.settings_manager import SettingsManager, DEFAULT_SETTINGS

@pytest.fixture
def mock_hass(tmp_path):
    hass = MagicMock()
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    def mock_path(x=None):
        if x is None:
            return str(config_dir)
        return str(config_dir / x)
        
    hass.config.path = MagicMock(side_effect=mock_path)
    async def mock_executor(target, *args, **kwargs):
        if hasattr(target, "__call__"):
            return target(*args, **kwargs)
        return target
    hass.async_add_executor_job = AsyncMock(side_effect=mock_executor)
    return hass

@pytest.mark.anyio
async def test_load_settings_default(mock_hass):
    """Test loading settings when file doesn't exist."""
    with patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):
        
        manager = SettingsManager(mock_hass, mock_hass.config.path("cronostar"))
        settings = await manager.load_settings()
        assert settings == DEFAULT_SETTINGS

@pytest.mark.anyio
async def test_load_settings_existing(mock_hass):
    """Test loading existing settings."""
    custom_settings = {"keyboard": {"ctrl": {"horizontal": 10}}}
    mock_data = json.dumps(custom_settings)
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value=mock_data), \
         patch("pathlib.Path.mkdir"):
        
        manager = SettingsManager(mock_hass, mock_hass.config.path("cronostar"))
        settings = await manager.load_settings()
        assert settings["keyboard"]["ctrl"]["horizontal"] == 10
        # Check merge
        assert settings["keyboard"]["shift"]["horizontal"] == 30

@pytest.mark.anyio
async def test_save_settings(mock_hass):
    """Test saving settings."""
    manager = SettingsManager(mock_hass, mock_hass.config.path("cronostar"))
    
    with patch("pathlib.Path.write_text") as mock_write, \
         patch("pathlib.Path.mkdir"):
        
        success = await manager.save_settings({"test": 1})
        assert success is True
        assert mock_write.called
