"""Tests for the conversation platform setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.azure_openai_sdk_conversation.const import DOMAIN
from custom_components.azure_openai_sdk_conversation.conversation import (
    async_setup_entry,
    async_unload_entry,
)


@pytest.mark.anyio
async def test_async_setup_entry_success(hass):
    """Test successful setup of the conversation platform."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {
        "api_key": "fake-key",
        "api_base": "https://fake.openai.azure.com",
        "chat_model": "gpt-4o",
    }

    config_entry.options = {
        "prompt": "Test prompt",
    }

    async_add_entities = MagicMock()

    with (
        patch(
            "custom_components.azure_openai_sdk_conversation.conversation.AzureOpenAIConversationAgent"
        ) as mock_agent_class,
        patch(
            "homeassistant.components.conversation.async_set_agent"
        ) as mock_set_agent,
    ):
        mock_agent = mock_agent_class.return_value
        mock_agent.async_setup = AsyncMock()

        result = await async_setup_entry(hass, config_entry, async_add_entities)

        assert result is True
        mock_agent.async_setup.assert_called_once()
        mock_set_agent.assert_called_once()
        assert hass.data[DOMAIN][config_entry.entry_id] == mock_agent


@pytest.mark.anyio
async def test_async_unload_entry(hass):
    """Test successful unloading of the conversation platform."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    mock_agent = MagicMock()
    mock_agent.async_close = AsyncMock()

    hass.data[DOMAIN] = {config_entry.entry_id: mock_agent}

    result = await async_unload_entry(hass, config_entry)

    assert result is True
    mock_agent.async_close.assert_called_once()
    assert config_entry.entry_id not in hass.data[DOMAIN]
