"""Tests for the MCP manager."""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from custom_components.azure_openai_sdk_conversation.context.mcp_manager import MCPManager
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger

@pytest.fixture
def mock_config(hass):
    return AgentConfig.from_dict(hass, {
        "api_key": "test",
        "api_base": "https://test",
        "chat_model": "gpt-4o",
    })

@pytest.fixture
def logger(hass, mock_config):
    return AgentLogger(hass, mock_config)

@pytest.fixture
def manager(hass, logger):
    return MCPManager(hass, ttl_seconds=3600, logger=logger)

@pytest.mark.anyio
async def test_mcp_manager_initial_and_delta(manager):
    conv_id = "test_conv"
    entities = [{"entity_id": "light.test", "name": "Light", "state": "off", "area": "Kitchen"}]
    
    # Initial
    assert manager.is_new_conversation(conv_id) is True
    prompt = manager.build_initial_prompt(conv_id, entities, "Base")
    assert "Light" in prompt
    assert manager.is_new_conversation(conv_id) is False
    
    # Delta - no change
    delta = manager.build_delta_prompt(conv_id, entities)
    assert delta is None
    
    # Delta - state change
    entities[0]["state"] = "on"
    delta = manager.build_delta_prompt(conv_id, entities)
    assert "Changed entities" in delta
    assert "light.test" in delta
    
    # Delta - removed entity
    delta = manager.build_delta_prompt(conv_id, [])
    assert "Removed entities: light.test" in delta

@pytest.mark.anyio
async def test_mcp_manager_cleanup(manager):
    conv_id = "old_conv"
    manager.build_initial_prompt(conv_id, [], "Base")
    
    # Backdate last update
    manager._last_updated[conv_id] = datetime.now(timezone.utc) - timedelta(seconds=4000)
    
    await manager._cleanup_old_conversations()
    assert manager.is_new_conversation(conv_id) is True

def test_mcp_manager_stats(manager):
    manager.build_initial_prompt("c1", [{"entity_id": "e1", "name": "n1", "state": "s1"}], "B")
    stats = manager.get_stats()
    assert stats["active_conversations"] == 1
    assert stats["total_entities_tracked"] == 1
