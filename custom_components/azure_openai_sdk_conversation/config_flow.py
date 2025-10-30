# File: /usr/share/hassio/homeassistant/custom_components/azure_openai_sdk_conversation/config_flow.py
"""Config flow for Azure OpenAI SDK Conversation – version 2025.9+."""

from __future__ import annotations

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client  # noqa: F401
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)
from homeassistant.helpers.typing import VolDictType

from . import normalize_azure_endpoint
from .const import (
    CONF_API_BASE,
    CONF_API_VERSION,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_USER_LOCATION,
    CONF_EXPOSED_ENTITIES_LIMIT,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
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
)
from .utils import APIVersionManager, AzureOpenAILogger, AzureOpenAIValidator

_LOGGER = logging.getLogger(__name__)
_LOG = AzureOpenAILogger(__name__)

DEFAULT_API_VERSION = "2025-03-01-preview"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_BASE): str,
        vol.Required(CONF_CHAT_MODEL, default=RECOMMENDED_CHAT_MODEL): str,
        vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): str,
    }
)

# -----------------------------------------------------------------------------
class AzureOpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure OpenAI SDK Conversation."""

    VERSION = 2
    MINOR_VERSION = 3  # Early wait + vocabulary + utterances path

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._validated: dict[str, Any] | None = None
        self._sampling_caps: dict[str, dict[str, Any]] = {}
        self._step1_data: dict[str, Any] | None = None

    # --------------------------------------------------------------------- STEP 1
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step. Validates credentials and fetches capabilities."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        self._step1_data = {
            CONF_API_KEY: user_input[CONF_API_KEY],
            CONF_API_BASE: user_input[CONF_API_BASE].strip(),
            CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL].strip(),
            CONF_API_VERSION: user_input.get(CONF_API_VERSION, DEFAULT_API_VERSION).strip(),
        }

        errors: dict[str, str] = {}

        # ------------ VALIDATION WITH RETRY --------------------------------
        validator = AzureOpenAIValidator(
            self.hass,
            self._step1_data[CONF_API_KEY],
            self._step1_data[CONF_API_BASE],
            self._step1_data[CONF_CHAT_MODEL],
            _LOG,
        )

        try:
            self._validated = await validator.validate(self._step1_data[CONF_API_VERSION])
            self._sampling_caps = await validator.capabilities()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Validation failed: %s", err)
            # Improved mapping heuristics for UI
            emsg = str(err).lower()
            if any(x in emsg for x in ["401", "403", "forbidden", "unauthorized", "invalid api key"]):
                errors["base"] = "invalid_auth"
            elif any(x in emsg for x in ["not found", "deployment", "404"]):
                errors["base"] = "invalid_deployment"
            elif any(x in emsg for x in ["timeout", "connect", "network"]):
                errors["base"] = "cannot_connect"
            else:
                errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

        return await self.async_step_params()

    # ------------------------------------------------------------------ STEP 2
    async def async_step_params(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle parameter configuration step with dynamic schema based on capabilities."""
        assert self._step1_data is not None

        cap_schema: VolDictType = {}

        # build dynamic schema from capabilities
        def _num_selector(meta: dict[str, Any]) -> NumberSelector:
            return NumberSelector(
                NumberSelectorConfig(
                    min=meta.get("min", 0),
                    max=meta.get("max", 2),
                    step=meta.get("step", 0.05) or 0.05,
                    mode="box",  # Improved UI
                )
            )

        for name, meta in self._sampling_caps.items():
            default = meta.get("default")
            if isinstance(default, (int, float)):
                cap_schema[vol.Optional(name, default=default)] = _num_selector(meta)
            else:
                cap_schema[vol.Optional(name, default=default)] = str

        # Added log settings (we keep the UI consistent)
        cap_schema[vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL)] = SelectSelector(
            SelectSelectorConfig(
                options=[LOG_LEVEL_NONE, LOG_LEVEL_ERROR, LOG_LEVEL_INFO, LOG_LEVEL_TRACE],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        cap_schema[vol.Optional(CONF_LOG_PAYLOAD_REQUEST, default=False)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_LOG_PAYLOAD_RESPONSE, default=False)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_LOG_SYSTEM_MESSAGE, default=False)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_LOG_MAX_PAYLOAD_CHARS, default=DEFAULT_LOG_MAX_PAYLOAD_CHARS)] = NumberSelector(
            NumberSelectorConfig(min=100, max=500000, step=100, mode="box")
        )
        cap_schema[vol.Optional(CONF_LOG_MAX_SSE_LINES, default=DEFAULT_LOG_MAX_SSE_LINES)] = NumberSelector(
            NumberSelectorConfig(min=1, max=200, step=1, mode="box")
        )

        # Early wait: enable and seconds
        cap_schema[vol.Optional(CONF_EARLY_WAIT_ENABLE, default=RECOMMENDED_EARLY_WAIT_ENABLE)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_EARLY_WAIT_SECONDS, default=RECOMMENDED_EARLY_WAIT_SECONDS)] = NumberSelector(
            NumberSelectorConfig(min=1, max=120, step=1, mode="box")
        )

        # Vocabulary: enable and synonyms file
        cap_schema[vol.Optional(CONF_VOCABULARY_ENABLE, default=RECOMMENDED_VOCABULARY_ENABLE)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_SYNONYMS_FILE, default="custom_components/azure_openai_sdk_conversation/assist_synonyms_it.json")] = str

        # Log utterances: enable and file path
        cap_schema[vol.Optional(CONF_LOG_UTTERANCES, default=True)] = BooleanSelector()
        cap_schema[vol.Optional(CONF_UTTERANCES_LOG_PATH, default=".storage/azure_openai_conversation_utterances.log")] = str

        if not cap_schema:
            # nothing extra to ask
            return self._create_entry(options={})

        errors: dict[str, str] = {}
        if user_input is not None:
            # type-cast numbers with improved validation
            cleaned: dict[str, Any] = {}
            for fld, val in user_input.items():
                if fld in self._sampling_caps:
                    meta = self._sampling_caps[fld]
                    if isinstance(meta.get("default"), (int, float)):
                        try:
                            sval = str(val)
                            num_val = float(sval) if "." in sval else int(sval)
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
                    # Extra options (log, early wait, vocabulary, utterances, etc.)
                    cleaned[fld] = val

            if not errors:
                return self._create_entry(options=cleaned)

            return self.async_show_form(step_id="params", data_schema=vol.Schema(cap_schema), errors=errors)

        return self.async_show_form(step_id="params", data_schema=vol.Schema(cap_schema))

    # ---------------------------------------------------------------- create
    def _create_entry(self, *, options: Mapping[str, Any]) -> ConfigFlowResult:
        """Create the config entry with defaults and dynamic options."""
        assert self._step1_data is not None
        assert self._validated is not None

        unique_id = (
            f"{normalize_azure_endpoint(self._step1_data[CONF_API_BASE])}"
            f"::{self._step1_data[CONF_CHAT_MODEL]}"
        )
        self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Robust calculation of the initial token_param for Chat:
        # - gpt-5 / gpt-4.1 / gpt-4.2 => max_completion_tokens
        # - others => based on api-version (>= 2025-03 => max_completion_tokens, otherwise max_tokens)
        def _ver_date_tuple(ver: str) -> tuple[int, int, int]:
            core = (ver or "").split("-preview")[0]
            parts = core.split("-")
            try:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:  # noqa: BLE001
                return (1900, 1, 1)

        model_l = (self._step1_data[CONF_CHAT_MODEL] or "").lower()
        if model_l.startswith("gpt-5") or model_l.startswith("gpt-4.1") or model_l.startswith("gpt-4.2"):
            chat_token_param = "max_completion_tokens"
        else:
            y, m, d = _ver_date_tuple(self._validated["api_version"])
            chat_token_param = "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"

        base_opts: dict[str, Any] = {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            "token_param": chat_token_param,
            CONF_API_VERSION: self._validated["api_version"],
            CONF_EXPOSED_ENTITIES_LIMIT: RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
            # default logging options
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
            # utterances log defaults
            CONF_LOG_UTTERANCES: True,
            CONF_UTTERANCES_LOG_PATH: ".storage/azure_openai_conversation_utterances.log",
        }
        base_opts.update(options)

        return self.async_create_entry(
            title=f"Azure OpenAI – {self._step1_data[CONF_CHAT_MODEL]}",
            data={
                CONF_API_KEY: self._step1_data[CONF_API_KEY],
                CONF_API_BASE: self._step1_data[CONF_API_BASE],
                CONF_CHAT_MODEL: self._step1_data[CONF_CHAT_MODEL],
            },
            options=base_opts,
        )

    # ---------------------------------------------------------------- options
    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: D401
        from .options_flow import AzureOpenAIOptionsFlow  # lazy import to cut deps

        return AzureOpenAIOptionsFlow(config_entry)