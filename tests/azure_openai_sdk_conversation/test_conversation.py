from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock

from homeassistant.core import HomeAssistant
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
def mock_hass() -> HomeAssistant:
    """Fixture for a mock Home Assistant."""
    hass = MagicMock()
    
    # Mock config.path
    def mock_path(*args):
        return "/config/" + "/".join(args)
    hass.config.path = mock_path
    
    # Mock async_add_executor_job
    async def mock_executor(func, *args):
        return func(*args)
    hass.async_add_executor_job = mock_executor
    
    hass.data = {}
    hass.states = MagicMock()
    hass.services = MagicMock()
    
    return hass

@pytest.fixture
def agent(mock_hass) -> AzureOpenAIConversationAgent:
    """Fixture for a conversation agent instance."""
    conf_dict = {**MOCK_CONFIG_DATA, **MOCK_OPTIONS}
    config = AgentConfig.from_dict(mock_hass, conf_dict)
    return AzureOpenAIConversationAgent(mock_hass, config)

@pytest.mark.anyio
async def test_agent_initialization(agent):
    """Test that the conversation agent initializes correctly."""
    assert agent._config.api_base == "https://fake.openai.azure.com"
    assert agent._config.chat_model == "gpt-4o-mini"
    assert agent._config.vocabulary_enable is True
    assert agent._config.local_intent_enable is True

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