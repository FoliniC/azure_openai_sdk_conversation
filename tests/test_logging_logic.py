"""Tests targeting logging and rare logic paths."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import json
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.storage.storage_manager import StorageManager
from custom_components.cronostar.const import DOMAIN, CONF_TARGET_ENTITY, CONF_LOGGING_ENABLED
from pathlib import Path

@pytest.mark.anyio
async def test_coordinator_logging_branches(hass):
    """Trigger various logging branches in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test", CONF_LOGGING_ENABLED: True}
    entry.options = {}
    
    hass.data[DOMAIN] = {"logging_enabled": True}
    coordinator = CronoStarCoordinator(hass, entry)
    
    mock_hass_state = MagicMock()
    mock_hass_state.state = "20"
    hass.states.get.return_value = mock_hass_state
    await coordinator._async_update_data()
    
    hass.states.get.return_value = None
    await coordinator._async_update_data()

@pytest.mark.anyio
async def test_coordinator_interpolate_debug(hass):
    """Trigger debug logging in interpolation."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True
    
    schedule = [{"time": "invalid", "value": 20}]
    coordinator._interpolate_schedule(schedule)

@pytest.mark.anyio
async def test_storage_backups_enabled_logs(hass):
    """Trigger logging when backups enabled."""
    with patch("pathlib.Path.mkdir"):
        manager = StorageManager(hass, hass.config.path("cronostar/profiles"), enable_backups=True)

@pytest.mark.anyio
async def test_storage_load_cache_lock(hass):
    """Hit the cache age logic in load_profile_cached."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    from datetime import datetime
    
    manager._cache["f1.json"] = {"data": 1}
    manager._cache_mtimes["f1.json"] = 1000 # Use mtimes instead of timestamps
    
    with patch("custom_components.cronostar.storage.storage_manager.os.path.getmtime", return_value=500):
        await manager.load_profile_cached("f1.json")
    
    with patch("pathlib.Path.exists", return_value=False):
        await manager.load_profile_cached("f1.json", force_reload=True)

@pytest.mark.anyio
async def test_storage_list_profiles_load_fail(hass):
    """Hit line 249-251 in list_profiles."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    p1 = MagicMock(spec=Path)
    p1.name = "cronostar_f1.json"
    with patch("pathlib.Path.glob", return_value=[p1]):
        manager.load_profile_cached = AsyncMock(return_value=None)
        await manager.list_profiles(preset_type="thermostat")

@pytest.mark.anyio
async def test_storage_json_errors(hass):
    """Hit various JSON and IO error paths."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    path = Path("test.json")
    
    # JSON decode error
    with patch("pathlib.Path.exists", return_value=True):
        hass.async_add_executor_job.side_effect = json.JSONDecodeError("err", "doc", 0)
        await manager._load_container(path)
        
    # Other error
    hass.async_add_executor_job.side_effect = Exception("IO error")
    await manager._load_container(path)
    
    # Write error - raises
    with pytest.raises(Exception):
        await manager._write_json(path, {})
    
    # Backup error - logs but continues
    hass.async_add_executor_job.side_effect = Exception("Backup fail")
    await manager._create_backup(path)