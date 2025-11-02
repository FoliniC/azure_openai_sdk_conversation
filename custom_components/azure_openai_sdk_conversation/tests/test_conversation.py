from __future__ import annotations
import pytest
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.azure_openai_sdk_conversation.conversation import AzureOpenAIConversationAgent
from custom_components.azure_openai_sdk_conversation.const import (
    CONF_VOCABULARY_ENABLE,
    CONF_SYNONYMS_FILE,
    CONF_LOCAL_INTENT_ENABLE,
)

pytest_plugins = "pytest_homeassistant_custom_component"


# Basic config entry data
MOCK_CONFIG_DATA = {
    "api_key": "fake_api_key",
    "api_base": "https://fake.openai.azure.com/",
    "chat_model": "gpt-4o-mini",
}

# Basic options
MOCK_OPTIONS = {
    CONF_VOCABULARY_ENABLE: True,
    CONF_SYNONYMS_FILE: "", # Use default synonyms
    CONF_LOCAL_INTENT_ENABLE: True,
}

@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Fixture for a mock Home Assistant."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.path = lambda *args: "/config/" + "/".join(args)
    # Mock async_add_executor_job to run sync functions directly
    async def mock_async_add_executor_job(func, *args):
        return func(*args)
    hass.async_add_executor_job = mock_async_add_executor_job
    return hass

@pytest.fixture
def agent(mock_hass) -> AzureOpenAIConversationAgent:
    """Fixture for a conversation agent instance."""
    conf = {**MOCK_CONFIG_DATA, **MOCK_OPTIONS}
    return AzureOpenAIConversationAgent(mock_hass, conf)

async def test_agent_initialization(agent):
    """Test that the conversation agent initializes correctly."""
    assert agent._endpoint == "https://fake.openai.azure.com"
    assert agent._deployment == "gpt-4o-mini"
    assert agent._vocabulary_enable is True
    assert agent._local_intent_enable is True

@pytest.mark.parametrize(
    "input_text, expected_text",
    [
        ("Spegni le luci del salotto", "spegni luce soggiorno"),
        ("Accendi la lampada in cucina", "accendi luce cucina"),
        ("Disattiva il ventilatore", "spegni ventilatore"),
        ("  accendere   luce   tavolo  cucina  ", "accendi tavolo"),
        ("spegni l'aspirapolvere", "spegni aspirapolvere"),
    ],
)
async def test_normalize_text(agent, input_text, expected_text):
    """Test the text normalization and synonym replacement."""
    await agent._ensure_synonyms_loaded() # Load default synonyms
    normalized = agent._normalize_text(input_text)
    assert normalized == expected_text

@pytest.mark.parametrize(
    "normalized_text, expected_action, expected_tokens",
    [
        ("spegni luce soggiorno", "spegni", ["soggiorno"]),
        ("accendi ventilatore", "accendi", ["ventilatore"]),
        ("spegni tavolo", "spegni", ["tavolo"]),
        ("accendi", "accendi", []),
        ("accendi tv", "accendi", ["tv"]),
        ("chiudi la porta", None, None), # Not an on/off intent
    ],
)
def test_extract_onoff_intent(agent, normalized_text, expected_action, expected_tokens):
    """Test the local on/off intent extraction."""
    intent = agent._extract_onoff_intent(normalized_text)
    
    if expected_action is None:
        assert intent is None
    else:
        action, tokens = intent
        assert action == expected_action
        assert tokens == expected_tokens
