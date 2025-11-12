"""
Custom logger for the conversation agent.

Provides structured logging for requests, responses, and other events, with
options for custom file logging of payloads.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from .config import AgentConfig, async_log_to_file

_LOGGER = logging.getLogger(__name__)


class AgentLogger:
    """A logger for the conversation agent with configurable levels and payload logging."""

    def __init__(self, hass: HomeAssistant, config: AgentConfig) -> None:
        """Initialize the agent logger."""
        self._hass = hass
        self._config = config
        self._level = self._parse_level(config.log_level)
        self._logger = logging.getLogger(__name__)

    def _parse_level(self, level_str: str) -> int:
        """Parse log level string to logging level constant."""
        return {
            "none": logging.NOTSET,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "info": logging.INFO,
            "debug": logging.DEBUG,
            "trace": logging.DEBUG,  # Map trace to debug
        }.get(level_str.lower(), logging.ERROR)

    def _safe_json(self, data: dict, max_len: int) -> str:
        """Safely convert dict to JSON string, truncating if necessary."""
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            if max_len > 0 and len(json_str) > max_len:
                return (
                    f"{json_str[:max_len]}... (truncated, total {len(json_str)} chars)"
                )
            return json_str
        except TypeError:
            return "<failed to serialize payload>"

    def should_log(self, level: int) -> bool:
        """Check if a message at a given level should be logged."""
        return self._level != logging.NOTSET and self._level <= level

    def should_log_request(self) -> bool:
        """Check if request payloads should be logged."""
        return self._config.log_payload_request

    def should_log_response(self) -> bool:
        """Check if response payloads should be logged."""
        return self._config.log_payload_response

    def should_log_system_message(self) -> bool:
        """Check if the system message should be logged."""
        return self._config.log_system_message

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        if self.should_log(logging.ERROR):
            self._logger.error(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        if self.should_log(logging.WARNING):
            self._logger.warning(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        if self.should_log(logging.INFO):
            self._logger.info(msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        if self.should_log(logging.DEBUG):
            self._logger.debug(msg, *args, **kwargs)

    async def log_system_message(
        self,
        system_message: str,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Log the system message, either to the main log or a custom file."""
        if not self.should_log_system_message():
            return

        if self._config.payload_log_path:
            structured_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "system_message",
                "conversation_id": conversation_id,
                "payload_length": len(system_message),
                "payload": system_message,
            }
            await async_log_to_file(
                self._hass, self._config.payload_log_path, structured_log
            )
            self.warning(
                "System message for conversation %s logged to custom file.",
                conversation_id,
            )
        else:
            self.info("System message:\n%s", system_message)

    async def log_request(
        self,
        api: str,
        payload: dict,
        user_message: str,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Log an API request payload."""
        if not self.should_log_request():
            return

        payload_str = self._safe_json(payload, 0)  # Full payload for custom log

        if self._config.payload_log_path:
            structured_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "request",
                "user_message": user_message,
                "api": api,
                "conversation_id": conversation_id,
                "payload_length": len(payload_str),
                "payload": payload,
            }
            await async_log_to_file(
                self._hass, self._config.payload_log_path, structured_log
            )
            self.warning(
                "Request payload for conversation %s logged to custom file.",
                conversation_id,
            )
        else:
            # Fallback to old behavior
            truncated_payload = self._safe_json(
                payload, self._config.log_max_payload_chars
            )
            self.info("%s API request payload:\n%s", api, truncated_payload)

    async def log_delegated_action(
        self,
        conversation_id: Optional[str],
        user_message: str,
        agent_name: str,
        response: str,
        execution_time_ms: float,
    ) -> None:
        """Log an action delegated to another agent."""
        if not self._config.payload_log_path:
            return

        structured_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "delegated_action",
            "conversation_id": conversation_id,
            "user_message": user_message,
            "handler": agent_name,
            "assistant_response": response,
            "execution_time_ms": round(execution_time_ms, 1),
        }
        await async_log_to_file(
            self._hass, self._config.payload_log_path, structured_log
        )
        self.warning(
            "Delegated action for conversation %s logged to custom file.",
            conversation_id,
        )

    async def log_local_action(
        self,
        conversation_id: Optional[str],
        user_message: str,
        action: str,
        entities: list[str],
        response: str,
        execution_time_ms: float,
    ) -> None:
        """Log a locally handled action."""
        if not self._config.payload_log_path:
            return

        structured_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "local_action",
            "conversation_id": conversation_id,
            "user_message": user_message,
            "handler": "local_intent",
            "action_details": {
                "action": action,
                "entities": entities,
            },
            "assistant_response": response,
            "execution_time_ms": round(execution_time_ms, 1),
        }
        await async_log_to_file(
            self._hass, self._config.payload_log_path, structured_log
        )
        self.warning(
            "Local action for conversation %s logged to custom file.",
            conversation_id,
        )

    async def log_response(
        self,
        api: str,
        tokens: dict[str, int],
        assistant_response: str,
        conversation_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
    ) -> None:
        """Log an API response."""
        if not self.should_log_response():
            return

        if self._config.payload_log_path:
            structured_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "response",
                "assistant_response": assistant_response,
                "api": api,
                "conversation_id": conversation_id,
                "response_length": len(assistant_response),
                "execution_time_ms": round(execution_time_ms, 1)
                if execution_time_ms
                else None,
                "tokens": tokens,
            }
            await async_log_to_file(
                self._hass, self._config.payload_log_path, structured_log
            )
            self.warning(
                "Response payload for conversation %s logged to custom file (exec_time=%.1fms).",
                conversation_id,
                execution_time_ms or 0,
            )
        else:
            # Fallback to old behavior
            total_tokens = tokens.get("total", 0)
            self.info(
                "%s API response (%d tokens):\n%s",
                api,
                total_tokens,
                assistant_response,
            )
