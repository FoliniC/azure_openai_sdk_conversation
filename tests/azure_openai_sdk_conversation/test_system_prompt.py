"""Tests for the system prompt builder."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.azure_openai_sdk_conversation.context.system_prompt import SystemPromptBuilder
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger

@pytest.fixture
def mock_config(hass):
    return AgentConfig.from_dict(hass, {
        "api_key": "test",
        "api_base": "https://test",
        "chat_model": "gpt-4o",
        "mcp_enabled": False
    })

@pytest.fixture
def logger(hass, mock_config):
    return AgentLogger(hass, mock_config)

@pytest.fixture
def builder(hass, mock_config, logger):
    return SystemPromptBuilder(hass, mock_config, logger)

@pytest.mark.anyio
async def test_build_full_prompt(builder, hass):
    """Test building full prompt without MCP."""
    builder._collector.collect = AsyncMock(return_value=[
        {"entity_id": "light.test", "name": "Test Light", "state": "on", "area": "Living"}
    ])
    
    prompt = await builder.build()
    
    assert "Test Light" in prompt
    assert "light.test" in prompt
    assert "Living" in prompt

@pytest.mark.anyio
async def test_build_mcp_initial(hass, logger):
    """Test building MCP initial prompt."""
    config = AgentConfig.from_dict(hass, {
        "api_key": "test",
        "api_base": "https://test",
        "chat_model": "gpt-4o",
        "mcp_enabled": True
    })
    
    # Mock loop.create_task to avoid MCP starting in background
    hass.loop.create_task = MagicMock()
    
    builder = SystemPromptBuilder(hass, config, logger)
    builder._collector.collect = AsyncMock(return_value=[])
    
    with patch.object(builder._mcp, "is_new_conversation", return_value=True), \
         patch.object(builder._mcp, "build_initial_prompt", return_value="Initial Prompt"):
        
        prompt = await builder.build(conversation_id="conv1")
        assert prompt == "Initial Prompt"

@pytest.mark.anyio
async def test_build_mcp_delta(hass, logger):
    """Test building MCP delta prompt."""
    config = AgentConfig.from_dict(hass, {
        "api_key": "test",
        "api_base": "https://test",
        "chat_model": "gpt-4o",
        "mcp_enabled": True
    })
    hass.loop.create_task = MagicMock()
    
    builder = SystemPromptBuilder(hass, config, logger)
    builder._collector.collect = AsyncMock(return_value=[])
    
    with patch.object(builder._mcp, "is_new_conversation", return_value=False), \
         patch.object(builder._mcp, "build_delta_prompt", return_value="Delta Prompt"):
        
        prompt = await builder.build(conversation_id="conv1")
        assert prompt == "Delta Prompt"
