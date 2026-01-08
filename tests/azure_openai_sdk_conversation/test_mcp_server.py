"""Tests for the MCP server."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.azure_openai_sdk_conversation.mcp_server import HAMCPStateManager, HAMCPServer

def test_mcp_state_manager_initial_prompt():
    mgr = HAMCPStateManager()
    entities = [{"entity_id": "light.test", "name": "Test Light", "state": "off", "area": "Living"}]
    prompt = mgr.get_initial_prompt("conv1", entities, "Base prompt")
    
    assert "Base prompt" in prompt
    assert "light.test" in prompt
    assert mgr.is_new_conversation("conv1") is False

def test_mcp_state_manager_delta_prompt():
    mgr = HAMCPStateManager()
    entities = [{"entity_id": "light.test", "name": "Test Light", "state": "off", "area": "Living"}]
    mgr.get_initial_prompt("conv1", entities, "Base prompt")
    
    # No change
    delta = mgr.get_delta_prompt("conv1", entities)
    assert delta is None
    
    # State change
    entities[0]["state"] = "on"
    delta = mgr.get_delta_prompt("conv1", entities)
    assert "Changed entities" in delta
    assert "light.test" in delta
    assert "on" in delta

def test_mcp_state_manager_new_entity():
    mgr = HAMCPStateManager()
    mgr.get_initial_prompt("conv1", [], "Base prompt")
    
    entities = [{"entity_id": "light.new", "name": "New Light", "state": "off"}]
    delta = mgr.get_delta_prompt("conv1", entities)
    assert "New entities" in delta
    assert "light.new" in delta

@pytest.mark.anyio
async def test_mcp_server_prepare_message():
    hass = MagicMock()
    agent = MagicMock()
    server = HAMCPServer(hass, agent)
    
    entities = [{"entity_id": "light.test", "name": "Test Light", "state": "off"}]
    
    # Initial
    msg = server.prepare_system_message("conv1", entities, "Base")
    assert "Initial Full State" in msg
    
    # Delta (no change)
    msg = server.prepare_system_message("conv1", entities, "Base")
    assert "No changes" in msg

@pytest.mark.anyio
async def test_mcp_server_start_stop():
    hass = MagicMock()
    agent = MagicMock()
    server = HAMCPServer(hass, agent)
    
    await server.start()
    assert server._cleanup_task is not None
    
    await server.stop()
    assert server._cleanup_task.cancelled()
