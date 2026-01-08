"""
Additional tests to reach 90% coverage in all files.
"""
import pytest
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant, CoreState
from custom_components.cronostar.const import DOMAIN, CONF_LOGGING_ENABLED
from custom_components.cronostar.config_flow import CronoStarConfigFlow, CronoStarOptionsFlow
from custom_components.cronostar.select import async_setup_entry as async_setup_select, CronoStarProfileSelect
from custom_components.cronostar.sensor import async_setup_entry as async_setup_sensor, CronoStarCurrentSensor
from custom_components.cronostar.switch import async_setup_entry as async_setup_switch, CronoStarEnabledSwitch
from custom_components.cronostar.setup import async_setup_integration, _setup_static_resources, _preload_profile_cache
from custom_components.cronostar.setup.events import setup_event_handlers
from custom_components.cronostar.setup.validators import validate_environment, _check_config_directory, _check_profiles_directory
from custom_components.cronostar.storage.settings_manager import SettingsManager

@pytest.mark.anyio
async def test_config_flow_aborts(hass):
    """Test config flow abort cases."""
    # Test single instance abort
    entry = MagicMock()
    entry.data = {"component_installed": True}
    
    flow = CronoStarConfigFlow()
    flow.hass = hass
    flow._async_current_entries = MagicMock(return_value=[entry])
    
    result = await flow.async_step_user()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    # Test create_controller abort on no input
    result = await flow.async_step_create_controller(user_input=None)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_input"

@pytest.mark.anyio
async def test_config_flow_install_success(hass):
    """Test successful install step."""
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_install_component(user_input={CONF_LOGGING_ENABLED: True})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["component_installed"] is True
    assert result["data"][CONF_LOGGING_ENABLED] is True

@pytest.mark.anyio
async def test_platforms_setup_entry(hass):
    """Test async_setup_entry for select, sensor, and switch."""
    mock_coordinator = MagicMock()
    mock_coordinator.prefix = "test_"
    mock_coordinator.name = "Test"
    mock_coordinator.entry.entry_id = "test_entry"
    mock_coordinator.hass = hass
    mock_coordinator.preset_type = "thermostat"
    
    entry = MagicMock()
    entry.runtime_data = mock_coordinator
    
    async_add_entities = MagicMock()
    
    # Select
    await async_setup_select(hass, entry, async_add_entities)
    assert async_add_entities.called
    
    # Sensor
    async_add_entities.reset_mock()
    await async_setup_sensor(hass, entry, async_add_entities)
    assert async_add_entities.called
    
    # Switch
    async_add_entities.reset_mock()
    await async_setup_switch(hass, entry, async_add_entities)
    assert async_add_entities.called

@pytest.mark.anyio
async def test_entities_logging_and_availability(hass):
    """Test logging calls and availability logic in entities."""
    mock_coordinator = MagicMock()
    mock_coordinator.prefix = "test_"
    mock_coordinator.name = "Test"
    mock_coordinator.entry.entry_id = "test_entry"
    mock_coordinator.hass = hass
    mock_coordinator.logging_enabled = True
    mock_coordinator.target_entity = "climate.test"
    mock_coordinator.data = {"available_profiles": ["A", "B"], "selected_profile": "A", "is_enabled": True, "current_value": 20.5}
    mock_coordinator.set_profile = AsyncMock()
    mock_coordinator.set_enabled = AsyncMock()
    
    # Test availability - Mock states
    hass.states.get = MagicMock(return_value=MagicMock(state="online"))
    
    # Select
    select = CronoStarProfileSelect(mock_coordinator)
    assert select.available is True
    await select.async_select_option("B")
    mock_coordinator.set_profile.assert_called_with("B")
    
    # Sensor
    sensor = CronoStarCurrentSensor(mock_coordinator)
    assert sensor.available is True
    assert sensor.native_value == 20.5
    
    # Switch
    switch = CronoStarEnabledSwitch(mock_coordinator)
    assert switch.available is True
    await switch.async_turn_on()
    mock_coordinator.set_enabled.assert_called_with(True)
    await switch.async_turn_off()
    mock_coordinator.set_enabled.assert_called_with(False)
    
    # Test unavailable
    hass.states.get = MagicMock(return_value=MagicMock(state="unavailable"))
    assert select.available is False
    assert sensor.available is False
    assert switch.available is False

def test_entity_init_exception_handling():
    """Test exception handling in entity __init__ for model_name."""
    mock_coordinator = MagicMock()
    mock_coordinator.prefix = "test_"
    mock_coordinator.name = "Test"
    mock_coordinator.entry.entry_id = "test_entry"
    # Make preset_type return something that will fail in .replace()
    mock_coordinator.preset_type = 123
    
    # For Sensor
    sensor = CronoStarCurrentSensor(mock_coordinator)
    assert sensor.device_info["model"] == "Controller"

    # For Select
    select = CronoStarProfileSelect(mock_coordinator)
    assert select.device_info["model"] == "Controller"

