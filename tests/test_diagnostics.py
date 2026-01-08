"""Test Diagnostics."""
from unittest.mock import MagicMock, AsyncMock
import pytest
from custom_components.cronostar.diagnostics import async_get_config_entry_diagnostics
from custom_components.cronostar.const import DOMAIN

@pytest.mark.anyio
async def test_diagnostics(hass):
    """Test diagnostics output."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.version = 1
    entry.domain = DOMAIN
    entry.title = "Test Entry"
    entry.data = {"test": "data"}
    entry.options = {"test": "options"}
    
    # Mock runtime_data (coordinator)
    coordinator = MagicMock()
    coordinator.name = "Test Coord"
    coordinator.preset = "thermostat"
    coordinator.target_entity = "climate.test"
    coordinator.selected_profile = "Default"
    coordinator.is_enabled = True
    coordinator.current_value = 20.0
    coordinator.available_profiles = ["Default"]
    entry.runtime_data = coordinator
    
    hass.data[DOMAIN] = {"_global_setup_done": True, "version": "1.0.0"}
    
    result = await async_get_config_entry_diagnostics(hass, entry)
    
    assert result["entry"]["entry_id"] == "test_entry"
    assert result["controller_state"]["name"] == "Test Coord"
    assert result["component_status"]["global_setup_done"] is True
