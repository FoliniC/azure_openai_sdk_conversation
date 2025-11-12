"""
Agent configuration management.

Centralizes all configuration access and provides type-safe getters.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
import logging

from homeassistant.core import HomeAssistant

from .. import const
from ..const import (
    DOMAIN,
    CONF_STATS_ENABLE,
    CONF_STATS_OVERRIDE_MODE,
    STATS_OVERRIDE_DEFAULT,
    STATS_OVERRIDE_ENABLE,
    STATS_OVERRIDE_DISABLE,
    CONF_STATS_AGGREGATED_FILE,
    CONF_STATS_AGGREGATION_INTERVAL,
    CONF_PAYLOAD_LOG_PATH,
    DEFAULT_LOG_MAX_SSE_LINES,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """
    Configuration for the conversation agent.

    This class provides type-safe access to all configuration values,
    with sensible defaults and validation.
    """

    # Core settings
    hass: HomeAssistant

    # Azure OpenAI settings
    api_key: str
    api_base: str
    chat_model: str
    api_version: str

    # Model parameters
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 512
    api_timeout: int = 30
    ssl_verify: bool = True
    reasoning_effort: str = "medium"

    # System prompt
    system_prompt: str = "You are a helpful assistant for Home Assistant."

    # Token parameter (max_tokens | max_completion_tokens | max_output_tokens)
    token_param: str = "max_tokens"

    # Responses API mode (auto | chat | responses)
    force_responses_mode: str = "auto"

    # Logging
    log_level: str = "error"
    log_payload_request: bool = False
    log_payload_response: bool = False
    log_system_message: bool = False
    log_max_payload_chars: int = 12000
    log_max_sse_lines: int = DEFAULT_LOG_MAX_SSE_LINES
    payload_log_path: Optional[str] = None
    debug_sse: bool = False
    debug_sse_lines: int = 10

    # Early wait / timeout
    early_wait_enable: bool = True
    early_wait_seconds: int = 5

    # Vocabulary / text normalization
    vocabulary_enable: bool = True
    synonyms_file: Optional[str] = None

    # Local intent handling
    local_intent_enable: bool = True

    # Utterances logging
    log_utterances: bool = True
    utterances_log_path: str = ".storage/azure_openai_conversation_utterances.log"

    # Statistics
    stats_enable: bool = False
    stats_aggregated_file: str = ".storage/azure_openai_stats_aggregated.json"
    stats_aggregation_interval: int = 60  # minutes

    # MCP Server
    mcp_enabled: bool = True
    mcp_ttl_seconds: int = 3600

    # Sliding Window Configuration
    sliding_window_enable: bool = True
    sliding_window_max_tokens: int = 4000
    sliding_window_preserve_system: bool = True

    # Tool Calling
    tools_enable: bool = True
    tools_whitelist: str = "light,switch,climate,cover,fan,media_player,lock,vacuum"
    tools_max_iterations: int = 5
    tools_max_calls_per_minute: int = 30
    tools_parallel_execution: bool = False
    # Web search
    web_search_enable: bool = False
    bing_api_key: Optional[str] = None
    bing_endpoint: str = "https://api.bing.microsoft.com/v7.0/search"
    bing_max_results: int = 5
    web_search_context_size: int = 2000

    # Entity exposure
    exposed_entities_limit: int = 500

    @classmethod
    def from_dict(cls, hass: HomeAssistant, data: dict[str, Any]) -> AgentConfig:
        """
        Create configuration from dictionary (config entry data + options).

        Args:
            hass: Home Assistant instance
            data: Combined data from config_entry.data and config_entry.options

        Returns:
            AgentConfig instance with all settings
        """

        # Helper to safely get values with defaults
        def get_str(key: str, default: str) -> str:
            val = data.get(key)
            return str(val).strip() if val else default

        def get_int(key: str, default: int) -> int:
            val = data.get(key)
            if isinstance(val, bool):
                return int(val)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
                try:
                    return int(float(val.strip()))
                except (ValueError, AttributeError):
                    return default
            return default

        def get_float(key: str, default: float) -> float:
            val = data.get(key)
            if isinstance(val, bool):
                return float(int(val))
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return float(val.strip())
                except (ValueError, AttributeError):
                    return default
            return default

        def get_bool(key: str, default: bool) -> bool:
            val = data.get(key)
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return val != 0
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("1", "true", "on", "yes", "y", "si", "s", "sÃ¬"):
                    return True
                if v in ("0", "false", "off", "no", "n"):
                    return False
            return default

        def resolve_path(path: Optional[str], default: str) -> str:
            """Resolve a path relative to HA config directory."""
            if not path:
                return hass.config.path(default)

            p = str(path).strip()
            if not os.path.isabs(p):
                p = hass.config.path(p)

            # If it's a directory, append default filename
            try:
                is_dir = os.path.isdir(p)
            except Exception:
                is_dir = False

            if is_dir or p.endswith(("/", "\\")):
                return os.path.join(p, os.path.basename(default))

            return p

        # --- Statistics ---
        def _get_stats_enable() -> bool:
            override_mode = get_str(CONF_STATS_OVERRIDE_MODE, STATS_OVERRIDE_DEFAULT)
            if override_mode == STATS_OVERRIDE_ENABLE:
                return True
            if override_mode == STATS_OVERRIDE_DISABLE:
                return False

            # Default mode: use global config
            global_config = hass.data.get(DOMAIN, {}).get("global_config", {})
            return global_config.get(CONF_STATS_ENABLE, False)

        return cls(
            hass=hass,
            # Required Azure settings
            api_key=get_str("api_key", ""),
            api_base=get_str("api_base", "").rstrip("/"),
            chat_model=get_str("chat_model", "gpt-4o-mini"),
            api_version=get_str("api_version", "2025-03-01-preview"),
            # Model parameters
            temperature=get_float("temperature", 0.7),
            top_p=get_float("top_p", 1.0),
            max_tokens=get_int("max_tokens", 512),
            api_timeout=get_int("api_timeout", 30),
            ssl_verify=get_bool("ssl_verify", True),
            reasoning_effort=get_str("reasoning_effort", "medium"),
            # System prompt
            system_prompt=get_str(
                "system_prompt", get_str("prompt", "You are a helpful assistant.")
            ),
            # Token parameter
            token_param=get_str("token_param", "max_tokens"),
            # Mode
            force_responses_mode=get_str("force_responses_mode", "auto"),
            # Logging
            log_level=get_str("log_level", "error"),
            log_payload_request=get_bool("log_payload_request", False),
            log_payload_response=get_bool("log_payload_response", False),
            log_system_message=get_bool("log_system_message", False),
            log_max_payload_chars=get_int("log_max_payload_chars", 12000),
            log_max_sse_lines=get_int(
                const.CONF_LOG_MAX_SSE_LINES, DEFAULT_LOG_MAX_SSE_LINES
            ),
            payload_log_path=resolve_path(
                data.get(CONF_PAYLOAD_LOG_PATH),
                ".storage/azure_openai_payloads.log",
            ),
            # Sliding Window
            sliding_window_enable=get_bool("sliding_window_enable", True),
            sliding_window_max_tokens=get_int("sliding_window_max_tokens", 4000),
            sliding_window_preserve_system=get_bool("sliding_window_preserve_system", True),
            debug_sse=get_bool("debug_sse", False),
            debug_sse_lines=get_int("debug_sse_lines", 10),
            # Early wait
            early_wait_enable=get_bool("early_wait_enable", True),
            early_wait_seconds=get_int("early_wait_seconds", 5),
            # Vocabulary
            vocabulary_enable=get_bool("vocabulary_enable", True),
            synonyms_file=data.get("synonyms_file"),
            # Local intent
            local_intent_enable=get_bool("local_intent_enable", True),
            # Utterances
            log_utterances=get_bool("log_utterances", True),
            utterances_log_path=resolve_path(
                data.get("utterances_log_path"),
                ".storage/azure_openai_conversation_utterances.log",
            ),
            # Statistics
            stats_enable=_get_stats_enable(),
            stats_aggregated_file=resolve_path(
                data.get(CONF_STATS_AGGREGATED_FILE),
                ".storage/azure_openai_stats_aggregated.json",
            ),
            stats_aggregation_interval=get_int(CONF_STATS_AGGREGATION_INTERVAL, 60),
            # MCP
            mcp_enabled=get_bool("mcp_enabled", True),
            mcp_ttl_seconds=get_int("mcp_ttl_seconds", 3600),
            # Tool Calling
            tools_enable=get_bool("tools_enable", True),
            tools_whitelist=get_str(
                "tools_whitelist",
                "light,switch,climate,cover,fan,media_player,lock,vacuum",
            ),
            tools_max_iterations=get_int("tools_max_iterations", 5),
            tools_max_calls_per_minute=get_int("tools_max_calls_per_minute", 30),
            tools_parallel_execution=get_bool("tools_parallel_execution", False),
            # Web search
            web_search_enable=get_bool(
                "web_search", get_bool("enable_web_search", False)
            ),
            bing_api_key=data.get("bing_api_key"),
            bing_endpoint=get_str(
                "bing_endpoint",
                "https://api.bing.microsoft.com/v7.0/search",
            ),
            bing_max_results=get_int("bing_max_results", 5),
            web_search_context_size=get_int("web_search_context_size", 2000),
            # Entity limits
            exposed_entities_limit=get_int("exposed_entities_limit", 500),
        )

    async def log_utterance(
        self,
        hass: HomeAssistant,
        conversation_id: Optional[str],
        mode: str,
        original: str,
        normalized: str,
    ) -> None:
        """
        Log an utterance to the configured file.

        Args:
            hass: Home Assistant instance
            conversation_id: Conversation ID
            mode: Handler mode (local_intent | llm_chat | llm_responses)
            original: Original user text
            normalized: Normalized text sent to handler
        """
        if not self.log_utterances or not self.utterances_log_path:
            return

        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "conversation_id": conversation_id or "",
                "mode": mode,
                "original": original,
                "normalized": normalized,
            },
            ensure_ascii=False,
        )

        def _write():
            path = self.utterances_log_path
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        try:
            await hass.async_add_executor_job(_write)
        except Exception:
            # Silently ignore logging failures
            pass

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.api_key:
            errors.append("api_key is required")

        if not self.api_base:
            errors.append("api_base is required")

        if not self.chat_model:
            errors.append("chat_model is required")

        if self.temperature < 0 or self.temperature > 2:
            errors.append(f"temperature must be in [0, 2], got {self.temperature}")

        if self.top_p < 0 or self.top_p > 1:
            errors.append(f"top_p must be in [0, 1], got {self.top_p}")

        if self.max_tokens < 1:
            errors.append(f"max_tokens must be > 0, got {self.max_tokens}")

        if self.api_timeout < 5:
            errors.append(f"api_timeout must be >= 5, got {self.api_timeout}")

        if self.tools_max_iterations < 1 or self.tools_max_iterations > 20:
            errors.append(
                f"tools_max_iterations must be in [1, 20], got {self.tools_max_iterations}"
            )

        if self.tools_max_calls_per_minute < 1:
            errors.append(
                f"tools_max_calls_per_minute must be > 0, got {self.tools_max_calls_per_minute}"
            )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """
        Convert configuration to dictionary.

        Useful for logging and debugging.

        Returns:
            Dictionary representation with sensitive data redacted
        """
        data = {
            # Redact sensitive data
            "api_key": self._redact_key(self.api_key),
            "api_base": self.api_base,
            "chat_model": self.chat_model,
            "api_version": self.api_version,
            # Model parameters
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "api_timeout": self.api_timeout,
            # Flags
            "vocabulary_enable": self.vocabulary_enable,
            "local_intent_enable": self.local_intent_enable,
            "early_wait_enable": self.early_wait_enable,
            "stats_enable": self.stats_enable,
            "mcp_enabled": self.mcp_enabled,
            "web_search_enable": self.web_search_enable,
            "tools_enable": self.tools_enable,
        }

        return data

    @staticmethod
    def _redact_key(key: Optional[str]) -> str:
        """Redact API key for logging."""
        if not key or len(key) <= 8:
            return "***"
        return f"{key[:3]}***{key[-3:]}"


async def async_log_to_file(
    hass: HomeAssistant,
    file_path: str,
    data: dict[str, Any],
) -> None:
    """Log structured data to a custom file asynchronously."""

    line = json.dumps(data, ensure_ascii=False)

    def _write() -> None:  # type: ignore
        """Blocking I/O operation to write to the file."""
        try:
            # Ensure directory exists
            abs_path = hass.config.path(file_path)
            parent_dir = os.path.dirname(abs_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)

            # Append to file
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        except Exception as e:
            _LOGGER.error("Failed to write to custom log file %s: %r", file_path, e)

    await hass.async_add_executor_job(_write)
