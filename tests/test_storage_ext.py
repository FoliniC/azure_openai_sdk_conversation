"""Extended tests for CronoStar Storage Manager."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.cronostar.storage.storage_manager import StorageManager


@pytest.mark.anyio
async def test_delete_profile_not_found(hass):
    """Test deleting a non-existent profile."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._load_container = AsyncMock(return_value={"profiles": {"P1": {}}})

    success = await manager.delete_profile("P2", "thermostat", "prefix")
    assert success is False


@pytest.mark.anyio
async def test_delete_profile_container_not_found(hass):
    """Test deleting when container doesn't exist."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._load_container = AsyncMock(return_value={})

    success = await manager.delete_profile("P1", "thermostat", "prefix")
    assert success is False


@pytest.mark.anyio
async def test_list_profiles_filters(hass):
    """Test list_profiles with preset and prefix filters."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))

    p1 = MagicMock(spec=Path)
    p1.name = "cronostar_t1.json"
    p2 = MagicMock(spec=Path)
    p2.name = "cronostar_t2.json"

    with patch("pathlib.Path.glob", return_value=[p1, p2]):
        # Mock load_profile_cached to return different meta
        manager.load_profile_cached = AsyncMock(
            side_effect=[
                {"meta": {"preset_type": "thermostat", "global_prefix": "p1_"}},
                {"meta": {"preset_type": "ev_charging", "global_prefix": "p2_"}},
            ]
        )

        # Filter by preset
        files = await manager.list_profiles(preset_type="thermostat")
        assert len(files) == 1
        assert files[0] == "cronostar_t1.json"

        # Filter by prefix
        manager.load_profile_cached.side_effect = [
            {"meta": {"preset_type": "thermostat", "global_prefix": "p1_"}},
            {"meta": {"preset_type": "ev_charging", "global_prefix": "p2_"}},
        ]
        files = await manager.list_profiles(prefix="p2_")
        assert len(files) == 1
        assert files[0] == "cronostar_t2.json"


@pytest.mark.anyio
async def test_get_profile_list(hass):
    """Test get_profile_list."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager.load_profile_cached = AsyncMock(
        return_value={"profiles": {"P1": {}, "P2": {}}}
    )

    profiles = await manager.get_profile_list("thermostat", "prefix")
    assert "P1" in profiles
    assert "P2" in profiles


@pytest.mark.anyio
async def test_get_cached_containers(hass):
    """Test get_cached_containers filtering."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._cache = {
        "f1.json": {"meta": {"preset_type": "thermostat", "global_prefix": "p1_"}},
        "f2.json": {"meta": {"preset_type": "ev_charging", "global_prefix": "p2_"}},
    }

    res = await manager.get_cached_containers(preset_type="thermostat")
    assert len(res) == 1
    assert res[0][0] == "f1.json"


@pytest.mark.anyio
async def test_write_json_error(hass):
    """Test error handling in _write_json."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    hass.async_add_executor_job.side_effect = Exception("Write error")

    with pytest.raises(Exception):
        await manager._write_json(Path("test.json"), {})


@pytest.mark.anyio
async def test_load_container_json_error(hass):
    """Test error handling in _load_container with invalid JSON."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    with patch("pathlib.Path.exists", return_value=True):
        hass.async_add_executor_job.return_value = "invalid json"
        res = await manager._load_container(Path("test.json"))
        assert res == {}
