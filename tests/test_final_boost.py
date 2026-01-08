"""Test final coverage boost."""
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import pytest
from homeassistant.data_entry_flow import FlowResultType
from custom_components.cronostar.const import DOMAIN, CONF_LOGGING_ENABLED
from custom_components.cronostar.storage.storage_manager import StorageManager

@pytest.mark.anyio
async def test_config_flow_install_component_form(hass):
    """Test showing install component form."""
    from custom_components.cronostar.config_flow import CronoStarConfigFlow
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_install_component()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "install_component"

@pytest.mark.anyio
async def test_options_flow_init_form(hass):
    """Test options flow init form."""
    from custom_components.cronostar.config_flow import CronoStarOptionsFlow
    entry = MagicMock()
    entry.options = {CONF_LOGGING_ENABLED: True}
    entry.data = {}
    
    flow = CronoStarOptionsFlow(entry)
    flow.hass = hass
    
    result = await flow.async_step_init()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

@pytest.mark.anyio
async def test_storage_manager_errors(hass):
    """Test storage manager error handling."""
    sm = StorageManager(hass, "test_path")
    
    # List profiles error
    with patch("os.listdir", side_effect=OSError("Boom")):
        files = await sm.list_profiles()
        assert files == []
        
    # Load profile error (file read)
    with patch("pathlib.Path.read_text", side_effect=OSError("Read error")):
        data = await sm.load_profile_cached("test.json", force_reload=True)
        assert data == {}

    # Save profile error
    with patch("pathlib.Path.write_text", side_effect=OSError("Write error")):
        success = await sm.save_profile("profile", "thermostat", {}, {}, "prefix")
        assert success is False
        
    # Delete profile error
    with patch("os.remove", side_effect=OSError("Delete error")):
        success = await sm.delete_profile("profile", "thermostat", "prefix")
        assert success is False

    # Ensure directories error
    with patch("pathlib.Path.mkdir", side_effect=OSError("Mkdir error")):
        # Should catch or raise? Code in __init__ doesn't seem to wrap in try/except.
        # If it raises, we should expect it.
        with pytest.raises(OSError):
             StorageManager(hass, "test_path")
