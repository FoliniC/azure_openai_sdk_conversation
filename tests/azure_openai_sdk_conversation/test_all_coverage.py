"""Comprehensive tests for Azure OpenAI SDK Conversation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.const import CONF_API_KEY

from custom_components.azure_openai_sdk_conversation.const import (
    CONF_API_BASE,
    CONF_CHAT_MODEL,
)
from custom_components.azure_openai_sdk_conversation.context.conversation_memory import (
    ConversationMemoryManager,
)
from custom_components.azure_openai_sdk_conversation.context.system_prompt import (
    SystemPromptBuilder,
)
from custom_components.azure_openai_sdk_conversation.core.agent import (
    AzureOpenAIConversationAgent,
)
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig


@pytest.fixture
def mock_config(hass):
    """Create a standard agent config."""
    return AgentConfig.from_dict(
        hass,
        {
            CONF_API_KEY: "test-key",
            CONF_API_BASE: "https://test.openai.azure.com",
            CONF_CHAT_MODEL: "gpt-4o",
            "api_version": "2024-05-01-preview",
            "sliding_window_enable": True,
            "sliding_window_max_tokens": 100,
            "tools_enable": False,
            "stats_enable": False,
            "vocabulary_enable": False,
            # ✅ FIX: Disable Early Wait to prevent timeout messages in tests
            "early_wait_enable": False,
        },
    )


@pytest.fixture
def agent(hass, mock_config):
    """Create an agent instance with mocked dependencies."""
    with (
        patch("custom_components.azure_openai_sdk_conversation.core.agent.ChatClient"),
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.LocalIntentHandler"
        ),
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.SystemPromptBuilder"
        ),
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.ConversationMemoryManager"
        ),
    ):
        agent = AzureOpenAIConversationAgent(hass, mock_config)
        return agent


@pytest.mark.asyncio
async def test_agent_process_empty_input(agent):
    """Test that empty input is handled gracefully."""
    user_input = conversation.ConversationInput(
        text="",
        conversation_id="conv_1",
        language="en",
        agent_id="agent_1",
        device_id=None,
    )

    with patch.object(agent, "_chat_client") as mock_chat:
        mock_chat.complete = AsyncMock(return_value=("", {"total": 0}))
        result = await agent.async_process(user_input)

        assert result is not None
        assert result.response is not None


@pytest.mark.asyncio
async def test_agent_process_success_llm(hass, mock_config):
    """Test successful LLM processing path."""
    with (
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.ChatClient"
        ) as MockClient,
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.LocalIntentHandler"
        ) as MockLocal,
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.SystemPromptBuilder"
        ) as MockBuilder,
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.ConversationMemoryManager"
        ) as MockMem,
        patch(
            "homeassistant.components.conversation.get_agent_manager"
        ) as mock_get_manager,
    ):
        mock_manager = mock_get_manager.return_value
        mock_manager.async_get_agent = AsyncMock(return_value=None)

        agent = AzureOpenAIConversationAgent(hass, mock_config)

        # Mocks
        mock_chat = MockClient.return_value
        mock_chat.complete = AsyncMock(return_value=("Hello human!", {"total": 10}))

        mock_local = MockLocal.return_value
        mock_local.try_handle = AsyncMock(return_value=None)
        mock_local.normalize_text = MagicMock(return_value="hello")
        mock_local.ensure_vocabulary_loaded = AsyncMock()

        mock_builder_inst = MockBuilder.return_value
        mock_builder_inst.build = AsyncMock(return_value="System prompt")

        mock_mem = MockMem.return_value
        mock_mem.add_message = AsyncMock()
        mock_mem.get_messages = AsyncMock(return_value=[])
        mock_mem.async_set_system_prompt = AsyncMock()

        # Inject mocks
        agent._chat_client = mock_chat
        agent._local_handler = mock_local
        agent._prompt_builder = mock_builder_inst
        agent._memory = mock_mem

        user_input = conversation.ConversationInput(
            text="Hello",
            conversation_id="c1",
            language="en",
            agent_id="a1",
            device_id=None,
        )

        result = await agent.async_process(user_input)

        assert "Hello human!" in result.response.speech["plain"]["speech"]
        mock_chat.complete.assert_awaited()


@pytest.mark.asyncio
async def test_agent_local_intent_fallback(hass, mock_config):
    """Test that local intent handler is tried before LLM."""
    with (
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.ChatClient"
        ) as MockClient,
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.LocalIntentHandler"
        ) as MockLocal,
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.SystemPromptBuilder"
        ),
        patch(
            "custom_components.azure_openai_sdk_conversation.core.agent.ConversationMemoryManager"
        ) as MockMem,
        patch(
            "homeassistant.components.conversation.get_agent_manager"
        ) as mock_get_manager,
    ):
        mock_manager = mock_get_manager.return_value
        mock_manager.async_get_agent = AsyncMock(return_value=None)

        agent = AzureOpenAIConversationAgent(hass, mock_config)

        # Mocks
        mock_local = MockLocal.return_value
        mock_local_response = MagicMock()
        mock_local_response.response.speech = {"plain": {"speech": "Local response"}}
        mock_local_response.response.response_type = (
            "action_done"  # Ensure success type
        )

        mock_local.try_handle = AsyncMock(return_value=mock_local_response)
        mock_local.normalize_text = MagicMock(return_value="turn on light")
        mock_local.ensure_vocabulary_loaded = AsyncMock()

        mock_chat = MockClient.return_value
        mock_chat.complete = AsyncMock()  # Should NOT be called

        mock_mem = MockMem.return_value
        mock_mem.add_message = AsyncMock()

        agent._chat_client = mock_chat
        agent._local_handler = mock_local
        agent._memory = mock_mem

        user_input = conversation.ConversationInput(
            text="turn on light",
            conversation_id="c1",
            language="en",
            agent_id="a1",
            device_id=None,
        )

        result = await agent.async_process(user_input)

        assert "Local response" in result.response.speech["plain"]["speech"]
        # ✅ FIX: Use assert_not_called() instead of assert_not_awaited() for broader compatibility
        mock_chat.complete.assert_not_called()


@pytest.mark.asyncio
async def test_memory_manager_eviction(hass, mock_config):
    """Test memory manager sliding window logic."""
    mock_tiktoken = MagicMock()
    mock_encoding = MagicMock()
    mock_encoding.encode = lambda x: [1] * len(x)
    mock_tiktoken.get_encoding.return_value = mock_encoding

    with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
        logger = MagicMock()
        mock_config.sliding_window_max_tokens = 20
        mock_config.sliding_window_preserve_system = True

        mgr = ConversationMemoryManager(hass, mock_config, logger)
        mgr._tiktoken = mock_tiktoken
        mgr._encoding = mock_encoding

        await mgr.add_message("c1", "system", "Sys")
        await mgr.add_message("c1", "user", "1234567890")
        await mgr.add_message("c1", "assistant", "1234567890")

        msgs = await mgr.get_messages("c1")
        assert len(msgs) <= 2
        assert any(m["role"] == "system" for m in msgs)


@pytest.mark.asyncio
async def test_system_prompt_builder(hass, mock_config):
    """Test system prompt construction."""
    logger = MagicMock()

    with patch(
        "custom_components.azure_openai_sdk_conversation.context.system_prompt.EntityCollector"
    ) as MockCollector:
        builder = SystemPromptBuilder(hass, mock_config, logger)

        mock_collector = MockCollector.return_value
        mock_collector.collect = AsyncMock(
            return_value=[
                {
                    "entity_id": "light.living",
                    "name": "Living",
                    "state": "on",
                    "area": "Living Room",
                }
            ]
        )
        builder._collector = mock_collector

        prompt = await builder.build("c1")

        assert "light.living" in prompt
        assert "Living" in prompt
        assert len(prompt) > 50


@pytest.mark.asyncio
async def test_config_normalization(hass):
    """Test AgentConfig initialization and normalization."""
    config_dict = {
        CONF_API_KEY: "test-key",
        CONF_API_BASE: "https://test.openai.azure.com/",
        CONF_CHAT_MODEL: "gpt-4o",
    }
    config = AgentConfig.from_dict(hass, config_dict)
    assert config.api_key == "test-key"
    assert not config.api_base.endswith("/")


@pytest.mark.asyncio
async def test_stream_parser_basic():
    """Test basic SSE stream parsing."""
    from custom_components.azure_openai_sdk_conversation.llm.stream_parser import (
        SSEStreamParser,
    )

    parser = SSEStreamParser()
    lines = [
        'data: {"choices": [{"index": 0, "delta": {"content": "Hello"}}]}',
        'data: {"choices": [{"index": 0, "delta": {"content": " world"}}]}',
        "data: [DONE]",
    ]
    content, tool_calls, tokens = parser.parse_stream(lines)
    assert content == "Hello world"
