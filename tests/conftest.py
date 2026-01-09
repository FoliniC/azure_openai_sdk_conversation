"""Global test configuration for anyio-based tests."""

import os
import sys

# -----------------------------------------------------------------------------
# 1. Path Setup (MUST be first)
# -----------------------------------------------------------------------------
# Add the 'tests' directory itself so we can import 'mock_ha' as a module if needed
sys.path.insert(0, os.path.dirname(__file__))

# Add the project root (up one level from 'tests') so we can import 'custom_components'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "custom_components"))

# -----------------------------------------------------------------------------
# 2. Imports (Now safe to import local modules)
# -----------------------------------------------------------------------------
import _socket  # noqa: E402
import socket  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

# -----------------------------------------------------------------------------
# 3. Socket Patching
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 4. Fixtures & Configuration
# -----------------------------------------------------------------------------


def pytest_configure(config):
    """Add markers and ensure sockets are enabled."""
    config.addinivalue_line("markers", "allow_socket: allow socket usage")
    config.addinivalue_line(
        "markers", "no_fail_on_log_exception: mark test to not fail on log exception"
    )

    try:
        import pytest_socket

        pytest_socket.enable_socket()
    except Exception:
        pass


@pytest.fixture(scope="session")
def anyio_backend():
    """Select asyncio as the backend for anyio tests."""
    return "asyncio"


@pytest.fixture
def enable_custom_integrations():
    """Mock fixture if not provided by plugin."""
    return True


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test repository."""
    yield


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms to be loaded."""
    return ["conversation"]


@pytest.fixture(autouse=True)
def patch_mcp_manager():
    """Ensure MCPManager.start is always an AsyncMock to avoid runtime warnings."""
    # This single fixture handles the global patching for MCPManager
    with patch(
        "custom_components.azure_openai_sdk_conversation.context.mcp_manager.MCPManager"
    ) as MockMCP:
        mock_instance = MockMCP.return_value
        mock_instance.start = AsyncMock(return_value=None)
        mock_instance.stop = AsyncMock(return_value=None)
        mock_instance.get_tools = AsyncMock(return_value=[])
        mock_instance.is_new_conversation = MagicMock(return_value=True)
        mock_instance.build_initial_prompt = MagicMock(
            return_value="Mock Initial Prompt"
        )
        mock_instance.build_delta_prompt = MagicMock(return_value="Mock Delta Prompt")
        yield mock_instance


@pytest.fixture
def hass(tmp_path):
    """Mock Home Assistant instance."""
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

    hass.data = {
        DOMAIN: {
            "settings_manager": settings_manager,
            "storage_manager": storage_manager,
        }
    }

    # Create a temporary config directory
    config_dir = tmp_path / "config"
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

    # ---------------------------------------------------------
    # ✅ FIX: Mock loop.create_task inside the fixture function
    # ---------------------------------------------------------
    def mock_create_task(coro):
        """Mock create_task that closes coroutines to suppress warnings."""
        if hasattr(coro, "close"):
            coro.close()  # Silences 'coroutine never awaited'
        return MagicMock()

    hass.loop.create_task = MagicMock(side_effect=mock_create_task)
    # ---------------------------------------------------------

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
    manager.load_profile_cached = AsyncMock(
        return_value={
            "meta": {
                "preset_type": "thermostat",
                "global_prefix": "cronostar_thermostat_test_",
                "min_value": 10,
                "max_value": 30,
            },
            "profiles": {
                "Default": {
                    "schedule": [
                        {"time": "08:00", "value": 20.0},
                        {"time": "20:00", "value": 18.0},
                    ]
                },
                "Comfort": {
                    "schedule": [
                        {"time": "08:00", "value": 22.0},
                        {"time": "22:00", "value": 20.0},
                    ]
                },
            },
        }
    )
    manager.save_profile = AsyncMock()
    manager.get_cached_containers = AsyncMock(
        return_value=[
            (
                "test_profile.json",
                {
                    "meta": {
                        "preset_type": "thermostat",
                        "global_prefix": "cronostar_thermostat_test_",
                        "min_value": 10,
                        "max_value": 30,
                    },
                    "profiles": {
                        "Default": {
                            "schedule": [
                                {"time": "08:00", "value": 20.0},
                                {"time": "20:00", "value": 18.0},
                            ]
                        }
                    },
                },
            )
        ]
    )
    return manager


@pytest.fixture
def mock_coordinator(hass, mock_storage_manager):
    """Create a mock coordinator."""
    try:
        from custom_components.cronostar.const import DOMAIN
        from custom_components.cronostar.coordinator import CronoStarCoordinator
    except ImportError:
        CronoStarCoordinator = MagicMock()
        DOMAIN = "cronostar"

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Test Controller"
    entry.data = {
        "name": "Test Controller",
        "preset": "thermostat",
        "target_entity": "climate.test_thermostat",
        "global_prefix": "cronostar_thermostat_test_",
    }
    entry.options = {}

    hass.data[DOMAIN] = {"storage_manager": mock_storage_manager}

    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.async_refresh = AsyncMock()

    coordinator.data = {
        "selected_profile": "Default",
        "is_enabled": True,
        "current_value": 0.0,
        "available_profiles": ["Default"],
    }

    return coordinator


def pytest_collection_modifyitems(config, items):
    """Automatically add markers to all tests."""
    import inspect

    for item in items:
        # Add anyio marker to all async tests if not already present
        if inspect.iscoroutinefunction(item.obj):
            if "anyio" not in [m.name for m in item.iter_markers()]:
                item.add_marker(pytest.mark.anyio)

        # Add standard markers
        item.add_marker(pytest.mark.no_fail_on_log_exception)
        item.add_marker(pytest.mark.allow_socket)
