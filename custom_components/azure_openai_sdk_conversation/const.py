# File: /usr/share/hassio/homeassistant/custom_components/azure_openai_sdk_conversation/const.py
"""Constants for the Azure OpenAI SDK Conversation integration."""

from __future__ import annotations

from typing import Final, List

from homeassistant.const import Platform

# Integration domain
DOMAIN: Final[str] = "azure_openai_sdk_conversation"

# Supported platforms
PLATFORMS: Final[List[Platform]] = [Platform.CONVERSATION]

# Configuration keys (schema/entry) - CONF_* convention
CONF_API_BASE: Final[str] = "api_base"
CONF_API_KEY: Final[str] = "api_key"
CONF_CHAT_MODEL: Final[str] = "chat_model"
CONF_API_VERSION: Final[str] = "api_version"
CONF_TOKEN_PARAM: Final[str] = "token_param"
CONF_SYSTEM_PROMPT: Final[str] = "system_prompt"
CONF_PROMPT: Final[str] = "prompt"

# Model parameters
CONF_TEMPERATURE: Final[str] = "temperature"
CONF_TOP_P: Final[str] = "top_p"
CONF_MAX_TOKENS: Final[str] = "max_tokens"
CONF_API_TIMEOUT: Final[str] = "api_timeout"
CONF_REASONING_EFFORT: Final[str] = "reasoning_effort"
CONF_EXPOSED_ENTITIES_LIMIT: Final[str] = "exposed_entities_limit"

# Web search settings
CONF_WEB_SEARCH: Final[str] = "web_search"
CONF_WEB_SEARCH_CONTEXT_SIZE: Final[str] = "web_search_context_size"
CONF_WEB_SEARCH_USER_LOCATION: Final[str] = "web_search_user_location"

# Flag for UI/flow
CONF_RECOMMENDED: Final[str] = "recommended"

# Log settings
CONF_LOG_LEVEL: Final[str] = "log_level"
CONF_LOG_PAYLOAD_REQUEST: Final[str] = "log_payload_request"
CONF_LOG_PAYLOAD_RESPONSE: Final[str] = "log_payload_response"
CONF_LOG_SYSTEM_MESSAGE: Final[str] = "log_system_message"
CONF_LOG_MAX_PAYLOAD_CHARS: Final[str] = "log_max_payload_chars"
CONF_LOG_MAX_SSE_LINES: Final[str] = "log_max_sse_lines"
CONF_PAYLOAD_LOG_PATH: Final[str] = "payload_log_path"
CONF_SSL_VERIFY: Final[str] = "ssl_verify"

LOG_LEVEL_NONE: Final[str] = "none"
LOG_LEVEL_ERROR: Final[str] = "error"
LOG_LEVEL_INFO: Final[str] = "info"
LOG_LEVEL_TRACE: Final[str] = "trace"

DEFAULT_LOG_LEVEL: Final[str] = LOG_LEVEL_ERROR
DEFAULT_LOG_MAX_PAYLOAD_CHARS: Final[int] = 12000
DEFAULT_LOG_MAX_SSE_LINES: Final[int] = 10

# Early wait settings
CONF_EARLY_WAIT_ENABLE: Final[str] = "early_wait_enable"
CONF_EARLY_WAIT_SECONDS: Final[str] = "early_wait_seconds"

# Vocabulary / synonyms
CONF_VOCABULARY_ENABLE: Final[str] = "vocabulary_enable"
CONF_SYNONYMS_FILE: Final[str] = "synonyms_file"

# Utterances log
CONF_LOG_UTTERANCES: Final[str] = "log_utterances"
CONF_UTTERANCES_LOG_PATH: Final[str] = "utterances_log_path"

# Local Intent
CONF_LOCAL_INTENT_ENABLE: Final[str] = "local_intent_enable"

# Statistics
CONF_STATS_ENABLE: Final[str] = "stats_enable"
CONF_STATS_COMPONENT_LOG_PATH: Final[str] = "stats_component_log_path"
CONF_STATS_LLM_LOG_PATH: Final[str] = "stats_llm_log_path"
CONF_STATS_OVERRIDE_MODE: Final[str] = "stats_override_mode"
CONF_STATS_AGGREGATED_FILE: Final[str] = "stats_aggregated_file"
CONF_STATS_AGGREGATION_INTERVAL: Final[str] = "stats_aggregation_interval_minutes"

