"""Tests for the local intent handler."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.azure_openai_sdk_conversation.local_intent.local_handler import LocalIntentHandler
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger
from homeassistant.components import conversation

@pytest.fixture
def mock_config(hass):
    return AgentConfig.from_dict(hass, {
        "api_key": "test",
        "api_base": "https://test",
        "chat_model": "gpt-4o",
        "local_intent_enable": True,
        "vocabulary_enable": True,
    })

@pytest.fixture
def logger(hass, mock_config):
    return AgentLogger(hass, mock_config)

@pytest.fixture
def handler(hass, mock_config, logger):
    return LocalIntentHandler(hass, mock_config, logger)

@pytest.mark.anyio
async def test_local_handler_try_handle_success(handler, hass):
    """Test successful local intent handling."""
    # Mock matcher
    handler._matcher.match_entities = MagicMock(return_value=[
        {"entity_id": "light.kitchen", "name": "Kitchen Light"}
    ])
    
    # Mock service call
    hass.services.async_call = AsyncMock()
    
    user_input = conversation.ConversationInput(
        text="accendi luce cucina",
        context=MagicMock(),
        conversation_id="conv1",
        language="it",
    )
    
    # normalized_text should start with "accendi" or "spegni" for _parse_onoff_intent
    result = await handler.try_handle("accendi cucina", user_input, start_time=0)
    
    assert result is not None
    assert "acceso" in result.response.speech["plain"]["speech"]
    assert "light.kitchen" in result.response.speech["plain"]["speech"]
    hass.services.async_call.assert_called_once()

@pytest.mark.anyio
async def test_local_handler_no_match(handler, hass):
    """Test when no entities match."""
    handler._matcher.match_entities = MagicMock(return_value=[])
    
    user_input = conversation.ConversationInput(
        text="accendi qualcosa di inesistente",
        context=MagicMock(),
        conversation_id="conv1",
        language="it",
    )
    
    result = await handler.try_handle("accendi inesistente", user_input, start_time=0)
    assert result is None

def test_parse_onoff_intent(handler):
    """Test parsing on/off intents."""
    # Italian
    action, tokens = handler._parse_onoff_intent("accendi luce cucina")
    assert action == "on"
    assert "cucina" in tokens
    
    action, tokens = handler._parse_onoff_intent("spegni il ventilatore")
    assert action == "off"
    assert "ventilatore" in tokens
    
    # Not an on/off intent
    assert handler._parse_onoff_intent("che ore sono?") is None

@pytest.mark.anyio
async def test_execute_service_error(handler, hass):
    """Test service execution error."""
    hass.services.async_call = AsyncMock(side_effect=Exception("Service failed"))
    
    results = await handler._execute_service("on", ["light.test"])
    assert len(results) == 1
    assert results[0][1] is False
    assert "Service failed" in results[0][2]
