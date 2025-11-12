from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from ..core.config import AgentConfig
from ..core.logger import AgentLogger
from .stream_parser import SSEStreamParser


class ResponsesClient:
    """Client for Azure OpenAI Responses API (o-series models)."""

    def __init__(
        self, hass: HomeAssistant, config: AgentConfig, logger: AgentLogger
    ) -> None:
        """Initialize the responses client."""
        self._logger = logger
        self._hass = hass
        self._config = config
        self._parser = SSEStreamParser(logger)

        # API version is determined by config, with a fallback for safety
        self.effective_api_version = config.api_version or "2024-02-15-preview"

        # Store base URL and headers for requests
        self._base_url = f"{config.api_base}/openai/deployments/{config.chat_model}"
        self._headers = {
            "Content-Type": "application/json",
            "api-key": config.api_key,
        }

        # Prepare HTTP client using HA's shared client
        self._http = get_async_client(self._hass, verify_ssl=config.ssl_verify)

    async def complete(
        self,
        messages: list[dict[str, str]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[callable] = None,
    ) -> tuple[str, dict[str, int]]:
        """Request completion from the model (no tools)."""
        payload = {
            "messages": messages,
            "temperature": self._config.temperature,
            "stream": True,
            self._config.token_param: self._config.max_tokens,
        }

        await self._logger.log_request(
            api="Responses",
            payload=payload,
            user_message=user_message,
            conversation_id=conversation_id,
        )

        return await self._stream_completion(
            payload=payload,
            conversation_id=conversation_id,
            first_chunk_event=first_chunk_event,
            track_callback=track_callback,
        )

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        track_callback: Optional[callable] = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Request completion with tool calling enabled."""
        payload = {
            "messages": messages,
            "temperature": self._config.temperature,
            "stream": True,
            self._config.token_param: self._config.max_tokens,
            "tools": tools,
        }

        await self._logger.log_request(
            api="Responses (with tools)",
            payload=payload,
            user_message=user_message,
            conversation_id=conversation_id,
        )

        return await self._stream_completion_with_tools(
            payload=payload,
            conversation_id=conversation_id,
            track_callback=track_callback,
        )

    async def _stream_completion(
        self,
        payload: dict[str, Any],
        conversation_id: Optional[str] = None,
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[callable] = None,
    ) -> tuple[str, dict[str, int]]:
        """
        Handle the streaming response for a regular completion.

        Returns:
            Tuple of (response_text, token_counts)
        """
        start_time = time.perf_counter()
        lines = []
        first_chunk = True

        try:
            async with self._http.stream(
                "POST",
                url=f"{self._base_url}/chat/completions",
                params={"api-version": self.effective_api_version},
                headers=self._headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if first_chunk:
                        if first_chunk_event:
                            first_chunk_event.set()
                        if track_callback:
                            track_callback()
                        first_chunk = False
                    lines.append(line)

            text_out, _, token_counts = self._parser.parse_stream(lines)

        except httpx.HTTPStatusError as err:
            await err.response.aread()
            self._logger.error(
                "Responses API error %d: %s",
                err.response.status_code,
                err.response.text,
            )
            raise

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        await self._logger.log_response(
            api="Responses",
            tokens=token_counts,
            assistant_response=text_out,
            conversation_id=conversation_id,
            execution_time_ms=execution_time_ms,
        )

        self._logger.debug(
            "Responses stream parse: text=%d chars, tokens=%s",
            len(text_out),
            token_counts,
        )

        return text_out, token_counts

    async def _stream_completion_with_tools(
        self,
        payload: dict[str, Any],
        conversation_id: Optional[str] = None,
        track_callback: Optional[callable] = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Handle streaming response for a tool-enabled completion.

        Returns:
            Tuple of (response_dict, token_counts)
        """
        start_time = time.perf_counter()
        lines = []
        first_chunk = True

        try:
            async with self._http.stream(
                "POST",
                url=f"{self._base_url}/chat/completions",
                params={"api-version": self.effective_api_version},
                headers=self._headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if first_chunk:
                        if track_callback:
                            track_callback()
                        first_chunk = False
                    lines.append(line)

            text_out, tool_calls_list, token_counts = self._parser.parse_stream(lines)

        except httpx.HTTPStatusError as err:
            await err.response.aread()
            self._logger.error(
                "Responses API error %d: %s",
                err.response.status_code,
                err.response.text,
            )
            raise

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        response_dict = {"content": text_out, "tool_calls": tool_calls_list}

        await self._logger.log_response(
            api="Responses (with tools)",
            tokens=token_counts,
            assistant_response=text_out,
            conversation_id=conversation_id,
            execution_time_ms=execution_time_ms,
        )

        self._logger.debug(
            "Responses stream parse complete: %d content chars, %d complete tool calls",
            len(text_out),
            len(tool_calls_list),
        )

        return response_dict, token_counts

    async def close(self) -> None:
        """Close the HTTP client."""
        # The client is managed by HA, no need to close it here.
        pass
