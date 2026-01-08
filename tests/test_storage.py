"""Test Storage Manager."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import json
import sys
from pathlib import Path
from custom_components.cronostar.storage.storage_manager import StorageManager

@pytest.mark.anyio
async def test_storage_list_profiles(hass):
    """Test listing profiles."""
    with patch("pathlib.Path.glob") as mock_glob:
        p1 = MagicMock(spec=Path)
        p1.name = "cronostar_test.json"
        mock_glob.return_value = [p1]
        
        manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
        manager.load_profile_cached = AsyncMock(return_value={"meta": {"preset_type": "thermostat"}})
        
        files = await manager.list_profiles()
        assert "cronostar_test.json" in files

@pytest.mark.anyio
async def test_storage_load_profile(hass):
    """Test loading profile."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    mock_data = '{"meta": {"test": 1}, "profiles": {}}'
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value=mock_data):
        
        data = await manager.load_profile_cached("test.json")
        assert data["meta"]["test"] == 1

@pytest.mark.anyio
async def test_storage_save_profile(hass):
    """Test saving profile."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._load_container = AsyncMock(return_value={"profiles": {}})
    
    with patch("pathlib.Path.write_text") as mock_write:
        success = await manager.save_profile(
            "NewProfile", 
            "thermostat", 
            {"schedule": []}, 
            {"meta": {}}, 
            "prefix"
        )
        assert success is True
        assert mock_write.called

@pytest.mark.anyio
async def test_storage_delete_profile(hass):
    """Test deleting profile."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    manager._load_container = AsyncMock(return_value={
        "profiles": {"P1": {}, "P2": {}}
    })
    
    with patch("pathlib.Path.write_text") as mock_write:
        success = await manager.delete_profile("P1", "thermostat", "prefix")
        assert success is True
        assert mock_write.called

@pytest.mark.anyio
async def test_storage_backups(hass):
    """Test backup creation."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"), enable_backups=True)
    filepath = MagicMock(spec=Path)
    filepath.exists.return_value = True
    filepath.stem = "test"
    filepath.suffix = ".json"
    filepath.parent = Path(hass.config.path("cronostar/profiles"))
    
    with patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_bytes"), \
         patch("pathlib.Path.read_bytes"):
        
        from homeassistant.util import dt as dt_util
        dt_util.now.return_value = MagicMock()
        dt_util.now.return_value.strftime.return_value = "20230101_120000"
        
        await manager._create_backup(filepath)

@pytest.mark.anyio
async def test_storage_cleanup_old_backups(hass):
    """Test cleanup of old backups."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.glob") as mock_glob:
        
        backups = []
        for i in range(15):
            b = MagicMock(spec=Path)
            b.stat.return_value.st_mtime = i
            b.name = f"test_backup_{i}.json"
            backups.append(b)
        
        mock_glob.return_value = backups
        
        await manager._cleanup_old_backups("test")
        
        delete_calls = [b.unlink.called for b in backups]
        assert sum(delete_calls) == 5

@pytest.mark.anyio
async def test_load_all_profiles(hass):
    """Test load_all_profiles."""
    manager = StorageManager(hass, hass.config.path("cronostar/profiles"))
    
    with patch("pathlib.Path.glob") as mock_glob:
        p1 = MagicMock(spec=Path)
        p1.name = "cronostar_test.json"
        mock_glob.return_value = [p1]
        
        manager._load_container = AsyncMock(return_value={"meta": {}})
        
        # Mock FileChecker module manually to avoid import issues
        mock_checker_mod = MagicMock()
        mock_checker_cls = mock_checker_mod.FileChecker
        mock_checker = mock_checker_cls.return_value
        mock_checker._validate_profile_file = AsyncMock(return_value={"valid": True})
        
        with patch.dict(sys.modules, {"custom_components.cronostar.deep_checks.file_checker": mock_checker_mod}):
            result = await manager.load_all_profiles()
            assert "cronostar_test.json" in result
            assert result["cronostar_test.json"]["validation_results"]["valid"] is True
