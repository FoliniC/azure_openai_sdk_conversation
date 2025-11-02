"""
Chat Completions API client for Azure OpenAI.

Handles:
- Streaming responses with SSE parsing
- Token counting from usage field
- Automatic retry with parameter fallback
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
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[Callable[[], None]] = None,
    ) -> tuple[str, dict[str, int]]:
        """
        Complete a chat conversation with streaming.
        
        Args:
            messages: List of message dicts with role and content
            conversation_id: Optional conversation ID for logging
            first_chunk_event: Event to set when first chunk arrives
            track_callback: Callback to invoke on first chunk
            
        Returns:
            Tuple of (response_text, token_counts)
            where token_counts = {"prompt": int, "completion": int, "total": int}
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
            self._logger.log_request("Chat", payload)
        
        # Attempt with current token_param, fallback if needed
        attempted = set()
        current_token_param = self._token_param
        
        while True:
            attempt_key = f"{self._effective_api_version}::{current_token_param}"
            if attempt_key in attempted:
                # Already tried this combination, give up
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
                # Check if we can retry with different parameter
                error_body = err.response.text
                
                if "Unsupported parameter: 'max_tokens'" in error_body:
                    self._logger.debug("Retrying with max_completion_tokens")
                    current_token_param = "max_completion_tokens"
                    continue
                
                elif "Unsupported parameter: 'max_completion_tokens'" in error_body:
                    self._logger.debug("Retrying with max_tokens")
                    current_token_param = "max_tokens"
                    continue
                
                else:
                    # Can't retry, re-raise
                    raise
            except httpx.TimeoutException as err:
                self._logger.error(
                    "Request to Azure OpenAI timed out after %ds: %s", self._timeout, err
                )
                raise TimeoutError(
                    f"Request timed out after {self._timeout}s. You can increase the timeout in the integration options."
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
        text_out = ""
        token_counts = {"prompt": 0, "completion": 0, "total": 0}
        first_chunk_notified = False
        
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
                resp.raise_for_status()
            
            # Collect SSE samples if debug enabled
            sse_samples = []
            collect_samples = (
                self._logger.should_log_response() or self._config.debug_sse
            )
            max_samples = (
                self._config.debug_sse_lines
                if self._config.debug_sse
                else self._config.log_max_sse_lines
            )
            
            # Parse SSE stream
            async for event_type, event_data in self._parser.parse_stream(
                resp.aiter_lines()
            ):
                # Collect sample
                if collect_samples and len(sse_samples) < max_samples:
                    sse_samples.append(f"{event_type}: {str(event_data)[:200]}")
                
                # Handle different event types
                if event_type == "delta":
                    # Text delta
                    delta_text = self._extract_text_from_delta(event_data)
                    if delta_text:
                        text_out += delta_text
                        
                        # Notify on first chunk
                        if not first_chunk_notified:
                            # Only set event if we have received some actual content
                            if text_out.strip():
                                first_chunk_notified = True
                                if track_callback:
                                    track_callback()
                                if first_chunk_event:
                                    first_chunk_event.set()
                
                elif event_type == "usage":
                    # Token usage information
                    usage = event_data if isinstance(event_data, dict) else {}
                    token_counts["prompt"] = usage.get(
                        "prompt_tokens", usage.get("input_tokens", 0)
                    )
                    token_counts["completion"] = usage.get(
                        "completion_tokens", usage.get("output_tokens", 0)
                    )
                    token_counts["total"] = usage.get(
                        "total_tokens",
                        token_counts["prompt"] + token_counts["completion"],
                    )
                
                elif event_type == "error":
                    # Error event
                    error_msg = event_data.get("message", str(event_data))
                    self._logger.error("Chat stream error: %s", error_msg)
                    raise RuntimeError(f"Chat stream error: {error_msg}")
            
            # Log SSE samples if collected
            if sse_samples:
                self._logger.debug(
                    "Chat SSE samples (%d lines):\n%s",
                    len(sse_samples),
                    "\n".join(sse_samples),
                )
        
        # If no token counts from usage, estimate
        if token_counts["total"] == 0:
            estimated = self._counter.estimate_tokens(
                prompt_messages=payload["messages"],
                completion_text=text_out,
            )
            token_counts.update(estimated)
            self._logger.debug("Estimated token counts: %s", token_counts)
        
        # Log response if configured
        if self._logger.should_log_response():
            self._logger.log_response("Chat", text_out, token_counts)
        
        return text_out, token_counts
    
    @staticmethod
    def _extract_text_from_delta(data: Any) -> str:
        """
        Extract text from delta event data.
        
        Handles various response formats:
        - {"choices": [{"delta": {"content": "text"}}]}
        - {"delta": {"content": "text"}}
        - {"content": "text"}
        - "text"
        """
        if isinstance(data, str):
            return data
        
        if not isinstance(data, dict):
            return ""
        
        # Try choices[0].delta.content
        choices = data.get("choices", [])
        if choices and isinstance(choices, list):
            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if isinstance(content, str):
                return content
        
        # Try delta.content
        delta = data.get("delta", {})
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                return content
        
        # Try direct content
        content = data.get("content")
        if isinstance(content, str):
            return content
        
        return ""
    
    async def close(self) -> None:
        """Clean up resources."""
        # httpx client is managed by HA, nothing to close
        pass