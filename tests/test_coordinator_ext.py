"""Extended tests for CronoStar Coordinator."""
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import pytest
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.const import DOMAIN, CONF_LOGGING_ENABLED, CONF_TARGET_ENTITY

@pytest.mark.anyio
async def test_coordinator_logging_enabled(hass):
    """Test coordinator initialization with logging enabled."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Test Controller"
    entry.data = {
        CONF_TARGET_ENTITY: "climate.test",
        CONF_LOGGING_ENABLED: True
    }
    entry.options = {}
    
    # Global logging
    hass.data[DOMAIN] = {"logging_enabled": True}
    
    coordinator = CronoStarCoordinator(hass, entry)
    assert coordinator.logging_enabled is True

@pytest.mark.anyio
async def test_coordinator_storage_fallback(hass):
    """Test coordinator storage manager fallback."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Test Controller"
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    entry.options = {}
    
    hass.data[DOMAIN] = {} # No storage manager
    
    with patch("custom_components.cronostar.coordinator.StorageManager") as mock_sm:
        coordinator = CronoStarCoordinator(hass, entry)
        assert mock_sm.called

@pytest.mark.anyio
async def test_async_update_data_target_missing(hass, mock_coordinator):
    """Test _async_update_data when target entity is missing."""
    mock_coordinator.hass.states.get.return_value = None
    
    result = await mock_coordinator._async_update_data()
    assert result["current_value"] == mock_coordinator.current_value

@pytest.mark.anyio
async def test_async_initialize_no_profiles(hass, mock_coordinator, mock_storage_manager):
    """Test async_initialize when no profiles are found."""
    mock_storage_manager.list_profiles.return_value = []
    await mock_coordinator.async_initialize()
    assert mock_coordinator.available_profiles == ["Default"]

@pytest.mark.anyio
async def test_async_initialize_exception(hass, mock_coordinator, mock_storage_manager):
    """Test async_initialize with an exception."""
    mock_storage_manager.list_profiles.side_effect = Exception("Storage error")
    # Should not raise
    await mock_coordinator.async_initialize()

@pytest.mark.anyio
async def test_async_refresh_profiles_no_files(hass, mock_coordinator, mock_storage_manager):
    """Test async_refresh_profiles when no files exist."""
    mock_storage_manager.list_profiles.return_value = []
    await mock_coordinator.async_refresh_profiles()
    # Should maintain current state or default
    assert mock_coordinator.available_profiles == ["Default"]

@pytest.mark.anyio
async def test_async_refresh_profiles_exception(hass, mock_coordinator, mock_storage_manager):
    """Test async_refresh_profiles with an exception."""
    mock_storage_manager.list_profiles.side_effect = Exception("Storage error")
    # Should not raise
    await mock_coordinator.async_refresh_profiles()

@pytest.mark.anyio
async def test_apply_schedule_disabled(hass, mock_coordinator):
    """Test apply_schedule when coordinator is disabled."""
    mock_coordinator.is_enabled = False
    await mock_coordinator.apply_schedule()
    # Should return early before doing anything

@pytest.mark.anyio
async def test_apply_schedule_empty_container(hass, mock_coordinator, mock_storage_manager):
    """Test apply_schedule with empty container."""
    mock_storage_manager.load_profile_cached.return_value = {}
    await mock_coordinator.apply_schedule()

@pytest.mark.anyio
async def test_interpolate_schedule_invalid_points(mock_coordinator):
    """Test interpolation with invalid schedule points."""
    schedule = [
        {"time": "invalid", "value": 20},
        {"time": "08:00", "value": None}
    ]
    val = mock_coordinator._interpolate_schedule(schedule)
    assert val is None

@pytest.mark.anyio
async def test_interpolate_schedule_single_point(mock_coordinator):
    """Test interpolation with a single schedule point."""
    schedule = [{"time": "08:00", "value": 20.0}]
    val = mock_coordinator._interpolate_schedule(schedule)
    assert val == 20.0

def test_get_next_change_empty(mock_coordinator):
    """Test get_next_change with empty schedule."""
    assert mock_coordinator._get_next_change([], 20.0) is None

def test_get_next_change_no_diff(mock_coordinator):
    """Test get_next_change with no different values."""
    schedule = [{"time": "08:00", "value": 20.0}]
    assert mock_coordinator._get_next_change(schedule, 20.0) is None

def test_get_next_change_exception(mock_coordinator):
    """Test get_next_change with exception."""
    # Force exception by passing non-iterable
    assert mock_coordinator._get_next_change(None, 20.0) is None
