"""Config flow for Azure OpenAI SDK Conversation – version 2025.9+."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client  # noqa: F401
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import VolDictType

from . import normalize_azure_endpoint
from .const import (
    CONF_API_BASE,
    CONF_API_VERSION,
    CONF_CHAT_MODEL,
    # Early wait + vocabulary + utterances
    CONF_EARLY_WAIT_ENABLE,
    CONF_EARLY_WAIT_SECONDS,
    CONF_EXPOSED_ENTITIES_LIMIT,
    CONF_LOCAL_INTENT_ENABLE,
    # Logging
    CONF_LOG_LEVEL,
    CONF_LOG_MAX_PAYLOAD_CHARS,
    CONF_LOG_MAX_SSE_LINES,
    CONF_LOG_PAYLOAD_REQUEST,
    CONF_LOG_PAYLOAD_RESPONSE,
    CONF_LOG_SYSTEM_MESSAGE,
    CONF_LOG_UTTERANCES,
    CONF_MAX_TOKENS,
    # MCP Server
    CONF_MCP_ENABLED,
    CONF_MCP_TTL_SECONDS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    # Sliding window
    CONF_SLIDING_WINDOW_ENABLE,
    CONF_SLIDING_WINDOW_MAX_TOKENS,
    CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
    CONF_STATS_COMPONENT_LOG_PATH,
    # Statistics
    CONF_STATS_ENABLE,
    CONF_STATS_LLM_LOG_PATH,
    CONF_SYNONYMS_FILE,
    # Tool calling
    CONF_TOOLS_ENABLE,
    CONF_TOOLS_MAX_CALLS_PER_MINUTE,
    CONF_TOOLS_MAX_ITERATIONS,
    CONF_TOOLS_PARALLEL_EXECUTION,
    CONF_TOOLS_WHITELIST,
    CONF_UTTERANCES_LOG_PATH,
    CONF_VOCABULARY_ENABLE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_PAYLOAD_CHARS,
    DEFAULT_LOG_MAX_SSE_LINES,
    # Core
    DOMAIN,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_NONE,
    LOG_LEVEL_TRACE,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_EARLY_WAIT_ENABLE,
    RECOMMENDED_EARLY_WAIT_SECONDS,
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
    RECOMMENDED_LOCAL_INTENT_ENABLE,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_MCP_ENABLED,
    RECOMMENDED_MCP_TTL_SECONDS,
    RECOMMENDED_SLIDING_WINDOW_ENABLE,
    RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
    RECOMMENDED_SLIDING_WINDOW_PRESERVE_SYSTEM,
    RECOMMENDED_TOOLS_ENABLE,
    RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
    RECOMMENDED_TOOLS_MAX_ITERATIONS,
    RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
    RECOMMENDED_TOOLS_WHITELIST,
    RECOMMENDED_VOCABULARY_ENABLE,
)
from .utils.validators import AzureOpenAIValidator  # ✅ Fixed import

_LOGGER = logging.getLogger(__name__)

DEFAULT_API_VERSION = "2025-03-01-preview"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_BASE): str,
        vol.Required(CONF_CHAT_MODEL, default=RECOMMENDED_CHAT_MODEL): str,
        vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): str,
    }
)


def _ver_date_tuple(ver: str) -> tuple[int, int, int]:
    """Parse 'YYYY-MM-DD...' into (Y, M, D); return a very old date on failure."""
    core = (ver or "").split("-preview")[0]
    parts = core.split("-")
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:  # noqa: BLE001
        return (1900, 1, 1)


def _pick_chat_token_param(*, model: str, api_version: str) -> str:
    """Choose max_tokens vs max_completion_tokens based on model and API version."""
    model_l = (model or "").lower()
    if (
        model_l.startswith("gpt-5")
        or model_l.startswith("gpt-4.1")
        or model_l.startswith("gpt-4.2")
    ):
        return "max_completion_tokens"
    y, m, d = _ver_date_tuple(api_version)
    return "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"


async def _maybe_await(value: Any) -> None:
    """Await value if it's awaitable/coroutine (helps with tests patching async methods)."""
    if asyncio.iscoroutine(value):
        await value


class AzureOpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure OpenAI SDK Conversation."""

    VERSION = 2
    MINOR_VERSION = 3  # Early wait + vocabulary + utterances path

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._validated: dict[str, Any] | None = None
        self._sampling_caps: dict[str, dict[str, Any]] = {}
        self._step1_data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step. Validates credentials and fetches capabilities."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        self._step1_data = {
            CONF_API_KEY: user_input[CONF_API_KEY],
            CONF_API_BASE: (user_input[CONF_API_BASE] or "").strip(),
            CONF_CHAT_MODEL: (user_input[CONF_CHAT_MODEL] or "").strip(),
            CONF_API_VERSION: (
                user_input.get(CONF_API_VERSION, DEFAULT_API_VERSION) or ""
            ).strip(),
        }

        errors: dict[str, str] = {}

        validator = AzureOpenAIValidator(
            self.hass,
            self._step1_data[CONF_API_KEY],
            self._step1_data[CONF_API_BASE],
            self._step1_data[CONF_CHAT_MODEL],
            _LOGGER,
        )

        try:
            self._validated = await validator.validate(
                self._step1_data[CONF_API_VERSION]
            )
            self._sampling_caps = await validator.capabilities()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Validation failed: %s", err)
            emsg = str(err).lower()

            if any(
                x in emsg
                for x in ["401", "403", "forbidden", "unauthorized", "invalid api key"]
            ):
                errors["base"] = "invalid_auth"
            elif any(x in emsg for x in ["not found", "deployment", "404"]):
                errors["base"] = "invalid_deployment"
            elif any(x in emsg for x in ["timeout", "connect", "network"]):
                errors["base"] = "cannot_connect"
            else:
                errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
            )

        return await self.async_step_params()

    async def async_step_params(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle parameter configuration step with dynamic schema based on capabilities."""
        assert self._step1_data is not None
        assert self._validated is not None

        cap_schema: VolDictType = {}

        def _num_selector(meta: dict[str, Any], *, mode: str = "box") -> NumberSelector:
            return NumberSelector(
                NumberSelectorConfig(
                    min=meta.get("min", 0),
                    max=meta.get("max", 2),
                    step=meta.get("step", 0.05) or 0.05,
                    mode=mode,
                )
            )

        # 1) Dynamic capabilities (temperature, max_tokens, etc.)
        for name, meta in (self._sampling_caps or {}).items():
            default = meta.get("default")
            if isinstance(default, (int, float)):
                cap_schema[vol.Optional(name, default=default)] = _num_selector(meta)
            else:
                cap_schema[vol.Optional(name, default=default)] = str

        # 2) Logging options
        cap_schema[vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL)] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=[
                        LOG_LEVEL_NONE,
                        LOG_LEVEL_ERROR,
                        LOG_LEVEL_INFO,
                        LOG_LEVEL_TRACE,
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        )
        cap_schema[vol.Optional(CONF_LOG_PAYLOAD_REQUEST, default=False)] = (
            BooleanSelector()
        )
        cap_schema[vol.Optional(CONF_LOG_PAYLOAD_RESPONSE, default=False)] = (
            BooleanSelector()
        )
        cap_schema[vol.Optional(CONF_LOG_SYSTEM_MESSAGE, default=False)] = (
            BooleanSelector()
        )
        cap_schema[
            vol.Optional(
                CONF_LOG_MAX_PAYLOAD_CHARS, default=DEFAULT_LOG_MAX_PAYLOAD_CHARS
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=100, max=500000, step=100, mode="box")
        )
        cap_schema[
            vol.Optional(CONF_LOG_MAX_SSE_LINES, default=DEFAULT_LOG_MAX_SSE_LINES)
        ] = NumberSelector(NumberSelectorConfig(min=1, max=200, step=1, mode="box"))

        # 3) Early wait
        cap_schema[
            vol.Optional(CONF_EARLY_WAIT_ENABLE, default=RECOMMENDED_EARLY_WAIT_ENABLE)
        ] = BooleanSelector()
        cap_schema[
            vol.Optional(
                CONF_EARLY_WAIT_SECONDS, default=RECOMMENDED_EARLY_WAIT_SECONDS
            )
        ] = NumberSelector(NumberSelectorConfig(min=1, max=120, step=1, mode="box"))

        # 4) Vocabulary + synonyms file
        cap_schema[
            vol.Optional(CONF_VOCABULARY_ENABLE, default=RECOMMENDED_VOCABULARY_ENABLE)
        ] = BooleanSelector()
        cap_schema[
            vol.Optional(
                CONF_SYNONYMS_FILE,
                default="custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json",
            )
        ] = str

        # 5) Utterances log
        cap_schema[vol.Optional(CONF_LOG_UTTERANCES, default=True)] = BooleanSelector()
        cap_schema[
            vol.Optional(
                CONF_UTTERANCES_LOG_PATH,
                default=".storage/azure_openai_conversation_utterances.log",
            )
        ] = str

        # 6) Local intent
        cap_schema[
            vol.Optional(
                CONF_LOCAL_INTENT_ENABLE, default=RECOMMENDED_LOCAL_INTENT_ENABLE
            )
        ] = BooleanSelector()

        # 7) Statistics
        cap_schema[vol.Optional(CONF_STATS_ENABLE, default=True)] = BooleanSelector()
        cap_schema[
            vol.Optional(
                CONF_STATS_COMPONENT_LOG_PATH,
                default=".storage/azure_openai_stats_component.log",
            )
        ] = str
        cap_schema[
            vol.Optional(
                CONF_STATS_LLM_LOG_PATH, default=".storage/azure_openai_stats_llm.log"
            )
        ] = str

        # 8) MCP server
        cap_schema[vol.Optional(CONF_MCP_ENABLED, default=RECOMMENDED_MCP_ENABLED)] = (
            BooleanSelector()
        )
        cap_schema[
            vol.Optional(CONF_MCP_TTL_SECONDS, default=RECOMMENDED_MCP_TTL_SECONDS)
        ] = NumberSelector(
            NumberSelectorConfig(min=300, max=7200, step=300, mode="box")
        )

        # 9) Tool calling
        cap_schema[
            vol.Optional(CONF_TOOLS_ENABLE, default=RECOMMENDED_TOOLS_ENABLE)
        ] = BooleanSelector()
        cap_schema[
            vol.Optional(CONF_TOOLS_WHITELIST, default=RECOMMENDED_TOOLS_WHITELIST)
        ] = str
        cap_schema[
            vol.Optional(
                CONF_TOOLS_MAX_ITERATIONS, default=RECOMMENDED_TOOLS_MAX_ITERATIONS
            )
        ] = NumberSelector(NumberSelectorConfig(min=1, max=50, step=1, mode="box"))
        cap_schema[
            vol.Optional(
                CONF_TOOLS_MAX_CALLS_PER_MINUTE,
                default=RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
            )
        ] = NumberSelector(NumberSelectorConfig(min=1, max=1000, step=1, mode="box"))
        cap_schema[
            vol.Optional(
                CONF_TOOLS_PARALLEL_EXECUTION,
                default=RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
            )
        ] = BooleanSelector()

        # 10) Sliding window
        cap_schema[
            vol.Optional(
                CONF_SLIDING_WINDOW_ENABLE, default=RECOMMENDED_SLIDING_WINDOW_ENABLE
            )
        ] = BooleanSelector()

        sliding_enabled = (user_input or {}).get(
            CONF_SLIDING_WINDOW_ENABLE, RECOMMENDED_SLIDING_WINDOW_ENABLE
        )
        if sliding_enabled:
            cap_schema[
                vol.Optional(
                    CONF_SLIDING_WINDOW_MAX_TOKENS,
                    default=RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
                )
            ] = NumberSelector(
                NumberSelectorConfig(min=1000, max=16000, step=500, mode="box")
            )
            cap_schema[
                vol.Optional(
                    CONF_SLIDING_WINDOW_PRESERVE_SYSTEM,
                    default=RECOMMENDED_SLIDING_WINDOW_PRESERVE_SYSTEM,
                )
            ] = BooleanSelector()

        schema = vol.Schema(cap_schema)

        # First visit: show form
        if user_input is None:
            return self.async_show_form(step_id="params", data_schema=schema)

        # Validate/clean user_input
        errors: dict[str, str] = {}
        cleaned: dict[str, Any] = {}

        for fld, val in user_input.items():
            if fld in (self._sampling_caps or {}):
                meta = self._sampling_caps[fld]
                default = meta.get("default")
                if isinstance(default, (int, float)):
                    try:
                        sval = str(val)
                        num_val: int | float = float(sval) if "." in sval else int(sval)
                        min_val = meta.get("min", 0)
                        max_val = meta.get("max", float("inf"))
                        if num_val < min_val or num_val > max_val:
                            errors[fld] = "value_out_of_range"
                        else:
                            cleaned[fld] = num_val
                    except (ValueError, TypeError):
                        errors[fld] = "invalid_number"
                else:
                    cleaned[fld] = val
            else:
                # Non-capability options (selectors/strings/bools)
                cleaned[fld] = val

        if errors:
            return self.async_show_form(
                step_id="params", data_schema=schema, errors=errors
            )

        return await self._async_create_entry(options=cleaned)

    async def _async_create_entry(
        self, *, options: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Create the config entry with defaults and dynamic options."""
        assert self._step1_data is not None
        assert self._validated is not None

        unique_id = (
            f"{normalize_azure_endpoint(self._step1_data[CONF_API_BASE])}"
            f"::{self._step1_data[CONF_CHAT_MODEL]}"
        )

        # ✅ Support both real HA coroutine and tests patching with plain MagicMock
        await _maybe_await(self.async_set_unique_id(unique_id))
        self._abort_if_unique_id_configured()

        api_version = (
            self._validated.get("api_version") or self._step1_data[CONF_API_VERSION]
        )
        chat_token_param = _pick_chat_token_param(
            model=self._step1_data[CONF_CHAT_MODEL], api_version=api_version
        )

        base_opts: dict[str, Any] = {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            "token_param": chat_token_param,
            CONF_API_VERSION: api_version,
            CONF_EXPOSED_ENTITIES_LIMIT: RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
            # logging defaults
            CONF_LOG_LEVEL: DEFAULT_LOG_LEVEL,
            CONF_LOG_PAYLOAD_REQUEST: False,
            CONF_LOG_PAYLOAD_RESPONSE: False,
            CONF_LOG_SYSTEM_MESSAGE: False,
            CONF_LOG_MAX_PAYLOAD_CHARS: DEFAULT_LOG_MAX_PAYLOAD_CHARS,
            CONF_LOG_MAX_SSE_LINES: DEFAULT_LOG_MAX_SSE_LINES,
            # early wait defaults
            CONF_EARLY_WAIT_ENABLE: RECOMMENDED_EARLY_WAIT_ENABLE,
            CONF_EARLY_WAIT_SECONDS: RECOMMENDED_EARLY_WAIT_SECONDS,
            # vocabulary defaults
            CONF_VOCABULARY_ENABLE: RECOMMENDED_VOCABULARY_ENABLE,
            CONF_SYNONYMS_FILE: "custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json",
            # local intent
            CONF_LOCAL_INTENT_ENABLE: RECOMMENDED_LOCAL_INTENT_ENABLE,
            # utterances log defaults
            CONF_LOG_UTTERANCES: True,
            CONF_UTTERANCES_LOG_PATH: ".storage/azure_openai_conversation_utterances.log",
            # MCP defaults
            CONF_MCP_ENABLED: RECOMMENDED_MCP_ENABLED,
            CONF_MCP_TTL_SECONDS: RECOMMENDED_MCP_TTL_SECONDS,
            # tools defaults
            CONF_TOOLS_ENABLE: RECOMMENDED_TOOLS_ENABLE,
            CONF_TOOLS_WHITELIST: RECOMMENDED_TOOLS_WHITELIST,
            CONF_TOOLS_MAX_ITERATIONS: RECOMMENDED_TOOLS_MAX_ITERATIONS,
            CONF_TOOLS_MAX_CALLS_PER_MINUTE: RECOMMENDED_TOOLS_MAX_CALLS_PER_MINUTE,
            CONF_TOOLS_PARALLEL_EXECUTION: RECOMMENDED_TOOLS_PARALLEL_EXECUTION,
            # sliding window defaults
            CONF_SLIDING_WINDOW_ENABLE: RECOMMENDED_SLIDING_WINDOW_ENABLE,
            CONF_SLIDING_WINDOW_MAX_TOKENS: RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS,
            CONF_SLIDING_WINDOW_PRESERVE_SYSTEM: RECOMMENDED_SLIDING_WINDOW_PRESERVE_SYSTEM,
            # stats defaults
            CONF_STATS_ENABLE: True,
            CONF_STATS_COMPONENT_LOG_PATH: ".storage/azure_openai_stats_component.log",
            CONF_STATS_LLM_LOG_PATH: ".storage/azure_openai_stats_llm.log",
        }

        base_opts.update(dict(options))

        return self.async_create_entry(
            title=f"Azure OpenAI – {self._step1_data[CONF_CHAT_MODEL]}",
            data={
                CONF_API_KEY: self._step1_data[CONF_API_KEY],
                CONF_API_BASE: self._step1_data[CONF_API_BASE],
                CONF_CHAT_MODEL: self._step1_data[CONF_CHAT_MODEL],
            },
            options=base_opts,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: D401
        """Return the options flow handler."""
        from .options_flow import AzureOpenAIOptionsFlow  # lazy import to cut deps

        return AzureOpenAIOptionsFlow(config_entry)
