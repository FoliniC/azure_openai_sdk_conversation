from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import time

from homeassistant.core import HomeAssistant
from homeassistant.components import conversation
from custom_components.azure_openai_sdk_conversation.core.agent import AzureOpenAIConversationAgent
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.const import (
    CONF_VOCABULARY_ENABLE,
    CONF_SYNONYMS_FILE,
    CONF_LOCAL_INTENT_ENABLE,
)

# Basic config entry data
MOCK_CONFIG_DATA = {
    "api_key": "fake_api_key",
    "api_base": "https://fake.openai.azure.com/",
    "chat_model": "gpt-4o-mini",
    "api_version": "2025-03-01-preview",
}

# Basic options
MOCK_OPTIONS = {
    CONF_VOCABULARY_ENABLE: True,
    CONF_SYNONYMS_FILE: "custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json",
    CONF_LOCAL_INTENT_ENABLE: True,
}

@pytest.fixture
def agent(hass) -> AzureOpenAIConversationAgent:
    """Fixture for a conversation agent instance."""
    conf_dict = {**MOCK_CONFIG_DATA, **MOCK_OPTIONS}
    config = AgentConfig.from_dict(hass, conf_dict)
    agent = AzureOpenAIConversationAgent(hass, config)
    # Manually set agent_id to avoid MagicMock parent issue
    agent.agent_id = "test_agent"
    return agent

@pytest.mark.anyio
async def test_agent_initialization(agent):
    """Test that the conversation agent initializes correctly."""
    assert agent._config.api_base == "https://fake.openai.azure.com"
    assert agent._config.chat_model == "gpt-4o-mini"
    assert agent._config.vocabulary_enable is True
    assert agent._config.local_intent_enable is True

@pytest.mark.anyio
async def test_supported_languages(agent):
    """Test supported languages."""
    assert "en" in agent.supported_languages
    assert "it" in agent.supported_languages

@pytest.mark.parametrize(
    "input_text, expected_text",
    [
        ("Spegni le luci del salotto", "spegni luce del soggiorno"),
        ("Accendi la lampada in cucina", "accendi luce in cucina"),
        ("Disattiva il ventilatore", "spegni il ventilatore"),
        ("  accendere   luce   tavolo  cucina  ", "accendi tavolo"),
        ("spegni l'aspirapolvere", "spegni l'aspirapolvere"),
    ],
)
@pytest.mark.anyio
async def test_normalize_text(agent, input_text, expected_text):
    """Test the text normalization and synonym replacement."""
    await agent._local_handler.ensure_vocabulary_loaded()
    normalized = agent._local_handler.normalize_text(input_text)
    assert normalized == expected_text

@pytest.mark.parametrize(
    "normalized_text, expected_action, expected_tokens",
    [
        ("spegni luce soggiorno", "off", ["soggiorno"]),
        ("accendi ventilatore", "on", ["ventilatore"]),
        ("spegni tavolo", "off", ["tavolo"]),
        ("accendi", "on", []),
        ("accendi tv", "on", ["tv"]),
        ("chiudi la porta", None, None),  # Not an on/off intent
    ],
)
def test_extract_onoff_intent(agent, normalized_text, expected_action, expected_tokens):
    """Test the local on/off intent extraction."""
    # Note: in new implementation it's _parse_onoff_intent and it's static
    intent = agent._local_handler._parse_onoff_intent(normalized_text)

    if expected_action is None:
        assert intent is None
    else:
        action, tokens = intent
        assert action == expected_action
        assert tokens == expected_tokens

@pytest.mark.anyio
async def test_async_process_empty_input(agent):
    """Test processing empty input."""
    user_input = conversation.ConversationInput(
        text="",
        context=MagicMock(),
        conversation_id="test_conv",
        language="en",
    )
    result = await agent.async_process(user_input)
    assert result.response.response_type == conversation.ResponseType.ACTION_DONE

@pytest.mark.anyio
async def test_async_process_default_agent_delegation(agent, hass):
    """Test delegation to default HA agent."""
    user_input = conversation.ConversationInput(
        text="turn on light",
        context=MagicMock(),
        conversation_id="test_conv",
        language="en",
    )
    
    mock_default_agent = AsyncMock()
    mock_default_agent.agent_id = "homeassistant"
    
    from homeassistant.helpers.intent import IntentResponse
    mock_response = IntentResponse(language="en")
    mock_response.async_set_speech("OK, turned on")
    
    mock_default_agent.async_process.return_value = conversation.ConversationResult(
        response=mock_response,
        conversation_id="test_conv"
    )
    
    agent_manager = MagicMock()
    agent_manager.async_get_agent = AsyncMock(return_value=mock_default_agent)
    
    with patch("homeassistant.components.conversation.get_agent_manager", return_value=agent_manager):
        result = await agent.async_process(user_input)
        
    assert result.response.speech["plain"]["speech"] == "OK, turned on"
    mock_default_agent.async_process.assert_called_once()

@pytest.mark.anyio
async def test_async_process_llm_fallback(agent, hass):
    """Test fallback to LLM when local intent fails."""
    user_input = conversation.ConversationInput(
        text="What is the weather?",
        context=MagicMock(),
        conversation_id="test_conv",
        language="en",
    )
    
    # Mock no default agent or default agent returns no_intent_match
    agent_manager = MagicMock()
    agent_manager.async_get_agent = AsyncMock(side_effect=ValueError("Not found"))
    
    # Mock local handler failure
    agent._local_handler.try_handle = AsyncMock(return_value=None)
    
    # Mock collector to avoid registry errors
    agent._prompt_builder._collector.collect = AsyncMock(return_value=[])
    
    # Mock ChatClient
    with patch.object(agent, "_chat_client") as mock_chat:
        mock_chat.complete = AsyncMock(return_value=("It is sunny.", {"total": 10}))
        mock_chat.effective_api_version = "2024-05-01-preview"
        
        with patch("homeassistant.components.conversation.get_agent_manager", return_value=agent_manager):
            result = await agent.async_process(user_input)
            
    assert result.response.speech["plain"]["speech"] == "It is sunny."