STATS_OVERRIDE_DEFAULT: Final[str] = "default"
STATS_OVERRIDE_ENABLE: Final[str] = "enable"
STATS_OVERRIDE_DISABLE: Final[str] = "disable"

# Token counting mode
CONF_TOKEN_COUNTING_MODE: Final[str] = "token_counting_mode"
TOKEN_COUNTING_SSE: Final[str] = "sse"
TOKEN_COUNTING_ESTIMATE: Final[str] = "estimate"
TOKEN_COUNTING_HYBRID: Final[str] = "hybrid"

# MCP Server
CONF_MCP_ENABLED: Final[str] = "mcp_enabled"
CONF_MCP_TTL_SECONDS: Final[str] = "mcp_ttl_seconds"

# Sliding Window Configuration
CONF_SLIDING_WINDOW_ENABLE: Final[str] = "sliding_window_enable"
CONF_SLIDING_WINDOW_MAX_TOKENS: Final[str] = "sliding_window_max_tokens"
CONF_SLIDING_WINDOW_PRESERVE_SYSTEM: Final[str] = "sliding_window_preserve_system"
CONF_SLIDING_WINDOW_TOKEN_BUFFER: Final[str] = "sliding_window_token_buffer"


# Tool Calling Configuration
CONF_TOOLS_ENABLE: Final[str] = "tools_enable"
CONF_TOOLS_WHITELIST: Final[str] = "tools_whitelist"
CONF_TOOLS_MAX_ITERATIONS: Final[str] = "tools_max_iterations"
CONF_TOOLS_MAX_CALLS_PER_MINUTE: Final[str] = "tools_max_calls_per_minute"
CONF_TOOLS_PARALLEL_EXECUTION: Final[str] = "tools_parallel_execution"

# Tool Calling Recommendations
RECOMMENDED_TOOLS_ENABLE: Final[bool] = True
RECOMMENDED_TOOLS_WHITELIST: Final[str] = (
    "light,switch,climate,cover,fan,media_player,lock,vacuum"
)
RECOMMENDED_TOOLS_MAX_ITERATIONS: Final[int] = 5
RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE: Final[int] = 30
RECOMMENDED_TOOLS_PARALLEL_EXECUTION: Final[bool] = False

# Pricing and alerts
CONF_CUSTOM_PRICING: Final[str] = "custom_pricing"
CONF_ALERT_ERROR_RATE: Final[str] = "alert_error_rate_percentage"
CONF_ALERT_COST_DAILY: Final[str] = "alert_cost_daily_usd"
CONF_ALERT_AVG_TIME: Final[str] = "alert_avg_execution_time_ms"

# Export formats
CONF_STATS_EXPORT_FORMAT: Final[str] = "stats_export_format"
EXPORT_FORMAT_JSON: Final[str] = "json"
EXPORT_FORMAT_CSV: Final[str] = "csv"
EXPORT_FORMAT_BOTH: Final[str] = "both"

# Error keys for UI/config flow
ERROR_CANNOT_CONNECT: Final[str] = "cannot_connect"
ERROR_INVALID_AUTH: Final[str] = "invalid_auth"
ERROR_INVALID_DEPLOYMENT: Final[str] = "invalid_deployment"
ERROR_UNKNOWN: Final[str] = "unknown"

# Default system prompt
DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are a conversational assistant integrated into Home Assistant. "
    "Respond concisely and usefully in the user's language: {{ user_language }}. "
    "House name: {{ name }}. "
    "Instructions:\n"
    "- Do not invent entities or states you do not know.\n"
    "- If you do not have enough context, ask for a brief clarification.\n"
    "- If the request is not about the house, still respond in a useful and concise way.\n\n"
    "User message: {{ user_text }}"
)

# Recommended values
RECOMMENDED_CHAT_MODEL: Final[str] = "gpt-4o-mini"
RECOMMENDED_TEMPERATURE: Final[float] = 0.7
RECOMMENDED_TOP_P: Final[float] = 1.0
RECOMMENDED_MAX_TOKENS: Final[int] = 512
RECOMMENDED_API_TIMEOUT: Final[int] = 30
RECOMMENDED_REASONING_EFFORT: Final[str] = "medium"
RECOMMENDED_EXPOSED_ENTITIES_LIMIT: Final[int] = 500

