"""
Basic tests for tool calling functionality.

To run:
    pytest tests/test_tools.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from homeassistant.core import HomeAssistant

from custom_components.azure_openai_sdk_conversation.tools import (
    ToolSchemaBuilder,
    FunctionExecutor,
    ToolManager,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_services = MagicMock(
        return_value={
            "light": {
                "turn_on": {
                    "description": "Turn on a light",
                    "fields": {
                        "entity_id": {
                            "description": "Entity ID",
                            "required": True,
                            "selector": {"entity": {"domain": "light"}},
                        },
                        "brightness": {
                            "description": "Brightness (0-255)",
                            "required": False,
                            "selector": {"number": {"min": 0, "max": 255}},
                        },
                    },
                },
                "turn_off": {
                    "description": "Turn off a light",
                    "fields": {
                        "entity_id": {
                            "description": "Entity ID",
                            "required": True,
                            "selector": {"entity": {"domain": "light"}},
                        },
                    },
                },
            },
            "switch": {
                "turn_on": {
                    "description": "Turn on a switch",
                    "fields": {
                        "entity_id": {
                            "description": "Entity ID",
                            "required": True,
                            "selector": {"entity": {"domain": "switch"}},
                        },
                    },
                },
            },
        }
    )

    hass.states = MagicMock()
    hass.states.get = MagicMock(
        return_value=MagicMock(
            entity_id="light.living_room",
            name="Living Room Light",
            state="off",
        )
    )

    return hass


@pytest.mark.asyncio
async def test_schema_builder_basic(mock_hass):
    """Test basic schema building."""
    builder = ToolSchemaBuilder(mock_hass)

    tools = await builder.build_all_tools(allowed_domains={"light"})

    assert len(tools) > 0
    assert tools[0]["type"] == "function"
    assert "function" in tools[0]
    assert "name" in tools[0]["function"]
    assert "description" in tools[0]["function"]
    assert "parameters" in tools[0]["function"]


@pytest.mark.asyncio
async def test_schema_builder_filters_domains(mock_hass):
    """Test domain filtering."""
    builder = ToolSchemaBuilder(mock_hass)

    # Only light domain
    light_tools = await builder.build_all_tools(allowed_domains={"light"})
    light_names = [t["function"]["name"] for t in light_tools]

    assert all(name.startswith("light_") for name in light_names)
    assert not any(name.startswith("switch_") for name in light_names)


@pytest.mark.asyncio
async def test_function_executor_validation(mock_hass):
    """Test function executor validation."""
    executor = FunctionExecutor(
        hass=mock_hass,
        allowed_domains={"light", "switch"},
        max_calls_per_minute=30,
    )

    # Valid call
    valid_call = {
        "id": "call_123",
        "function": {
            "name": "light_turn_on",
            "arguments": '{"entity_id": "light.living_room"}',
        },
    }

    # Mock async_call
    mock_hass.services.async_call = AsyncMock()

    result = await executor.execute_tool_call(valid_call)

    assert result["success"] is True
    assert "light.living_room" in result["content"]
    mock_hass.services.async_call.assert_called_once()


@pytest.mark.asyncio
async def test_function_executor_blacklist(mock_hass):
    """Test blacklisted service rejection."""
    executor = FunctionExecutor(
        hass=mock_hass,
        allowed_domains={"homeassistant"},
        max_calls_per_minute=30,
    )

    # Blacklisted service
    blacklisted_call = {
        "id": "call_456",
        "function": {
            "name": "homeassistant_restart",
            "arguments": "{}",
        },
    }

    result = await executor.execute_tool_call(blacklisted_call)

    assert result["success"] is False
    assert "blacklisted" in result["content"].lower()


@pytest.mark.asyncio
async def test_function_executor_rate_limit(mock_hass):
    """Test rate limiting."""
    executor = FunctionExecutor(
        hass=mock_hass,
        allowed_domains={"light"},
        max_calls_per_minute=2,  # Very low limit for testing
    )

    mock_hass.services.async_call = AsyncMock()

    call_template = {
        "id": "call_{}",
        "function": {
            "name": "light_turn_on",
            "arguments": '{"entity_id": "light.test"}',
        },
    }

    # First two calls should succeed
    for i in range(2):
        call = call_template.copy()
        call["id"] = f"call_{i}"
        result = await executor.execute_tool_call(call)
        assert result["success"] is True

    # Third call should be rate limited
    call = call_template.copy()
    call["id"] = "call_3"
    result = await executor.execute_tool_call(call)
    assert result["success"] is False
    assert "rate limit" in result["content"].lower()


@pytest.mark.asyncio
async def test_function_executor_invalid_entity(mock_hass):
    """Test invalid entity_id handling."""
    executor = FunctionExecutor(
        hass=mock_hass,
        allowed_domains={"light"},
        max_calls_per_minute=30,
    )

    # Mock state as None (non-existent entity)
    mock_hass.states.get = MagicMock(return_value=None)

    invalid_call = {
        "id": "call_789",
        "function": {
            "name": "light_turn_on",
            "arguments": '{"entity_id": "light.nonexistent"}',
        },
    }

    result = await executor.execute_tool_call(invalid_call)

    assert result["success"] is False
    assert (
        "invalid" in result["content"].lower()
        or "non-existent" in result["content"].lower()
    )


@pytest.mark.asyncio
async def test_tool_manager_cache(mock_hass):
    """Test tool schema caching."""
    from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
    from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger

    config = AgentConfig.from_dict(
        mock_hass,
        {
            "api_key": "test",
            "api_base": "https://test.openai.azure.com",
            "chat_model": "gpt-4o",
            "tools_enable": True,
            "tools_whitelist": "light,switch",
        },
    )

    logger = AgentLogger(config)

    manager = ToolManager(hass=mock_hass, config=config, logger=logger)

    # First call - builds schema
    tools1 = await manager.get_tools_schema()
    assert len(tools1) > 0

    # Second call - uses cache
    tools2 = await manager.get_tools_schema()
    assert tools1 == tools2

    # Invalidate cache
    manager.invalidate_cache()

    # Third call - rebuilds
    tools3 = await manager.get_tools_schema()
    assert len(tools3) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