@pytest.mark.anyio
async def test_setup_integration_failures(hass):
    """Test failure paths in async_setup_integration."""
    with patch("custom_components.cronostar.setup.validate_environment", return_value=False):
        assert await async_setup_integration(hass, {}) is False

    with patch("custom_components.cronostar.setup.validate_environment", return_value=True), \
         patch("custom_components.cronostar.setup._setup_static_resources", return_value=False):
        assert await async_setup_integration(hass, {}) is False

@pytest.mark.anyio
async def test_setup_events_startup(hass):
    """Test event handlers startup logic."""
    mock_storage = AsyncMock()
    mock_storage.list_profiles = AsyncMock(return_value=["file1"])
    mock_storage.load_profile_cached = AsyncMock(side_effect=Exception("load error"))
    
    hass.state = CoreState.running
    hass.data["cronostar"] = {"profile_service": AsyncMock()}
    hass.async_create_task = MagicMock()
    
    await setup_event_handlers(hass, mock_storage)
    
    # Get the coro from call
    coro = hass.async_create_task.call_args[0][0]
    try:
        await coro
    except Exception:
        pass
    
    mock_storage.load_profile_cached.assert_called_with("file1", force_reload=False)
    assert hass.data["cronostar"]["profile_service"].async_update_profile_selectors.called

@pytest.mark.anyio
async def test_validators_exceptions(hass):
    """Test exception paths in validators."""
    with patch("custom_components.cronostar.setup.validators.Path.exists", side_effect=Exception("fs error")):
        assert _check_config_directory(hass) is False
        assert _check_profiles_directory(hass) is False

    with patch("custom_components.cronostar.setup.validators.Path.is_dir", return_value=False):
        # Trigger "Profiles path is not a directory"
        with patch("custom_components.cronostar.setup.validators.Path.exists", return_value=True):
            assert _check_profiles_directory(hass) is False

    with patch("custom_components.cronostar.setup.validators.Path.touch", side_effect=Exception("perm error")):
        # Trigger "Profiles directory not writable"
        with patch("custom_components.cronostar.setup.validators.Path.exists", return_value=True), \
             patch("custom_components.cronostar.setup.validators.Path.is_dir", return_value=True):
            assert _check_profiles_directory(hass) is False

@pytest.mark.anyio
async def test_settings_manager_exceptions(hass, tmp_path):
    """Test exception paths in SettingsManager."""
    sm = SettingsManager(hass, tmp_path)
    
    # Force read failure
    with patch("pathlib.Path.read_text", side_effect=Exception("read error")):
        # Create file so it tries to read
        (tmp_path / "settings.json").touch()
        settings = await sm.load_settings()
        assert settings["keyboard"]["ctrl"]["horizontal"] == 1 # Default
        
    # Force save failure
    with patch("pathlib.Path.write_text", side_effect=Exception("write error")):
        assert await sm.save_settings({"test": 1}) is False

@pytest.mark.anyio
async def test_setup_static_resources_edge_cases(hass):
    """Test edge cases in _setup_static_resources."""
    # Test Path not found
    with patch("custom_components.cronostar.setup.Path.exists", return_value=False):
        assert await _setup_static_resources(hass) is False
        
    # Test HTTP not loaded
    hass.config.components = []
    with patch("custom_components.cronostar.setup.Path.exists", return_value=True):
        # Should return True because it just skips
        assert await _setup_static_resources(hass) is True

    # Test Exception in registration
    hass.config.components = ["http"]
    with patch("custom_components.cronostar.setup.Path.exists", return_value=True), \
         patch("custom_components.cronostar.setup.async_get_integration", side_effect=Exception("int error")):
        assert await _setup_static_resources(hass) is False

@pytest.mark.anyio
async def test_preload_profile_cache_inner_error(hass):
    """Test error handling in _preload_profile_cache loop."""
    mock_storage = AsyncMock()
    mock_storage.list_profiles = AsyncMock(return_value=["file1"])
    mock_storage.load_profile_cached = AsyncMock(side_effect=Exception("inner error"))
    mock_storage.get_cached_containers = AsyncMock(return_value=[])
    
    # Should not raise, just log warning
    await _preload_profile_cache(hass, mock_storage)
    assert mock_storage.load_profile_cached.called

@pytest.mark.anyio
async def test_check_profiles_directory_not_a_dir(hass):
    """Test _check_profiles_directory when path exists but is not a directory."""
    with patch("custom_components.cronostar.setup.validators.Path.exists", return_value=True), \
         patch("custom_components.cronostar.setup.validators.Path.is_dir", return_value=False):
        assert _check_profiles_directory(hass) is False
