"""Extra tests for error_handler.py."""
import pytest
import logging
from unittest.mock import MagicMock, patch
from homeassistant.exceptions import HomeAssistantError
from custom_components.cronostar.utils.error_handler import (
    handle_service_errors,
    CronoStarError,
    safe_get,
    build_error_response,
    log_operation
)

@pytest.mark.anyio
async def test_handle_service_errors_success():
    """Test handle_service_errors decorator with success."""
    @handle_service_errors
    async def mock_func(val):
        return val
    
    assert await mock_func(10) == 10

@pytest.mark.anyio
async def test_handle_service_errors_cronostar_error():
    """Test handle_service_errors decorator with CronoStarError."""
    @handle_service_errors
    async def mock_func():
        raise CronoStarError("CronoStar error")
    
    with pytest.raises(CronoStarError):
        await mock_func()

@pytest.mark.anyio
async def test_handle_service_errors_unexpected_error():
    """Test handle_service_errors decorator with unexpected error."""
    @handle_service_errors
    async def mock_func():
        raise ValueError("Unexpected error")
    
    with pytest.raises(HomeAssistantError) as excinfo:
        await mock_func()
    assert "Service failed: Unexpected error" in str(excinfo.value)

def test_safe_get_non_dict():
    """Test safe_get with non-dictionary intermediate value."""
    data = {"a": 1}
    assert safe_get(data, "a", "b") is None
    assert safe_get(data, "a", "b", default="missing") == "missing"

def test_build_error_response_no_context():
    """Test build_error_response without context."""
    err = ValueError("test error")
    resp = build_error_response(err)
    assert resp["success"] is False
    assert resp["error"] == "test error"
    assert "context" not in resp

def test_log_operation_failure(caplog):
    """Test log_operation with failure."""
    import logging
    with caplog.at_level(logging.WARNING):
        log_operation("test_op", False)
        assert "✗ test_op" in caplog.text
