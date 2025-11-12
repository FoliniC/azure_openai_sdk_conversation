"""
Chat Completions API client for Azure OpenAI.

Handles:
- Streaming responses with SSE parsing
- Token counting from usage field
- Automatic retry with parameter fallback
- Tool calling with proper delta accumulation
- Early chunk notification
"""

from __future__ import annotations

import asyncio

from typing import Any, Optional, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

import httpx

from .stream_parser import SSEStreamParser
from .token_counter import TokenCounter

from ..core.config import AgentConfig
from ..core.logger import AgentLogger


class ChatClient:
    """Client for Azure OpenAI Chat Completions API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize Chat Completions client.

        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger
        self._http = get_async_client(hass)

        # API settings
        self._endpoint = config.api_base.rstrip("/")
        self._model = config.chat_model
        self._api_version = config.api_version
        self._timeout = config.api_timeout

        # Determine effective api_version and token_param
        self._effective_api_version = self._api_version
        self._token_param = self._determine_token_param()

        # Headers
        self._headers = {
            "api-key": config.api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        # Parser and counter
        self._parser = SSEStreamParser(logger=logger)
        self._counter = TokenCounter()

        self._logger.debug(
            "ChatClient initialized: model=%s, api_version=%s, token_param=%s",
            self._model,
            self._effective_api_version,
            self._token_param,
        )

    @property
    def effective_api_version(self) -> str:
        """Get the effective API version being used."""
        return self._effective_api_version

    def _determine_token_param(self) -> str:
        """
        Determine which token parameter to use based on api_version.

        Returns:
            "max_tokens" or "max_completion_tokens"
        """
        # Check if config has explicit token_param
        if hasattr(self._config, "token_param") and self._config.token_param:
            return self._config.token_param

        # Otherwise infer from api_version
        parts = self._api_version.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2].split("-")[0])

            # From 2025-01-01 onwards, use max_completion_tokens
            if (year, month, day) >= (2025, 1, 1):
                return "max_completion_tokens"
        except (ValueError, IndexError):
            pass

        return "max_tokens"

    async def complete(
        self,
        messages: list[dict[str, str]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[Callable[[], None]] = None,
    ) -> tuple[str, dict[str, int]]:
        """
        Complete a chat conversation with streaming.
        """
        url = f"{self._endpoint}/openai/deployments/{self._model}/chat/completions"

        # Build payload
        payload = {
            "messages": messages,
            "temperature": self._config.temperature,
            "stream": True,
            self._token_param: self._config.max_tokens,
        }

        # Log request if configured
        if self._logger.should_log_request():
            await self._logger.log_request(
                "Chat",
                payload,
                user_message=user_message,
                conversation_id=conversation_id,
            )

        # Attempt with current token_param, fallback if needed
        attempted = set()
        current_token_param = self._token_param

        while True:
            attempt_key = f"{self._effective_api_version}::{current_token_param}"
            if attempt_key in attempted:
                raise RuntimeError(
                    "Failed to complete chat after trying all parameter combinations"
                )
            attempted.add(attempt_key)

            # Update payload with current token param
            if current_token_param != self._token_param:
                payload.pop(self._token_param, None)
                payload[current_token_param] = self._config.max_tokens

            try:
                text_out, token_counts = await self._stream_completion(
                    url=url,
                    payload=payload,
                    conversation_id=conversation_id,
                    first_chunk_event=first_chunk_event,
                    track_callback=track_callback,
                )

                # Success - update for future requests
                self._token_param = current_token_param
                return text_out, token_counts

            except httpx.HTTPStatusError as err:
                # âœ… CORREZIONE: Leggi il body della risposta correttamente
                try:
                    # The response body should have been read in _stream_completion
                    error_text = err.response.content.decode("utf-8", errors="ignore")
                except Exception as read_err:
                    self._logger.warning(
                        "Could not read error response body (it may have been closed or already read): %r",
                        read_err,
                    )
                    error_text = f"HTTP {err.response.status_code}"

                self._logger.error(
                    "Chat API error %d: %s", err.response.status_code, error_text[:500]
                )

                if "Unsupported parameter: 'max_tokens'" in error_text:
                    self._logger.debug("Retrying with max_completion_tokens")
                    current_token_param = "max_completion_tokens"
                    continue

                elif "Unsupported parameter: 'max_completion_tokens'" in error_text:
                    self._logger.debug("Retrying with max_tokens")
                    current_token_param = "max_tokens"
                    continue

                else:
                    # Can't retry, re-raise
                    raise

            except httpx.TimeoutException as err:
                self._logger.error(
                    "Request to Azure OpenAI timed out after %ds: %s",
                    self._timeout,
                    err,
                )
                raise TimeoutError(
                    f"Request timed out after {self._timeout}s. "
                    "You can increase the timeout in the integration options."
                ) from err

    async def _stream_completion(
        self,
        url: str,
        payload: dict[str, Any],
        conversation_id: Optional[str],
        first_chunk_event: Optional[asyncio.Event],
        track_callback: Optional[Callable[[], None]],
    ) -> tuple[str, dict[str, int]]:
        """
        Execute streaming completion with SSE parsing.

        Returns:
            Tuple of (text, token_counts)
        """
        import time

        text_out = ""
        token_counts = {"prompt": 0, "completion": 0, "total": 0}
        start_time = time.perf_counter()

        async with self._http.stream(
            "POST",
            url,
            params={"api-version": self._effective_api_version},
            headers=self._headers,
            json=payload,
            timeout=self._timeout,
        ) as resp:
            # Check for error
            if resp.status_code >= 400:
                await resp.aread()
                resp.raise_for_status()

            # âœ… CORRECTED: Collect ALL SSE lines before parsing
            lines = []
            first_chunk = True

            async for line in resp.aiter_lines():
                if first_chunk and track_callback:
                    track_callback()
                    first_chunk = False

                lines.append(line)

            # --- START: Log raw SSE response ---
            self._logger.warning(
                "\n--- Raw LLM SSE Response (No Tools) ---\n%s\n--- End of Raw Response ---",
                "\n".join(lines),
            )
            # --- END: Log raw SSE response ---

            # âœ… CORRECTED: Pass list to parser (not async generator)
            text_out, _, token_counts = self._parser.parse_stream(lines)

            # If no token counts from usage, estimate
            if token_counts["total"] == 0:
                estimated = self._counter.estimate_tokens(
                    prompt_messages=payload["messages"],
                    completion_text=text_out,
                )
                token_counts.update(estimated)
                self._logger.debug("Estimated token counts: %s", token_counts)

            execution_time_ms = (time.perf_counter() - start_time) * 1000
            # Log response if configured
            if self._logger.should_log_response():
                await self._logger.log_response(
                    api="Chat",
                    tokens=token_counts,
                    assistant_response=text_out,
                    conversation_id=conversation_id,
                    execution_time_ms=execution_time_ms,
                )
                self._logger.debug(
                    "Chat stream parse: text=%d chars, tokens=%d",
                    len(text_out),
                    token_counts.get("total", 0),
                )

            return text_out, token_counts

    # Nel metodo complete_with_tools, modifica la gestione degli errori HTTP:

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[Callable[[], None]] = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Complete with tool calling support.
        """
        url = f"{self._endpoint}/openai/deployments/{self._model}/chat/completions"

        # Build payload with tools
        payload = {
            "messages": messages,
            "temperature": self._config.temperature,
            "stream": True,
            self._token_param: self._config.max_tokens,
            "tools": tools,
            "tool_choice": "auto",
        }

        # Log request if configured
        if self._logger.should_log_request():
            await self._logger.log_request(
                "Chat (with tools)",
                payload,
                user_message=user_message,
                conversation_id=conversation_id,
            )

        # Execute with retry logic
        attempted = set()
        current_token_param = self._token_param

        while True:
            attempt_key = f"{self._effective_api_version}::{current_token_param}"
            if attempt_key in attempted:
                raise RuntimeError(
                    "Failed to complete chat after trying all parameter combinations"
                )
            attempted.add(attempt_key)

            # Update payload with current token param
            if current_token_param != self._token_param:
                payload.pop(self._token_param, None)
                payload[current_token_param] = self._config.max_tokens

            try:
                response_dict, token_counts = await self._stream_completion_with_tools(
                    url=url,
                    payload=payload,
                    conversation_id=conversation_id,
                    first_chunk_event=first_chunk_event,
                    track_callback=track_callback,
                )

                # Success - update for future requests
                self._token_param = current_token_param
                return response_dict, token_counts

            except httpx.HTTPStatusError as err:
                # âœ… CORREZIONE: Leggi il body della risposta correttamente
                try:
                    # The response body should have been read in _stream_completion_with_tools
                    error_text = err.response.content.decode("utf-8", errors="ignore")
                except Exception as read_err:
                    # Se non riesci a leggere, usa il messaggio di default
                    self._logger.warning(
                        "Could not read error response body (it may have been closed or already read): %r",
                        read_err,
                    )
                    error_text = f"HTTP {err.response.status_code}"

                self._logger.error(
                    "Chat API error %d: %s", err.response.status_code, error_text[:500]
                )

                # Check if we can retry with different parameter
                if "Unsupported parameter: 'max_tokens'" in error_text:
                    self._logger.debug("Retrying with max_completion_tokens")
                    current_token_param = "max_completion_tokens"
                    continue

                elif "Unsupported parameter: 'max_completion_tokens'" in error_text:
                    self._logger.debug("Retrying with max_tokens")
                    current_token_param = "max_tokens"
                    continue

                else:
                    # Can't retry, re-raise
                    raise

            except httpx.TimeoutException as err:
                self._logger.error(
                    "Request to Azure OpenAI timed out after %ds: %s",
                    self._timeout,
                    err,
                )
                raise TimeoutError(
                    f"Request timed out after {self._timeout}s. "
                    "You can increase the timeout in the integration options."
                ) from err

    async def _stream_completion_with_tools(
        self,
        url: str,
        payload: dict[str, Any],
        conversation_id: Optional[str],
        first_chunk_event: Optional[asyncio.Event],
        track_callback: Optional[Callable[[], None]],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Execute streaming completion with tool calling support.

        Returns:
            Tuple of (response_dict, token_counts)
        """
        import time

        text_out = ""
        token_counts = {"prompt": 0, "completion": 0, "total": 0}
        start_time = time.perf_counter()

        async with self._http.stream(
            "POST",
            url,
            params={"api-version": self._effective_api_version},
            headers=self._headers,
            json=payload,
            timeout=self._timeout,
        ) as resp:
            # Check for error
            if resp.status_code >= 400:
                await resp.aread()
                resp.raise_for_status()

            # âœ… CORRECTED: Collect ALL SSE lines before parsing
            lines = []
            first_chunk = True

            async for line in resp.aiter_lines():
                if first_chunk and track_callback:
                    track_callback()
                    first_chunk = False

                lines.append(line)

            # --- START: Log raw SSE response ---
            self._logger.warning(
                "\n--- Raw LLM SSE Response (With Tools) ---\n%s\n--- End of Raw Response ---",
                "\n".join(lines),
            )
            # --- END: Log raw SSE response ---

            # âœ… CORRECTED: Pass list to parser and get complete tool calls
            text_out, tool_calls_list, token_counts = self._parser.parse_stream(lines)

            # Log SSE collection if configured
            if self._logger.should_log_response():
                self._logger.debug(
                    "Chat SSE collected %d lines for parsing",
                    len(lines),
                )

            # If no token counts from usage, estimate
            if token_counts["total"] == 0:
                estimated = self._counter.estimate_tokens(
                    prompt_messages=payload["messages"],
                    completion_text=text_out,
                )
                token_counts.update(estimated)
                self._logger.debug("Estimated token counts: %s", token_counts)

            # Build response dict
            response_dict = {
                "text": text_out,
                "tool_calls": tool_calls_list if tool_calls_list else None,
            }

            execution_time_ms = (time.perf_counter() - start_time) * 1000
            # Log response if configured
            if self._logger.should_log_response():
                await self._logger.log_response(
                    api="Chat (with tools)",
                    tokens=token_counts,
                    assistant_response=text_out,
                    conversation_id=conversation_id,
                    execution_time_ms=execution_time_ms,
                )

            if tool_calls_list:
                self._logger.info(
                    "Tool calls requested: %d, tokens: %d total",
                    len(tool_calls_list),
                    token_counts.get("total", 0),
                )

            return response_dict, token_counts

    async def close(self) -> None:
        """Clean up resources."""
        # httpx client is managed by HA, nothing to close
        pass
