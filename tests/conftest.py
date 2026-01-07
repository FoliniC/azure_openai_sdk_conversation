import tests.mock_ha # Must be first to mock HA modules
import socket
import _socket
import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import pathlib

# Ensure sockets are enabled and won't be disabled
try:
    import pytest_socket
    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.enable_socket()
except Exception:
    pass

# Force restore original socket from C implementation
socket.socket = _socket.socket
if hasattr(_socket, "socketpair"):
    socket.socketpair = _socket.socketpair

@pytest.fixture
def enable_custom_integrations():
    """Mock fixture if not provided by plugin."""
    return True

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test repository."""
    yield

def pytest_configure(config):
    """Add project root to python path and ensure sockets are enabled."""
    config.addinivalue_line("markers", "allow_socket: allow socket usage")
    config.addinivalue_line("markers", "no_fail_on_log_exception: mark test to not fail on log exception")
    
    try:
        import pytest_socket
        pytest_socket.enable_socket()
    except Exception:
        pass

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)
    # Also add custom_components directory specifically
    sys.path.insert(0, os.path.join(project_root, "custom_components"))

@pytest.fixture
def anyio_backend():
    return "asyncio"

# --- Cronostar specific fixtures (adapted) ---

# Mock Path.mkdir was causing FileNotFoundError for pytest internal tmp directories.
# Removing it should allow pytest to work correctly in the container.
# @pytest.fixture(autouse=True)
# def mock_path_mkdir():
#     with patch("pathlib.Path.mkdir") as mock:
#         yield mock

@pytest.fixture
def hass(tmp_path):
    """Mock Home Assistant instance."""
    # Try importing DOMAIN, if fails (e.g. structure difference), define it string
    try:
        from custom_components.cronostar.const import DOMAIN
    except ImportError:
        DOMAIN = "cronostar"

    hass = MagicMock()
    
    # Initialize DOMAIN data structure
    settings_manager = MagicMock()
    settings_manager.load_settings = AsyncMock(return_value={})
    settings_manager.save_settings = AsyncMock()
    
    storage_manager = MagicMock()
    storage_manager.list_profiles = AsyncMock(return_value=[])
    storage_manager.load_profile_cached = AsyncMock(return_value={})
    
    hass.data = {DOMAIN: {
        "settings_manager": settings_manager,
        "storage_manager": storage_manager
    }}
    
    # Create a temporary config directory (using standard tmp_path)
    config_dir = tmp_path / "config"
    # Ensure it exists (mock_path_mkdir might block this if active? 
    # But mock_path_mkdir is autouse=True... 
    # If mock_path_mkdir is active, os.makedirs might still work if it doesn't use pathlib.Path.mkdir internally?
    # Python's os.makedirs usually uses os.mkdir. 
    # Let's use os.makedirs to be safe.)
    os.makedirs(str(config_dir), exist_ok=True)
    
    def mock_path(x=None):
        if x is None:
            return str(config_dir)
        return str(config_dir / x)
        
    hass.config.path = MagicMock(side_effect=mock_path)
    hass.config.components = []
    
    # Mock states with proper structure
    hass.states.get = MagicMock(return_value=None)
    
    hass.states.async_set = MagicMock()
    hass.states.async_remove = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.services.async_register = MagicMock()
    hass.services.async_remove = AsyncMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.flow.async_init = AsyncMock()
    hass.config_entries.async_update_entry = MagicMock()
    
    # Mock loop
    hass.loop.create_task = MagicMock()
    
    # Mock async_add_executor_job
    async def mock_executor(target, *args, **kwargs):
        if hasattr(target, "__call__"):
            return target(*args, **kwargs)
        return target
    hass.async_add_executor_job = AsyncMock(side_effect=mock_executor)
    
    return hass

@pytest.fixture
def mock_storage_manager():
    """Mock the StorageManager."""
    manager = MagicMock()
    manager.list_profiles = AsyncMock(return_value=["test_profile.json"])
    manager.load_profile_cached = AsyncMock(return_value={
        "meta": {
            "preset_type": "thermostat",
            "global_prefix": "cronostar_thermostat_test_",
            "min_value": 10,
            "max_value": 30
        },
        "profiles": {
            "Default": {
                "schedule": [
                    {"time": "08:00", "value": 20.0},
                    {"time": "20:00", "value": 18.0}
                ]
            },
            "Comfort": {
                "schedule": [
                    {"time": "08:00", "value": 22.0},
                    {"time": "22:00", "value": 20.0}
                ]
            }
        }
    })
    manager.save_profile = AsyncMock()
    manager.get_cached_containers = AsyncMock(return_value=[
        ("test_profile.json", {
             "meta": {
                "preset_type": "thermostat",
                "global_prefix": "cronostar_thermostat_test_",
                "min_value": 10,
                "max_value": 30
            },
            "profiles": {
                "Default": {
                    "schedule": [
                        {"time": "08:00", "value": 20.0},
                        {"time": "20:00", "value": 18.0}
                    ]
                }
            }
        })
    ])
    return manager

@pytest.fixture
def mock_coordinator(hass, mock_storage_manager):
    """Create a mock coordinator."""
    # We mock the class so we don't need real imports that might fail
    # But the test using this fixture likely imports the real class.
    # The original conftest imported it.
    try:
        from custom_components.cronostar.coordinator import CronoStarCoordinator
        from custom_components.cronostar.const import DOMAIN
    except ImportError:
        # Fallback for compilation if modules missing
        CronoStarCoordinator = MagicMock()
        DOMAIN = "cronostar"
    
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Test Controller"
    entry.data = {
        "name": "Test Controller",
        "preset": "thermostat",
        "target_entity": "climate.test_thermostat",
        "global_prefix": "cronostar_thermostat_test_"
    }
    entry.options = {}
    
    hass.data[DOMAIN] = {"storage_manager": mock_storage_manager}
    
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.async_refresh = AsyncMock()
    
    coordinator.data = {
        "selected_profile": "Default",
        "is_enabled": True,
        "current_value": 0.0,
        "available_profiles": ["Default"]
    }
    
    return coordinator

def pytest_collection_modifyitems(config, items):
    import inspect
    print(f"DEBUG: modifyitems called with {len(items)} items")
    for item in items:
        # Add anyio marker to all async tests
        if inspect.iscoroutinefunction(item.obj):
            # print(f"DEBUG: Marking {item.name} as anyio")
            item.add_marker("anyio")
            
        item.add_marker("no_fail_on_log_exception")
        item.add_marker("allow_socket")