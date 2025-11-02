"""
Responses API client for Azure OpenAI (reasoning models).

Handles:
- Streaming responses with messages/instructions format
- Token counting from usage field
- Automatic fallback between input/messages formats
- Version compatibility (2025-03-01-preview+)
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


class ResponsesClient:
    """Client for Azure OpenAI Responses API (reasoning models)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize Responses API client.

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
        self._api_version = self._ensure_min_version(
            config.api_version, "2025-03-01-preview"
        )
        self._timeout = config.api_timeout

        # Determine token parameter for Responses
        self._token_param = self._determine_token_param()

        # Track format preference (input vs messages+instructions)
        self._use_messages_format = False

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
            "ResponsesClient initialized: model=%s, api_version=%s, token_param=%s",
            self._model,
            self._api_version,
            self._token_param,
        )

    @property
    def effective_api_version(self) -> str:
        """Get the effective API version being used."""
        return self._api_version

    @staticmethod
    def _ensure_min_version(version: str, minimum: str) -> str:
        """Ensure version is at least minimum."""

        def parse_version(v: str) -> tuple[int, int, int]:
            parts = v.split("-")[0].split("-preview")[0].split(".")
            if len(parts) < 3:
                parts = v.split("-")[:3]
            try:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                return (1900, 1, 1)

        v_tuple = parse_version(version)
        m_tuple = parse_version(minimum)

        return version if v_tuple >= m_tuple else minimum

    def _determine_token_param(self) -> str:
        """
        Determine token parameter for Responses API.

        Returns:
            "max_output_tokens" for 2025-03-01+, else "max_completion_tokens"
        """
        parts = self._api_version.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2].split("-")[0])

            if (year, month, day) >= (2025, 3, 1):
                return "max_output_tokens"
        except (ValueError, IndexError):
            pass

        return "max_completion_tokens"

    async def complete(
        self,
        messages: list[dict[str, str]],
        conversation_id: Optional[str] = None,
        first_chunk_event: Optional[asyncio.Event] = None,
        track_callback: Optional[Callable[[], None]] = None,
    ) -> tuple[str, dict[str, int]]:
        """
        Complete a conversation with Responses API.

        Args:
            messages: List of message dicts (system, user messages)
            conversation_id: Optional conversation ID
            first_chunk_event: Event to set on first chunk
            track_callback: Callback to invoke on first chunk

        Returns:
            Tuple of (response_text, token_counts)
        """
        url = f"{self._endpoint}/openai/responses"

        # Extract system message and user messages
        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        # Try with current format preference
        attempted = set()
        current_format = "messages" if self._use_messages_format else "input"
        current_token_param = self._token_param

        while True:
            attempt_key = (
                f"{self._api_version}::{current_token_param}::{current_format}"
            )
            if attempt_key in attempted:
                # Tried all combinations
                raise RuntimeError(
                    "Failed to complete with Responses API after all attempts"
                )
            attempted.add(attempt_key)

            # Build payload
            payload = self._build_payload(
                system_msg=system_msg,
                user_messages=user_messages,
                use_messages=current_format == "messages",
                token_param=current_token_param,
            )

            try:
                text_out, token_counts = await self._stream_completion(
                    url=url,
                    payload=payload,
                    conversation_id=conversation_id,
                    first_chunk_event=first_chunk_event,
                    track_callback=track_callback,
                )

                # Success - remember preferences
                self._use_messages_format = current_format == "messages"
                self._token_param = current_token_param

                return text_out, token_counts

            except httpx.HTTPStatusError as err:
                error_body = err.response.text

                # Try switching token parameter
                if "Unsupported parameter" in error_body:
                    if (
                        "max_output_tokens" in error_body
                        and current_token_param != "max_completion_tokens"
                    ):
                        self._logger.debug("Retrying with max_completion_tokens")
                        current_token_param = "max_completion_tokens"
                        continue
                    elif (
                        "max_completion_tokens" in error_body
                        and current_token_param != "max_output_tokens"
                    ):
                        self._logger.debug("Retrying with max_output_tokens")
                        current_token_param = "max_output_tokens"
                        continue

                # Try switching format
                if current_format == "input" and not self._use_messages_format:
                    self._logger.debug("Retrying with messages+instructions format")
                    current_format = "messages"
                    continue

                # Can't retry
                raise
            except httpx.TimeoutException as err:
                self._logger.error(
                    "Request to Azure OpenAI timed out after %ds: %s",
                    self._timeout,
                    err,
                )
                raise TimeoutError(
                    f"Request timed out after {self._timeout}s. You can increase the timeout in the integration options."
                ) from err

    def _build_payload(
        self,
        system_msg: str,
        user_messages: list[dict[str, str]],
        use_messages: bool,
        token_param: str,
    ) -> dict[str, Any]:
        """Build request payload for Responses API."""

        # Convert messages to input format
        def to_input_items(msgs: list[dict[str, str]]) -> list[dict[str, Any]]:
            items = []
            for msg in msgs:
                items.append(
                    {
                        "role": msg["role"],
                        "content": [{"type": "input_text", "text": msg["content"]}],
                    }
                )
            return items

        payload = {
            "model": self._model,
            token_param: self._config.max_tokens,
            "temperature": self._config.temperature,
            "stream": True,
            "modalities": ["text"],
            "text": {"format": "text"},
        }

        if use_messages:
            # messages + instructions format
            payload["messages"] = to_input_items(user_messages)
            payload["instructions"] = system_msg
        else:
            # input format (system + user as input)
            all_messages = [{"role": "system", "content": system_msg}] + user_messages
            payload["input"] = to_input_items(all_messages)

        return payload

    async def _stream_completion(
        self,
        url: str,
        payload: dict[str, Any],
        conversation_id: Optional[str],
        first_chunk_event: Optional[asyncio.Event],
        track_callback: Optional[Callable[[], None]],
    ) -> tuple[str, dict[str, int]]:
        """Execute streaming completion with SSE parsing."""
        text_out = ""
        token_counts = {"prompt": 0, "completion": 0, "total": 0}
        first_chunk_notified = False

        # Log request if configured
        if self._logger.should_log_request():
            self._logger.log_request("Responses", payload)

        async with self._http.stream(
            "POST",
            url,
            params={"api-version": self._api_version},
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
                    delta_text = self._extract_text_from_data(event_data)
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
                    # Token usage
                    usage = event_data if isinstance(event_data, dict) else {}
                    token_counts["prompt"] = usage.get(
                        "input_tokens", usage.get("prompt_tokens", 0)
                    )
                    token_counts["completion"] = usage.get(
                        "output_tokens", usage.get("completion_tokens", 0)
                    )
                    token_counts["total"] = usage.get(
                        "total_tokens",
                        token_counts["prompt"] + token_counts["completion"],
                    )

                elif event_type == "error":
                    error_msg = event_data.get("message", str(event_data))
                    self._logger.error("Responses stream error: %s", error_msg)
                    raise RuntimeError(f"Responses stream error: {error_msg}")

            # Log SSE samples
            if sse_samples:
                self._logger.debug(
                    "Responses SSE samples (%d lines):\n%s",
                    len(sse_samples),
                    "\n".join(sse_samples),
                )

        # Estimate tokens if not provided
        if token_counts["total"] == 0:
            estimated = self._counter.estimate_tokens(
                prompt_messages=payload.get("messages", payload.get("input", [])),
                completion_text=text_out,
            )
            token_counts.update(estimated)
            self._logger.debug("Estimated token counts: %s", token_counts)

        # Log response
        if self._logger.should_log_response():
            self._logger.log_response("Responses", text_out, token_counts)

        return text_out, token_counts

    @staticmethod
    def _extract_text_from_data(data: Any) -> str:
        """
        Extract text from response data.

        Handles various formats:
        - {"delta": {"text": "..."}}
        - {"output": [{"content": [{"text": "..."}]}]}
        - {"text": "..."}
        - "text"
        """
        if isinstance(data, str):
            return data

        if not isinstance(data, dict):
            return ""

        # Try delta.text
        delta = data.get("delta", {})
        if isinstance(delta, dict):
            text = delta.get("text")
            if isinstance(text, str):
                return text

        # Try output[0].content[0].text
        output = data.get("output", [])
        if isinstance(output, list) and output:
            content = output[0].get("content", [])
            if isinstance(content, list) and content:
                text = content[0].get("text")
                if isinstance(text, str):
                    return text

        # Try direct text
        text = data.get("text")
        if isinstance(text, str):
            return text

        # Recursive search in nested structures
        def search_text(obj: Any) -> Optional[str]:
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                for key in ["text", "content", "delta"]:
                    if key in obj:
                        result = search_text(obj[key])
                        if result:
                            return result
            if isinstance(obj, list):
                for item in obj:
                    result = search_text(item)
                    if result:
                        return result
            return None

        return search_text(data) or ""

    async def close(self) -> None:
        """Clean up resources."""
        pass
