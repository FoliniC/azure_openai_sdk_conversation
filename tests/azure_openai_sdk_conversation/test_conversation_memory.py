"""
Unit tests for ConversationMemoryManager.

Run with: pytest tests/test_conversation_memory.py -v
"""

from unittest.mock import MagicMock

import pytest

from custom_components.azure_openai_sdk_conversation.context.conversation_memory import (
    ConversationMemoryManager,
)
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = lambda *args: "/config/" + "/".join(args)

    async def mock_async_add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = mock_async_add_executor_job
    return hass


@pytest.fixture
def config(mock_hass):
    """Mock AgentConfig with sliding window enabled."""
    return AgentConfig.from_dict(
        mock_hass,
        {
            "api_key": "test",
            "api_base": "https://test.openai.azure.com",
            "chat_model": "gpt-4o",
            "sliding_window_enable": True,
            "sliding_window_max_tokens": 100,  # Small for testing
            "sliding_window_preserve_system": True,
        },
    )


@pytest.fixture
def logger(mock_hass, config):
    """Mock AgentLogger."""
    return AgentLogger(mock_hass, config)


@pytest.fixture
def memory_manager(mock_hass, config, logger):
    """ConversationMemoryManager instance."""
    return ConversationMemoryManager(
        hass=mock_hass,
        config=config,
        logger=logger,
    )


@pytest.mark.anyio
async def test_add_message_creates_window(memory_manager):
    """Test that adding message creates new window."""
    conv_id = "test_conv_1"

    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Hello",
        tags={"input"},
    )

    stats = memory_manager.get_stats(conv_id)
    assert stats["exists"] is True
    assert stats["message_count"] == 1


@pytest.mark.anyio
async def test_fifo_eviction(memory_manager):
    """Test FIFO eviction when token limit exceeded."""
    conv_id = "test_conv_2"

    # Add messages until we exceed limit (100 tokens)
    for i in range(10):
        await memory_manager.add_message(
            conversation_id=conv_id,
            role="user",
            content=f"Message {i}" * 5,  # Each ~10 tokens
        )

    stats = memory_manager.get_stats(conv_id)

    # Should have evicted some messages
    assert stats["message_count"] < 10
    assert stats["current_tokens"] <= 100


@pytest.mark.anyio
async def test_preserve_system_messages(memory_manager):
    """Test that system messages are preserved during eviction."""
    conv_id = "test_conv_3"

    # Add system message
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="system",
        content="You are a helpful assistant.",
        tags={"system"},
    )

    # Add many user messages to trigger eviction
    for i in range(20):
        await memory_manager.add_message(
            conversation_id=conv_id,
            role="user",
            content=f"Message {i}" * 5,
        )

    messages = await memory_manager.get_messages(conv_id)

    # System message should still be present
    assert any(msg["role"] == "system" for msg in messages)


@pytest.mark.anyio
async def test_tag_filtering(memory_manager):
    """Test message retrieval with tag filter."""
    conv_id = "test_conv_4"

    # Add messages with different tags
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="User message",
        tags={"input", "important"},
    )

    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="Assistant response",
        tags={"output"},
    )

    # Filter by tag
    important_msgs = await memory_manager.get_messages(
        conv_id, tag_filter={"important"}
    )

    assert len(important_msgs) == 1
    assert important_msgs[0]["role"] == "user"


@pytest.mark.anyio
async def test_reset_conversation(memory_manager):
    """Test conversation reset."""
    conv_id = "test_conv_5"

    # Add messages
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Hello",
    )

    # Reset
    await memory_manager.reset_conversation(conv_id)

    # Window should be gone
    stats = memory_manager.get_stats(conv_id)
    assert stats["exists"] is False


@pytest.mark.anyio
async def test_token_counting(memory_manager):
    """Test accurate token counting with tiktoken."""
    conv_id = "test_conv_6"

    text = "Hello, how are you?"

    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content=text,
    )

    stats = memory_manager.get_stats(conv_id)

    # Token count should be > 0 and reasonable
    assert stats["current_tokens"] > 0
    assert stats["current_tokens"] < len(text)  # Tokens < chars


@pytest.mark.anyio
async def test_multiple_conversations(memory_manager):
    """Test managing multiple conversations."""
    conv_ids = ["conv_1", "conv_2", "conv_3"]

    for conv_id in conv_ids:
        await memory_manager.add_message(
            conversation_id=conv_id,
            role="user",
            content="Message",
        )

    all_convs = memory_manager.get_all_conversations()

    assert len(all_convs) == 3
    assert set(all_convs) == set(conv_ids)


@pytest.mark.anyio
async def test_tag_distribution_stats(memory_manager):
    """Test tag distribution in stats."""
    conv_id = "test_conv_7"

    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Message 1",
        tags={"input", "important"},
    )

    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="Message 2",
        tags={"output"},
    )

    stats = memory_manager.get_stats(conv_id)

    assert "tag_distribution" in stats
    assert stats["tag_distribution"]["input"] == 1
    assert stats["tag_distribution"]["important"] == 1
    assert stats["tag_distribution"]["output"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
