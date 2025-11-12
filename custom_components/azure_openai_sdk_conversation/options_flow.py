# File: /usr/share/hassio/homeassistant/custom_components/azure_openai_sdk_conversation/options_flow.py
"""Options flow for Azure OpenAI SDK Conversation."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, OptionsFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import (
    CONF_API_TIMEOUT,
    CONF_API_VERSION,
    CONF_EXPOSED_ENTITIES_LIMIT,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_USER_LOCATION,
    RECOMMENDED_API_TIMEOUT,
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    # logging
    CONF_LOG_LEVEL,
    CONF_LOG_PAYLOAD_REQUEST,
    CONF_LOG_PAYLOAD_RESPONSE,
    CONF_LOG_SYSTEM_MESSAGE,
    CONF_LOG_MAX_PAYLOAD_CHARS,
    CONF_LOG_MAX_SSE_LINES,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_PAYLOAD_CHARS,
    DEFAULT_LOG_MAX_SSE_LINES,
    LOG_LEVEL_NONE,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_TRACE,
    # early wait + vocabulary + utterances
    CONF_EARLY_WAIT_ENABLE,
    CONF_EARLY_WAIT_SECONDS,
    CONF_VOCABULARY_ENABLE,
    CONF_SYNONYMS_FILE,
    CONF_LOG_UTTERANCES,
    CONF_UTTERANCES_LOG_PATH,
    RECOMMENDED_EARLY_WAIT_ENABLE,
    RECOMMENDED_EARLY_WAIT_SECONDS,
    RECOMMENDED_VOCABULARY_ENABLE,
    CONF_LOCAL_INTENT_ENABLE,
    RECOMMENDED_LOCAL_INTENT_ENABLE,
    # MCP Server
    CONF_MCP_ENABLED,
    CONF_MCP_TTL_SECONDS,
    RECOMMENDED_MCP_ENABLED,
    RECOMMENDED_MCP_TTL_SECONDS,
    # Statistics
    CONF_STATS_OVERRIDE_MODE,
    STATS_OVERRIDE_DEFAULT,
    STATS_OVERRIDE_ENABLE,
    STATS_OVERRIDE_DISABLE,
    RECOMMENDED_STATS_OVERRIDE_MODE,
    CONF_STATS_AGGREGATED_FILE,
    RECOMMENDED_STATS_AGGREGATED_FILE,
    CONF_STATS_AGGREGATION_INTERVAL,
    RECOMMENDED_STATS_AGGREGATION_INTERVAL,
    CONF_TOOLS_ENABLE,
    CONF_TOOLS_WHITELIST,
    CONF_TOOLS_MAX_ITERATIONS,
    CONF_TOOLS_MAX_CALLS_PER_MINUTE,
    CONF_TOOLS_PARALLEL_EXECUTION,
    RECOMMENDED_TOOLS_ENABLE,
    RECOMMENDED_TOOLS_WHITELIST,
    RECOMMENDED_TOOLS_MAX_ITERATIONS,
    RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
    RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
    CONF_SSL_VERIFY,
    CONF_PAYLOAD_LOG_PATH,
    # Sliding Window
    CONF_SLIDING_WINDOW_ENABLE,
    CONF_SLIDING_WINDOW_MAX_TOKENS,
    CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
    RECOMMENDED_SLIDING_WINDOW_ENABLE,
    RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
    CONF_SLIDING_WINDOW_TOKEN_BUFFER,
    RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER,
)
from .utils import APIVersionManager

_LOGGER = logging.getLogger(__name__)


class AzureOpenAIOptionsFlow(OptionsFlow):
    """Handle options flow for Azure OpenAI SDK Conversation."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        # If the user has submitted the form, we recalculate token_param consistent with model+version.
        if user_input is not None:
            model = (self.config_entry.data.get("chat_model") or "").lower()

            # Determine the chosen api-version (if not provided, use the current one)
            chosen_version = str(
                user_input.get(CONF_API_VERSION)
                or self.config_entry.options.get(CONF_API_VERSION)
                or self.config_entry.data.get(CONF_API_VERSION, "2025-03-01-preview")
            )

            def _ver_date_tuple(ver: str) -> tuple[int, int, int]:
                core = (ver or "").split("-preview")[0]
                parts = core.split("-")
                try:
                    return (int(parts[0]), int(parts[1]), int(parts[2]))
                except Exception:  # noqa: BLE001
                    return (1900, 1, 1)

            if (
                model.startswith("gpt-5")
                or model.startswith("gpt-4.1")
                or model.startswith("gpt-4.2")
            ):
                token_param = "max_completion_tokens"
            else:
                y, m, d = _ver_date_tuple(chosen_version)
                token_param = (
                    "max_completion_tokens"
                    if (y, m, d) >= (2025, 3, 1)
                    else "max_tokens"
                )

            # Also save token_param in the options to guide the Chat provider to avoid the first wrong attempt.
            user_input = {**user_input, "token_param": token_param}
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RECOMMENDED,
                    default=self.config_entry.options.get(CONF_RECOMMENDED, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_PROMPT,
                    default=self.config_entry.options.get(
                        CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                    ),
                ): TemplateSelector(),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=self.config_entry.options.get(
                        CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=2.0,
                        step=0.05,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_TOP_P,
                    default=self.config_entry.options.get(
                        CONF_TOP_P, RECOMMENDED_TOP_P
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.01,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=self.config_entry.options.get(
                        CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=8192,
                        step=1,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_EXPOSED_ENTITIES_LIMIT,
                    default=self.config_entry.options.get(
                        CONF_EXPOSED_ENTITIES_LIMIT, RECOMMENDED_EXPOSED_ENTITIES_LIMIT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=50,
                        max=2000,
                        step=10,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_API_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_API_TIMEOUT, RECOMMENDED_API_TIMEOUT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=300,
                        step=5,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_SSL_VERIFY,
                    default=self.config_entry.options.get(CONF_SSL_VERIFY, True),
                ): BooleanSelector(),
            }
        )

        # Add options for "o*" (reasoning) models
        model = self.config_entry.data.get("chat_model", "").lower()
        if model.startswith("o"):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_REASONING_EFFORT,
                        default=self.config_entry.options.get(
                            CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )

        # Advanced options for API version
        current_version = self.config_entry.options.get(
            CONF_API_VERSION,
            self.config_entry.data.get(CONF_API_VERSION, "2025-03-01-preview"),
        )
        known_versions = APIVersionManager.known_versions()
        if current_version not in known_versions:
            known_versions.append(current_version)

        schema = schema.extend(
            {
                vol.Optional(
                    CONF_API_VERSION,
                    default=current_version,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(known_versions, reverse=True),
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        # Options for web search (if implemented)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_WEB_SEARCH,
                    default=self.config_entry.options.get(
                        CONF_WEB_SEARCH, RECOMMENDED_WEB_SEARCH
                    ),
                ): BooleanSelector(),
            }
        )
        if self.config_entry.options.get(CONF_WEB_SEARCH, False):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=self.config_entry.options.get(
                            CONF_WEB_SEARCH_CONTEXT_SIZE,
                            RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=500,
                            max=5000,
                            step=100,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=self.config_entry.options.get(
                            CONF_WEB_SEARCH_USER_LOCATION,
                            RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                        ),
                    ): BooleanSelector(),
                }
            )

        # Logging options
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOG_LEVEL,
                    default=self.config_entry.options.get(
                        CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            LOG_LEVEL_NONE,
                            LOG_LEVEL_ERROR,
                            LOG_LEVEL_INFO,
                            LOG_LEVEL_TRACE,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_LOG_PAYLOAD_REQUEST,
                    default=self.config_entry.options.get(
                        CONF_LOG_PAYLOAD_REQUEST, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_PAYLOAD_RESPONSE,
                    default=self.config_entry.options.get(
                        CONF_LOG_PAYLOAD_RESPONSE, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_SYSTEM_MESSAGE,
                    default=self.config_entry.options.get(
                        CONF_LOG_SYSTEM_MESSAGE, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_MAX_PAYLOAD_CHARS,
                    default=self.config_entry.options.get(
                        CONF_LOG_MAX_PAYLOAD_CHARS, DEFAULT_LOG_MAX_PAYLOAD_CHARS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=100,
                        max=500000,
                        step=100,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_LOG_MAX_SSE_LINES,
                    default=self.config_entry.options.get(
                        CONF_LOG_MAX_SSE_LINES, DEFAULT_LOG_MAX_SSE_LINES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=200,
                        step=1,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_PAYLOAD_LOG_PATH,
                    default=self.config_entry.options.get(
                        CONF_PAYLOAD_LOG_PATH,
                        ".storage/azure_openai_payloads.log",
                    ),
                ): str,
            }
        )

        # Early wait (enable + seconds)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_EARLY_WAIT_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_EARLY_WAIT_ENABLE, RECOMMENDED_EARLY_WAIT_ENABLE
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_EARLY_WAIT_SECONDS,
                    default=self.config_entry.options.get(
                        CONF_EARLY_WAIT_SECONDS, RECOMMENDED_EARLY_WAIT_SECONDS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=120,
                        step=1,
                        mode="box",
                    )
                ),
            }
        )

        # Vocabulary (enable + synonyms file)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_VOCABULARY_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_VOCABULARY_ENABLE, RECOMMENDED_VOCABULARY_ENABLE
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SYNONYMS_FILE,
                    default=self.config_entry.options.get(
                        CONF_SYNONYMS_FILE,
                        "custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json",
                    ),
                ): str,
            }
        )

        # Utterances log (enable + file path)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOG_UTTERANCES,
                    default=self.config_entry.options.get(CONF_LOG_UTTERANCES, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_UTTERANCES_LOG_PATH,
                    default=self.config_entry.options.get(
                        CONF_UTTERANCES_LOG_PATH,
                        ".storage/azure_openai_conversation_utterances.log",
                    ),
                ): str,
            }
        )

        # Local Intent Handling
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOCAL_INTENT_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_LOCAL_INTENT_ENABLE, RECOMMENDED_LOCAL_INTENT_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Statistics
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_STATS_OVERRIDE_MODE,
                    default=self.config_entry.options.get(
                        CONF_STATS_OVERRIDE_MODE, RECOMMENDED_STATS_OVERRIDE_MODE
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            STATS_OVERRIDE_DEFAULT,
                            STATS_OVERRIDE_ENABLE,
                            STATS_OVERRIDE_DISABLE,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="stats_override_mode",
                    )
                ),
                vol.Optional(
                    CONF_STATS_AGGREGATED_FILE,
                    default=self.config_entry.options.get(
                        CONF_STATS_AGGREGATED_FILE,
                        RECOMMENDED_STATS_AGGREGATED_FILE,
                    ),
                ): str,
                vol.Optional(
                    CONF_STATS_AGGREGATION_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_STATS_AGGREGATION_INTERVAL,
                        RECOMMENDED_STATS_AGGREGATION_INTERVAL,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=1440,
                        step=5,
                        mode="box",
                    )
                ),
            }
        )

        # MCP Server
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_MCP_ENABLED,
                    default=self.config_entry.options.get(
                        CONF_MCP_ENABLED, RECOMMENDED_MCP_ENABLED
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MCP_TTL_SECONDS,
                    default=self.config_entry.options.get(
                        CONF_MCP_TTL_SECONDS, RECOMMENDED_MCP_TTL_SECONDS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=300,
                        max=7200,
                        step=300,
                        mode="box",
                    )
                ),
            }
        )

        # Sliding Window section
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_SLIDING_WINDOW_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_SLIDING_WINDOW_ENABLE, RECOMMENDED_SLIDING_WINDOW_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Only show additional settings if sliding window is enabled
        if self.config_entry.options.get(
            CONF_SLIDING_WINDOW_ENABLE, RECOMMENDED_SLIDING_WINDOW_ENABLE
        ):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_SLIDING_WINDOW_MAX_TOKENS,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_MAX_TOKENS,
                            RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1000,
                            max=16000,
                            step=500,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SLIDING_WINDOW_TOKEN_BUFFER,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_TOKEN_BUFFER,
                            RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1000,
                            step=50,
                            mode="box",
                        )
                    ),
                }
            )

        # Tool Calling section
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_TOOLS_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_TOOLS_ENABLE, RECOMMENDED_TOOLS_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Only show additional tool settings if tools are enabled
        if self.config_entry.options.get(CONF_TOOLS_ENABLE, RECOMMENDED_TOOLS_ENABLE):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_TOOLS_WHITELIST,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_WHITELIST, RECOMMENDED_TOOLS_WHITELIST
                        ),
                    ): str,
                    vol.Optional(
                        CONF_TOOLS_MAX_ITERATIONS,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_MAX_ITERATIONS, RECOMMENDED_TOOLS_MAX_ITERATIONS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=20,
                            step=1,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_TOOLS_MAX_CALLS_PER_MINUTE,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_MAX_CALLS_PER_MINUTE,
                            RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5,
                            max=100,
                            step=5,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_TOOLS_PARALLEL_EXECUTION,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_PARALLEL_EXECUTION,
                            RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
                        ),
                    ): BooleanSelector(),
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema)


