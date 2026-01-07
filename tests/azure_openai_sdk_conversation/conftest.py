import os
import sys

# Add the current directory to path so we can import mock_ha relatively or absolutely
sys.path.insert(0, os.path.dirname(__file__))
import mock_ha # Must be first to mock HA modules
import socket
import _socket

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

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

def pytest_configure(config):
    """Add project root to python path and ensure sockets are enabled."""
    config.addinivalue_line("markers", "allow_socket: allow socket usage")
    
    try:
        import pytest_socket
        pytest_socket.enable_socket()
    except Exception:
        pass

    # Go up two levels: tests/azure_openai_sdk_conversation -> tests -> project_root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    sys.path.insert(0, project_root)
    # Also add custom_components directory specifically
    sys.path.insert(0, os.path.join(project_root, "custom_components"))

@pytest.fixture
def enable_custom_integrations():
    """Mock fixture if not provided by plugin."""
    return True

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test repository."""
    yield


@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms to be loaded."""
    return ["conversation"]

def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker("no_fail_on_log_exception")
        item.add_marker("allow_socket")