RECOMMENDED_WEB_SEARCH: Final[bool] = False
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE: Final[int] = 2000
RECOMMENDED_WEB_SEARCH_USER_LOCATION: Final[bool] = False

RECOMMENDED_EARLY_WAIT_ENABLE: Final[bool] = True
RECOMMENDED_EARLY_WAIT_SECONDS: Final[int] = 5
RECOMMENDED_VOCABULARY_ENABLE: Final[bool] = True
RECOMMENDED_LOCAL_INTENT_ENABLE: Final[bool] = True

RECOMMENDED_STATS_ENABLE: Final[bool] = True
RECOMMENDED_STATS_OVERRIDE_MODE: Final[str] = STATS_OVERRIDE_DEFAULT
RECOMMENDED_STATS_AGGREGATED_FILE: Final[str] = (
    ".storage/azure_openai_stats_aggregated.json"
)
RECOMMENDED_STATS_AGGREGATION_INTERVAL: Final[int] = 60
RECOMMENDED_TOKEN_COUNTING_MODE: Final[str] = TOKEN_COUNTING_HYBRID

RECOMMENDED_MCP_ENABLED: Final[bool] = True
RECOMMENDED_MCP_TTL_SECONDS: Final[int] = 3600

# Defaults
RECOMMENDED_SLIDING_WINDOW_ENABLE: Final[bool] = True
RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS: Final[int] = 4000
RECOMMENDED_SLIDING_WINDOW_PRESERVE_SYSTEM: Final[bool] = True
RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER: Final[int] = 200

RECOMMENDED_ALERT_ERROR_RATE: Final[float] = 5.0
RECOMMENDED_ALERT_COST_DAILY: Final[float] = 5.0
RECOMMENDED_ALERT_AVG_TIME: Final[float] = 3000.0

RECOMMENDED_STATS_EXPORT_FORMAT: Final[str] = EXPORT_FORMAT_JSON