@callback
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    """Get the options flow for this handler."""
    return AzureOpenAIOptionsFlow(config_entry)
=======
# File: /usr/share/hassio/homeassistant/custom_components/azure_openai_sdk_conversation/options_flow.py
"""Options flow for Azure OpenAI SDK Conversation."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, OptionsFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import (
    CONF_API_TIMEOUT,
    CONF_API_VERSION,
    CONF_EXPOSED_ENTITIES_LIMIT,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_USER_LOCATION,
    RECOMMENDED_API_TIMEOUT,
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    # logging
    CONF_LOG_LEVEL,
    CONF_LOG_PAYLOAD_REQUEST,
    CONF_LOG_PAYLOAD_RESPONSE,
    CONF_LOG_SYSTEM_MESSAGE,
    CONF_LOG_MAX_PAYLOAD_CHARS,
    CONF_LOG_MAX_SSE_LINES,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_PAYLOAD_CHARS,
    DEFAULT_LOG_MAX_SSE_LINES,
    LOG_LEVEL_NONE,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_TRACE,
    # early wait + vocabulary + utterances
    CONF_EARLY_WAIT_ENABLE,
    CONF_EARLY_WAIT_SECONDS,
    CONF_VOCABULARY_ENABLE,
    CONF_SYNONYMS_FILE,
    CONF_LOG_UTTERANCES,
    CONF_UTTERANCES_LOG_PATH,
    RECOMMENDED_EARLY_WAIT_ENABLE,
    RECOMMENDED_EARLY_WAIT_SECONDS,
    RECOMMENDED_VOCABULARY_ENABLE,
    CONF_LOCAL_INTENT_ENABLE,
    RECOMMENDED_LOCAL_INTENT_ENABLE,
    # MCP Server
    CONF_MCP_ENABLED,
    CONF_MCP_TTL_SECONDS,
    RECOMMENDED_MCP_ENABLED,
    RECOMMENDED_MCP_TTL_SECONDS,
    # Statistics
    CONF_STATS_OVERRIDE_MODE,
    STATS_OVERRIDE_DEFAULT,
    STATS_OVERRIDE_ENABLE,
    STATS_OVERRIDE_DISABLE,
    RECOMMENDED_STATS_OVERRIDE_MODE,
    CONF_STATS_AGGREGATED_FILE,
    RECOMMENDED_STATS_AGGREGATED_FILE,
    CONF_STATS_AGGREGATION_INTERVAL,
    RECOMMENDED_STATS_AGGREGATION_INTERVAL,
    CONF_TOOLS_ENABLE,
    CONF_TOOLS_WHITELIST,
    CONF_TOOLS_MAX_ITERATIONS,
    CONF_TOOLS_MAX_CALLS_PER_MINUTE,
    CONF_TOOLS_PARALLEL_EXECUTION,
    RECOMMENDED_TOOLS_ENABLE,
    RECOMMENDED_TOOLS_WHITELIST,
    RECOMMENDED_TOOLS_MAX_ITERATIONS,
    RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
    RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
    CONF_SSL_VERIFY,
    CONF_PAYLOAD_LOG_PATH,
    # Sliding Window
    CONF_SLIDING_WINDOW_ENABLE,
    CONF_SLIDING_WINDOW_MAX_TOKENS,
    CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
    RECOMMENDED_SLIDING_WINDOW_ENABLE,
    RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
    CONF_SLIDING_WINDOW_TOKEN_BUFFER,
    RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER,
)
from .utils import APIVersionManager

_LOGGER = logging.getLogger(__name__)


class AzureOpenAIOptionsFlow(OptionsFlow):
    """Handle options flow for Azure OpenAI SDK Conversation."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        # If the user has submitted the form, we recalculate token_param consistent with model+version.
        if user_input is not None:
            model = (self.config_entry.data.get("chat_model") or "").lower()

            # Determine the chosen api-version (if not provided, use the current one)
            chosen_version = str(
                user_input.get(CONF_API_VERSION)
                or self.config_entry.options.get(CONF_API_VERSION)
                or self.config_entry.data.get(CONF_API_VERSION, "2025-03-01-preview")
            )

            def _ver_date_tuple(ver: str) -> tuple[int, int, int]:
                core = (ver or "").split("-preview")[0]
                parts = core.split("-")
                try:
                    return (int(parts[0]), int(parts[1]), int(parts[2]))
                except Exception:  # noqa: BLE001
                    return (1900, 1, 1)

            if (
                model.startswith("gpt-5")
                or model.startswith("gpt-4.1")
                or model.startswith("gpt-4.2")
            ):
                token_param = "max_completion_tokens"
            else:
                y, m, d = _ver_date_tuple(chosen_version)
                token_param = (
                    "max_completion_tokens"
                    if (y, m, d) >= (2025, 3, 1)
                    else "max_tokens"
                )

            # Also save token_param in the options to guide the Chat provider to avoid the first wrong attempt.
            user_input = {**user_input, "token_param": token_param}
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RECOMMENDED,
                    default=self.config_entry.options.get(CONF_RECOMMENDED, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_PROMPT,
                    default=self.config_entry.options.get(
                        CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                    ),
                ): TemplateSelector(),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=self.config_entry.options.get(
                        CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=2.0,
                        step=0.05,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_TOP_P,
                    default=self.config_entry.options.get(
                        CONF_TOP_P, RECOMMENDED_TOP_P
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.01,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=self.config_entry.options.get(
                        CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=8192,
                        step=1,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_EXPOSED_ENTITIES_LIMIT,
                    default=self.config_entry.options.get(
                        CONF_EXPOSED_ENTITIES_LIMIT, RECOMMENDED_EXPOSED_ENTITIES_LIMIT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=50,
                        max=2000,
                        step=10,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_API_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_API_TIMEOUT, RECOMMENDED_API_TIMEOUT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=300,
                        step=5,
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_SSL_VERIFY,
                    default=self.config_entry.options.get(CONF_SSL_VERIFY, True),
                ): BooleanSelector(),
            }
        )

        # Add options for "o*" (reasoning) models
        model = self.config_entry.data.get("chat_model", "").lower()
        if model.startswith("o"):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_REASONING_EFFORT,
                        default=self.config_entry.options.get(
                            CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )

        # Advanced options for API version
        current_version = self.config_entry.options.get(
            CONF_API_VERSION,
            self.config_entry.data.get(CONF_API_VERSION, "2025-03-01-preview"),
        )
        known_versions = APIVersionManager.known_versions()
        if current_version not in known_versions:
            known_versions.append(current_version)

        schema = schema.extend(
            {
                vol.Optional(
                    CONF_API_VERSION,
                    default=current_version,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(known_versions, reverse=True),
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        # Options for web search (if implemented)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_WEB_SEARCH,
                    default=self.config_entry.options.get(
                        CONF_WEB_SEARCH, RECOMMENDED_WEB_SEARCH
                    ),
                ): BooleanSelector(),
            }
        )
        if self.config_entry.options.get(CONF_WEB_SEARCH, False):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=self.config_entry.options.get(
                            CONF_WEB_SEARCH_CONTEXT_SIZE,
                            RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=500,
                            max=5000,
                            step=100,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=self.config_entry.options.get(
                            CONF_WEB_SEARCH_USER_LOCATION,
                            RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                        ),
                    ): BooleanSelector(),
                }
            )

        # Logging options
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOG_LEVEL,
                    default=self.config_entry.options.get(
                        CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            LOG_LEVEL_NONE,
                            LOG_LEVEL_ERROR,
                            LOG_LEVEL_INFO,
                            LOG_LEVEL_TRACE,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_LOG_PAYLOAD_REQUEST,
                    default=self.config_entry.options.get(
                        CONF_LOG_PAYLOAD_REQUEST, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_PAYLOAD_RESPONSE,
                    default=self.config_entry.options.get(
                        CONF_LOG_PAYLOAD_RESPONSE, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_SYSTEM_MESSAGE,
                    default=self.config_entry.options.get(
                        CONF_LOG_SYSTEM_MESSAGE, False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_LOG_MAX_PAYLOAD_CHARS,
                    default=self.config_entry.options.get(
                        CONF_LOG_MAX_PAYLOAD_CHARS, DEFAULT_LOG_MAX_PAYLOAD_CHARS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=100,
                        max=500000,
                        step=100,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_LOG_MAX_SSE_LINES,
                    default=self.config_entry.options.get(
                        CONF_LOG_MAX_SSE_LINES, DEFAULT_LOG_MAX_SSE_LINES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=200,
                        step=1,
                        mode="box",
                    )
                ),
                vol.Optional(
                    CONF_PAYLOAD_LOG_PATH,
                    default=self.config_entry.options.get(
                        CONF_PAYLOAD_LOG_PATH,
                        ".storage/azure_openai_payloads.log",
                    ),
                ): str,
            }
        )

        # Early wait (enable + seconds)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_EARLY_WAIT_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_EARLY_WAIT_ENABLE, RECOMMENDED_EARLY_WAIT_ENABLE
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_EARLY_WAIT_SECONDS,
                    default=self.config_entry.options.get(
                        CONF_EARLY_WAIT_SECONDS, RECOMMENDED_EARLY_WAIT_SECONDS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=120,
                        step=1,
                        mode="box",
                    )
                ),
            }
        )

        # Vocabulary (enable + synonyms file)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_VOCABULARY_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_VOCABULARY_ENABLE, RECOMMENDED_VOCABULARY_ENABLE
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SYNONYMS_FILE,
                    default=self.config_entry.options.get(
                        CONF_SYNONYMS_FILE,
                        "custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json",
                    ),
                ): str,
            }
        )

        # Utterances log (enable + file path)
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOG_UTTERANCES,
                    default=self.config_entry.options.get(CONF_LOG_UTTERANCES, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_UTTERANCES_LOG_PATH,
                    default=self.config_entry.options.get(
                        CONF_UTTERANCES_LOG_PATH,
                        ".storage/azure_openai_conversation_utterances.log",
                    ),
                ): str,
            }
        )

        # Local Intent Handling
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_LOCAL_INTENT_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_LOCAL_INTENT_ENABLE, RECOMMENDED_LOCAL_INTENT_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Statistics
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_STATS_OVERRIDE_MODE,
                    default=self.config_entry.options.get(
                        CONF_STATS_OVERRIDE_MODE, RECOMMENDED_STATS_OVERRIDE_MODE
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            STATS_OVERRIDE_DEFAULT,
                            STATS_OVERRIDE_ENABLE,
                            STATS_OVERRIDE_DISABLE,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="stats_override_mode",
                    )
                ),
                vol.Optional(
                    CONF_STATS_AGGREGATED_FILE,
                    default=self.config_entry.options.get(
                        CONF_STATS_AGGREGATED_FILE,
                        RECOMMENDED_STATS_AGGREGATED_FILE,
                    ),
                ): str,
                vol.Optional(
                    CONF_STATS_AGGREGATION_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_STATS_AGGREGATION_INTERVAL,
                        RECOMMENDED_STATS_AGGREGATION_INTERVAL,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=1440,
                        step=5,
                        mode="box",
                    )
                ),
            }
        )

        # MCP Server
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_MCP_ENABLED,
                    default=self.config_entry.options.get(
                        CONF_MCP_ENABLED, RECOMMENDED_MCP_ENABLED
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MCP_TTL_SECONDS,
                    default=self.config_entry.options.get(
                        CONF_MCP_TTL_SECONDS, RECOMMENDED_MCP_TTL_SECONDS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=300,
                        max=7200,
                        step=300,
                        mode="box",
                    )
                ),
            }
        )

        # Sliding Window section
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_SLIDING_WINDOW_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_SLIDING_WINDOW_ENABLE, RECOMMENDED_SLIDING_WINDOW_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Only show additional settings if sliding window is enabled
        if self.config_entry.options.get(
            CONF_SLIDING_WINDOW_ENABLE, RECOMMENDED_SLIDING_WINDOW_ENABLE
        ):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_SLIDING_WINDOW_MAX_TOKENS,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_MAX_TOKENS,
                            RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1000,
                            max=16000,
                            step=500,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SLIDING_WINDOW_TOKEN_BUFFER,
                        default=self.config_entry.options.get(
                            CONF_SLIDING_WINDOW_TOKEN_BUFFER,
                            RECOMMENDED_SLIDING_WINDOW_TOKEN_BUFFER,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1000,
                            step=50,
                            mode="box",
                        )
                    ),
                }
            )

        # Tool Calling section
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_TOOLS_ENABLE,
                    default=self.config_entry.options.get(
                        CONF_TOOLS_ENABLE, RECOMMENDED_TOOLS_ENABLE
                    ),
                ): BooleanSelector(),
            }
        )

        # Only show additional tool settings if tools are enabled
        if self.config_entry.options.get(CONF_TOOLS_ENABLE, RECOMMENDED_TOOLS_ENABLE):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_TOOLS_WHITELIST,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_WHITELIST, RECOMMENDED_TOOLS_WHITELIST
                        ),
                    ): str,
                    vol.Optional(
                        CONF_TOOLS_MAX_ITERATIONS,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_MAX_ITERATIONS, RECOMMENDED_TOOLS_MAX_ITERATIONS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=20,
                            step=1,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_TOOLS_MAX_CALLS_PER_MINUTE,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_MAX_CALLS_PER_MINUTE,
                            RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5,
                            max=100,
                            step=5,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_TOOLS_PARALLEL_EXECUTION,
                        default=self.config_entry.options.get(
                            CONF_TOOLS_PARALLEL_EXECUTION,
                            RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
                        ),
                    ): BooleanSelector(),
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema)


@callback
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    """Get the options flow for this handler."""
    return AzureOpenAIOptionsFlow(config_entry)
>>>>>>> e8f918df5a0f1a917b9e8681179363a6574e13f1
