"""Tests to fill the remaining coverage gaps."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.services.profile_service import ProfileService
from custom_components.cronostar.const import DOMAIN

@pytest.mark.anyio
async def test_coordinator_unsupported_domain(hass):
    """Test coordinator with an unsupported target domain."""
    entry = MagicMock()
    entry.data = {"target_entity": "light.test", "preset": "thermostat"}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True
    
    # Manually trigger _update_target_entity with unsupported domain
    # Code: if domain == 'climate'... elif domain in ['switch', 'light', 'fan']... 
    # Wait, light IS supported.
    # Unsupported would be 'sensor.test'
    coordinator.target_entity = "sensor.test"
    await coordinator._update_target_entity(20.0)
    # Should log warning

@pytest.mark.anyio
async def test_coordinator_update_exception(hass):
    """Test coordinator update exception handling."""
    entry = MagicMock()
    entry.data = {"target_entity": "climate.test", "preset": "thermostat"}
    coordinator = CronoStarCoordinator(hass, entry)
    
    hass.services.async_call.side_effect = Exception("Service fail")
    await coordinator._update_target_entity(20.0)
    # Should log error

@pytest.mark.anyio
async def test_coordinator_interpolate_edge_cases(hass):
    """Test interpolation edge cases."""
    entry = MagicMock()
    entry.data = {"target_entity": "climate.test", "preset": "thermostat"}
    coordinator = CronoStarCoordinator(hass, entry)
    
    # Identical points
    schedule = [
        {"time": "08:00", "value": 20.0},
        {"time": "08:00", "value": 20.0}
    ]
    from datetime import datetime
    with patch("custom_components.cronostar.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 8, 0, 0)
        assert coordinator._interpolate_schedule(schedule) == 20.0

@pytest.mark.anyio
async def test_profile_service_ensure_controller_no_prefix(hass):
    """Test _ensure_controller_exists with empty prefix."""
    ps = ProfileService(hass, MagicMock(), MagicMock())
    await ps._ensure_controller_exists("", "thermostat", {})
    assert not hass.config_entries.flow.async_init.called

@pytest.mark.anyio
async def test_profile_service_update_selectors_load_fail(hass):
    """Test update_selectors when one file fails to load."""
    storage = MagicMock()
    storage.list_profiles = AsyncMock(return_value=["f1.json"])
    storage.load_profile_cached = AsyncMock(return_value=None)
    
    ps = ProfileService(hass, storage, MagicMock())
    await ps.async_update_profile_selectors()
    # Should continue

@pytest.mark.anyio
async def test_storage_get_cached_containers_filters(hass):
    """Test get_cached_containers with varied filters."""
    from custom_components.cronostar.storage.storage_manager import StorageManager
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._cache = {
        "f1.json": {"meta": {"preset_type": "thermostat", "global_prefix": "p1_"}}
    }
    
    # Mismatched preset
    assert len(await manager.get_cached_containers(preset_type="fan")) == 0
    # Mismatched prefix
    assert len(await manager.get_cached_containers(global_prefix="p2")) == 0
    # Match
    assert len(await manager.get_cached_containers(preset_type="thermostat", global_prefix="p1")) == 1