__all__ = [
    # Domain / platforms
    "DOMAIN",
    "PLATFORMS",
    # Config keys
    "CONF_API_BASE",
    "CONF_API_KEY",
    "CONF_CHAT_MODEL",
    "CONF_API_VERSION",
    "CONF_TOKEN_PARAM",
    "CONF_SYSTEM_PROMPT",
    "CONF_PROMPT",
    "CONF_TEMPERATURE",
    "CONF_TOP_P",
    "CONF_MAX_TOKENS",
    "CONF_API_TIMEOUT",
    "CONF_REASONING_EFFORT",
    "CONF_EXPOSED_ENTITIES_LIMIT",
    "CONF_WEB_SEARCH",
    "CONF_WEB_SEARCH_CONTEXT_SIZE",
    "CONF_WEB_SEARCH_USER_LOCATION",
    "CONF_RECOMMENDED",
    # Logging
    "CONF_LOG_LEVEL",
    "CONF_LOG_PAYLOAD_REQUEST",
    "CONF_LOG_PAYLOAD_RESPONSE",
    "CONF_LOG_SYSTEM_MESSAGE",
    "CONF_LOG_MAX_PAYLOAD_CHARS",
    "CONF_LOG_MAX_SSE_LINES",
    "LOG_LEVEL_NONE",
    "LOG_LEVEL_ERROR",
    "LOG_LEVEL_INFO",
    "LOG_LEVEL_TRACE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_MAX_PAYLOAD_CHARS",
    "DEFAULT_LOG_MAX_SSE_LINES",
    # Early wait + Vocabulary + Utterances
    "CONF_EARLY_WAIT_ENABLE",
    "CONF_EARLY_WAIT_SECONDS",
    "CONF_VOCABULARY_ENABLE",
    "CONF_SYNONYMS_FILE",
    "CONF_LOG_UTTERANCES",
    "CONF_UTTERANCES_LOG_PATH",
    "CONF_LOCAL_INTENT_ENABLE",
    # Statistics
    "CONF_STATS_ENABLE",
    "CONF_STATS_COMPONENT_LOG_PATH",
    "CONF_STATS_LLM_LOG_PATH",
    "CONF_STATS_OVERRIDE_MODE",
    "CONF_STATS_AGGREGATED_FILE",
    "CONF_STATS_AGGREGATION_INTERVAL",
    "STATS_OVERRIDE_DEFAULT",
    "STATS_OVERRIDE_ENABLE",
    "STATS_OVERRIDE_DISABLE",
    "CONF_TOKEN_COUNTING_MODE",
    "TOKEN_COUNTING_SSE",
    "TOKEN_COUNTING_ESTIMATE",
    "TOKEN_COUNTING_HYBRID",
    # MCP
    "CONF_MCP_ENABLED",
    "CONF_MCP_TTL_SECONDS",
    # Alerts and pricing
    "CONF_CUSTOM_PRICING",
    "CONF_ALERT_ERROR_RATE",
    "CONF_ALERT_COST_DAILY",
    "CONF_ALERT_AVG_TIME",
    # Export
    "CONF_STATS_EXPORT_FORMAT",
    "EXPORT_FORMAT_JSON",
    "EXPORT_FORMAT_CSV",
    "EXPORT_FORMAT_BOTH",
    # Error keys
    "ERROR_CANNOT_CONNECT",
    "ERROR_INVALID_AUTH",
    "ERROR_INVALID_DEPLOYMENT",
    "ERROR_UNKNOWN",
    # Defaults / recommendations
    "DEFAULT_SYSTEM_PROMPT",
    "RECOMMENDED_CHAT_MODEL",
    "RECOMMENDED_TEMPERATURE",
    "RECOMMENDED_TOP_P",
    "RECOMMENDED_MAX_TOKENS",
    "RECOMMENDED_API_TIMEOUT",
    "RECOMMENDED_REASONING_EFFORT",
    "RECOMMENDED_EXPOSED_ENTITIES_LIMIT",
    "RECOMMENDED_WEB_SEARCH",
    "RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE",
    "RECOMMENDED_WEB_SEARCH_USER_LOCATION",
    "RECOMMENDED_EARLY_WAIT_ENABLE",
    "RECOMMENDED_EARLY_WAIT_SECONDS",
    "RECOMMENDED_VOCABULARY_ENABLE",
    "RECOMMENDED_LOCAL_INTENT_ENABLE",
    "RECOMMENDED_STATS_ENABLE",
    "RECOMMENDED_STATS_OVERRIDE_MODE",
    "RECOMMENDED_STATS_AGGREGATED_FILE",
    "RECOMMENDED_STATS_AGGREGATION_INTERVAL",
    "RECOMMENDED_TOKEN_COUNTING_MODE",
    "RECOMMENDED_MCP_ENABLED",
    "RECOMMENDED_MCP_TTL_SECONDS",
    "RECOMMENDED_ALERT_ERROR_RATE",
    "RECOMMENDED_ALERT_COST_DAILY",
    "RECOMMENDED_ALERT_AVG_TIME",
    "RECOMMENDED_STATS_EXPORT_FORMAT",
    # Tool Calling
    "CONF_TOOLS_ENABLE",
    "CONF_TOOLS_WHITELIST",
    "CONF_TOOLS_MAX_ITERATIONS",
    "CONF_TOOLS_MAX_CALLS_PER_MINUTE",
    "CONF_TOOLS_PARALLEL_EXECUTION",
    "RECOMMENDED_TOOLS_ENABLE",
    "RECOMMENDED_TOOLS_WHITELIST",
    "RECOMMENDED_TOOLS_MAX_ITERATIONS",
    "RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE",
    "RECOMMENDED_TOOLS_PARALLEL_EXECUTION",
    "CONF_SLIDING_WINDOW_ENABLE",
    "CONF_SLIDING_WINDOW_MAX_TOKENS",
    "CONF_SLIDING_WINDOW_PRESERVE_SYSTEM",
    "CONF_SLIDING_WINDOW_TOKEN_BUFFER",
    "RECOMMENDED_SLIDING_WINDOW_ENABLE",
    "RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS",
    "RECOMMENDED_SLIDING_WINDOW_PRESERVE_SYSTEM",
    "RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER",
]
