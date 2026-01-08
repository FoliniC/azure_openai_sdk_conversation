"""Tests for the Chat Completions client."""

import pytest
from unittest.mock import MagicMock, patch
import httpx
from custom_components.azure_openai_sdk_conversation.llm.chat_client import ChatClient
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger


@pytest.fixture
def mock_config(hass):
    return AgentConfig.from_dict(hass, {
        "api_key": "test-key",
        "api_base": "https://test.openai.azure.com/",
        "chat_model": "gpt-4o",
        "api_version": "2024-05-01-preview",
    })


@pytest.fixture
def logger(hass, mock_config):
    return AgentLogger(hass, mock_config)


@pytest.fixture
def client(hass, mock_config, logger):
    return ChatClient(hass, mock_config, logger)


@pytest.mark.anyio
async def test_chat_client_complete_success(client, hass):
    """Test successful chat completion."""
    class SuccessResponse:
        def __init__(self):
            self.status_code = 200  # Real int

        async def aiter_lines(self):
            yield 'data: {"choices": [{"index": 0, "delta": {"content": "Hello"}}]}'
            yield 'data: [DONE]'

        async def aread(self):
            pass

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_http = MagicMock()
    mock_http.stream.return_value = SuccessResponse()

    with patch("custom_components.azure_openai_sdk_conversation.llm.chat_client.get_async_client"):
        client._http = mock_http  # ✅ Override fixture's real _http
        content, tokens = await client.complete([{"role": "user", "content": "Hi"}])
        assert content == "Hello"
        assert "total" in tokens


@pytest.mark.anyio
async def test_chat_client_timeout(client, hass):
    """Test chat client timeout."""
    mock_http = MagicMock()
    mock_http.stream.side_effect = httpx.TimeoutException("Timeout")  # ✅ Raises inside stream()

    with patch("custom_components.azure_openai_sdk_conversation.llm.chat_client.get_async_client"):
        client._http = mock_http  # ✅ Override fixture's real _http
        with pytest.raises(TimeoutError):
            await client.complete([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_chat_client_http_error(client, hass):
    """Test chat client HTTP error."""
    class ErrorResponse:
        def __init__(self):
            self.status_code = 401  # Real int ✅
            self.content = b"Unauthorized"

        async def aread(self):
            pass

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                message="401", request=MagicMock(), response=self
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_http = MagicMock()
    mock_http.stream.return_value = ErrorResponse()

    with patch("custom_components.azure_openai_sdk_conversation.llm.chat_client.get_async_client"):
        client._http = mock_http  # ✅ Override fixture's real _http
        with pytest.raises(httpx.HTTPStatusError):
            await client.complete([{"role": "user", "content": "Hi"}])
