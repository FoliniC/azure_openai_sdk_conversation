"""Config flow for Azure OpenAI SDK Conversation – versione 2025.9+."""  
  
from __future__ import annotations  
  
import logging  
from typing import Any, Mapping  
  
import openai  
import voluptuous as vol  
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow  
from homeassistant.const import CONF_API_KEY  
from homeassistant.core import HomeAssistant  
from homeassistant.helpers import llm  
from homeassistant.helpers.httpx_client import get_async_client  
from homeassistant.helpers.selector import (  
    NumberSelector,  
    NumberSelectorConfig,  
    SelectOptionDict,  
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
    DOMAIN,  
    RECOMMENDED_CHAT_MODEL,  
    RECOMMENDED_MAX_TOKENS,  
    RECOMMENDED_REASONING_EFFORT,  
    RECOMMENDED_TEMPERATURE,  
    RECOMMENDED_TOP_P,  
    RECOMMENDED_WEB_SEARCH,  
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,  
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,  
)  
from .utils import APIVersionManager, AzureOpenAILogger, AzureOpenAIValidator  
  
_LOGGER = logging.getLogger(__name__)  
_LOG = AzureOpenAILogger(__name__)  
  
DEFAULT_API_VERSION = "2025-01-01-preview"  
  
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
    VERSION = 2  
  
    def __init__(self) -> None:  
        self._validated: dict[str, Any] | None = None  
        self._sampling_caps: dict[str, dict[str, Any]] = {}  
        self._step1_data: dict[str, Any] | None = None  
  
    # --------------------------------------------------------------------- STEP 1  
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  
        if user_input is None:  
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)  
  
        self._step1_data = {  
            CONF_API_KEY: user_input[CONF_API_KEY],  
            CONF_API_BASE: user_input[CONF_API_BASE].strip(),  
            CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL].strip(),  
            CONF_API_VERSION: user_input.get(CONF_API_VERSION, DEFAULT_API_VERSION).strip(),  
        }  
  
        errors: dict[str, str] = {}  
  
        # ------------ VALIDAZIONE CON RETRY --------------------------------  
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
        except openai.AuthenticationError:  
            errors["base"] = "invalid_auth"  
        except openai.NotFoundError:  
            errors["base"] = "invalid_deployment"  
        except openai.APIConnectionError:  
            errors["base"] = "cannot_connect"  
        except Exception as err:  # pylint: disable=broad-except  
            _LOGGER.exception("Validation failed: %s", err)  
            errors["base"] = "unknown"  
  
        if errors:  
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)  
  
        return await self.async_step_params()  
  
    # ------------------------------------------------------------------ STEP 2  
    async def async_step_params(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  
        assert self._step1_data is not None  
        cap_schema: VolDictType = {}  
  
        # build dynamic schema from capabilities  
        def _num_selector(meta: dict[str, Any]) -> NumberSelector:  
            return NumberSelector(  
                NumberSelectorConfig(  
                    min=meta.get("min", 0),  
                    max=meta.get("max", 2),  
                    step=meta.get("step", 0.05) or 0.05,  
                )  
            )  
  
        for name, meta in self._sampling_caps.items():  
            default = meta.get("default")  
            if isinstance(default, (int, float)):  
                cap_schema[vol.Optional(name, default=default)] = _num_selector(meta)  
            else:  
                cap_schema[vol.Optional(name, default=default)] = str  
  
        if not cap_schema:  
            # nothing extra to ask  
            return self._create_entry(options={})  
  
        errors: dict[str, str] = {}  
        if user_input is not None:  
            # type-cast numbers  
            cleaned = {}  
            for fld, val in user_input.items():  
                if fld in self._sampling_caps:  
                    meta = self._sampling_caps[fld]  
                    if isinstance(meta.get("default"), (int, float)):  
                        try:  
                            cleaned[fld] = float(val) if "." in str(val) else int(val)  
                        except Exception:  # pylint: disable=broad-except  
                            errors[fld] = "invalid_number"  
                    else:  
                        cleaned[fld] = val  
            if not errors:  
                return self._create_entry(options=cleaned)  
  
        return self.async_show_form(step_id="params", data_schema=vol.Schema(cap_schema), errors=errors)  
  
    # ---------------------------------------------------------------- create  
    def _create_entry(self, *, options: Mapping[str, Any]) -> ConfigFlowResult:  
        assert self._step1_data is not None  
        assert self._validated is not None  
  
        unique_id = (  
            f"{normalize_azure_endpoint(self._step1_data[CONF_API_BASE])}"  
            f"::{self._step1_data[CONF_CHAT_MODEL]}"  
        )  
        self.async_set_unique_id(unique_id)  
        self._abort_if_unique_id_configured()  
  
        base_opts = {  
            CONF_RECOMMENDED: False,  
            CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,  
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,  
            "token_param": self._validated["token_param"],  
            CONF_API_VERSION: self._validated["api_version"],  
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