"""
Configurable logger for the conversation agent.

Provides granular logging based on configured log level and flags.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import AgentConfig


class AgentLogger:
    """Configurable logger wrapper."""

    def __init__(self, config: AgentConfig) -> None:
        """
        Initialize logger with configuration.

        Args:
            config: Agent configuration with log settings
        """
        self._config = config
        self._logger = logging.getLogger(__name__)

        # Determine log level
        self._level = self._parse_level(config.log_level)

    @staticmethod
    def _parse_level(level_str: str) -> int:
        """Parse log level string to logging constant."""
        level_lower = level_str.lower()

        if level_lower == "none":
            return logging.CRITICAL + 1  # Effectively disable
        elif level_lower == "error":
            return logging.ERROR
        elif level_lower == "info":
            return logging.INFO
        elif level_lower == "trace" or level_lower == "debug":
            return logging.DEBUG

        return logging.ERROR  # Default

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message if level permits."""
        if self._level <= logging.DEBUG:
            self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message if level permits."""
        if self._level <= logging.INFO:
            self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message if level permits."""
        if self._level <= logging.WARNING:
            self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log error message (always logged)."""
        if self._level <= logging.ERROR:
            self._logger.error(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        if self._level <= logging.ERROR:
            self._logger.exception(msg, *args, **kwargs)

    def should_log_request(self) -> bool:
        """Check if request payloads should be logged."""
        return self._level <= logging.INFO and self._config.log_payload_request

    def should_log_response(self) -> bool:
        """Check if response payloads should be logged."""
        return self._level <= logging.INFO and self._config.log_payload_response

    def should_log_system_message(self) -> bool:
        """Check if system messages should be logged."""
        return self._level <= logging.INFO and self._config.log_system_message

    def log_request(self, api: str, payload: dict) -> None:
        """
        Log API request payload.

        Args:
            api: API name (Chat, Responses, etc.)
            payload: Request payload dict
        """
        if not self.should_log_request():
            return

        payload_str = self._safe_json(payload, self._config.log_max_payload_chars)
        self.info("%s API request payload:\n%s", api, payload_str)

    def log_response(self, api: str, text: str, tokens: dict[str, int]) -> None:
        """
        Log API response.

        Args:
            api: API name
            text: Response text
            tokens: Token counts dict
        """
        if not self.should_log_response():
            return

        truncated = self._truncate(text, self._config.log_max_payload_chars)
        self.info(
            "%s API response (%d tokens):\n%s",
            api,
            tokens.get("total", 0),
            truncated,
        )

    @staticmethod
    def _safe_json(obj: Any, max_len: int) -> str:
        """Convert object to JSON string, safely handling errors."""
        import json

        try:
            s = json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            try:
                s = str(obj)
            except Exception:
                s = "<unserializable>"

        if len(s) > max_len:
            return f"{s[:max_len]}... (truncated, total {len(s)} chars)"

        return s

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_len:
            return text

        return f"{text[:max_len]}... (truncated, total {len(text)} chars)"
