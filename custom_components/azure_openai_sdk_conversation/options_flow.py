"""Options flow per Azure OpenAI SDK Conversation – versione ≥ 2025.9."""  
  
from __future__ import annotations  
  
import logging  
from typing import Any, Mapping  
  
import voluptuous as vol  
from homeassistant.components.zone import ENTITY_ID_HOME  
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow  
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY  
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
from openai import AsyncAzureOpenAI  
  
from . import normalize_azure_endpoint  
from .const import (  
    CONF_API_BASE,  
    CONF_API_TIMEOUT,  
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
    RECOMMENDED_API_TIMEOUT,  
    UNSUPPORTED_MODELS,  
    WEB_SEARCH_MODELS,  
)  
from .utils import APIVersionManager  
  
_LOGGER = logging.getLogger(__name__)  
  
  
class AzureOpenAIOptionsFlow(OptionsFlow):  
    """Gestione delle opzioni per una config-entry esistente."""  
  
    def __init__(self, config_entry: ConfigEntry) -> None:  
        self.config_entry = config_entry  
        self.last_rendered_recommended = config_entry.options.get(CONF_RECOMMENDED, False)  
        # Pre-popoliamo con le versioni note; se la versione in uso non è nota, la aggiungiamo.  
        self.available_api_versions: list[str] = list(APIVersionManager._KNOWN)  # type: ignore[attr-defined]  
        current_ver = config_entry.options.get(CONF_API_VERSION)  
        if current_ver and current_ver not in self.available_api_versions:  
            self.available_api_versions.insert(0, current_ver)  
  
    # --------------------------------------------------------------------- STEP unico  
    async def async_step_init(  
        self, user_input: dict[str, Any] | None = None  
    ) -> ConfigFlowResult:  # noqa: D401  
        base_options: dict[str, Any] = {**self.config_entry.data, **self.config_entry.options}  
  
        errors: dict[str, str] = {}  
  
        # --------------------------- salvataggio ---------------------------  
        if user_input is not None:  
            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:  
                # Casting numerico  
                for fld in (CONF_TEMPERATURE, CONF_TOP_P):  
                    if fld in user_input:  
                        user_input[fld] = float(user_input[fld])  
                for fld in (CONF_MAX_TOKENS, CONF_API_TIMEOUT):  
                    if fld in user_input:  
                        user_input[fld] = int(user_input[fld])  
  
                if user_input.get(CONF_CHAT_MODEL) in UNSUPPORTED_MODELS:  
                    errors[CONF_CHAT_MODEL] = "model_not_supported"  
  
                if (  
                    user_input.get(CONF_WEB_SEARCH)  
                    and user_input.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)  
                    not in WEB_SEARCH_MODELS  
                ):  
                    errors[CONF_WEB_SEARCH] = "web_search_not_supported"  
  
                cleaned = {k: v for k, v in user_input.items() if v not in ("", None)}  
  
                if not errors:  
                    _LOGGER.debug(  
                        "Saving AzureOpenAI options: %s",  
                        {  
                            k: ("***" if k == CONF_API_KEY else v)  
                            for k, v in cleaned.items()  
                        },  
                    )  
                    return self.async_create_entry(title="", data=cleaned)  
  
            # L’utente ha commutato il flag “recommended”: rielabora schema  
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]  
            base_options.update(user_input)  
  
        # --------------------------- rendering form ------------------------  
        schema = self._option_schema(self.hass, base_options)  
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema), errors=errors)  
  
    # ------------------------------------------------------------------ schema helper  
    def _option_schema(self, hass: HomeAssistant, options: Mapping[str, Any]) -> VolDictType:  
        """Genera dinamicamente lo schema dell’options-flow."""  
        hass_apis: list[SelectOptionDict] = [  
            SelectOptionDict(label=api.name, value=api.id) for api in llm.async_get_apis(hass)  
        ]  
        suggested_llm_apis = options.get("llm_hass_api")  
        if isinstance(suggested_llm_apis, str):  
            suggested_llm_apis = [suggested_llm_apis]  
  
        schema: VolDictType = {  
            vol.Optional(  
                CONF_PROMPT,  
                description={  
                    "suggested_value": options.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT)  
                },  
            ): TemplateSelector(),  
            vol.Optional(  
                "llm_hass_api",  
                description={"suggested_value": suggested_llm_apis},  
            ): SelectSelector(  
                SelectSelectorConfig(options=hass_apis, multiple=True)  
            ),  
            vol.Required(  
                CONF_RECOMMENDED,  
                default=options.get(CONF_RECOMMENDED, False),  
            ): bool,  
        }  
  
        # In modalità “recommended” chiediamo solo i 3 campi base  
        if options.get(CONF_RECOMMENDED):  
            return schema  
  
        # ---------- campi avanzati ---------------------------------------  
        api_version_options = [  
            SelectOptionDict(label=v, value=v) for v in self.available_api_versions  
        ]  
  
        schema.update(  
            {  
                vol.Optional(  
                    CONF_API_BASE,  
                    description={"suggested_value": options.get(CONF_API_BASE)},  
                    default=options.get(CONF_API_BASE, ""),  
                ): str,  
                vol.Optional(  
                    CONF_CHAT_MODEL,  
                    description={"suggested_value": options.get(CONF_CHAT_MODEL)},  
                    default=options.get(CONF_CHAT_MODEL, ""),  
                ): str,  
                vol.Optional(  
                    CONF_API_VERSION,  
                    description={"suggested_value": options.get(CONF_API_VERSION)},  
                    default=options.get(CONF_API_VERSION, APIVersionManager.best_for_model("")),  # type: ignore[arg-type]  
                ): SelectSelector(  
                    SelectSelectorConfig(  
                        options=api_version_options,  
                        mode=SelectSelectorMode.DROPDOWN,  
                    )  
                ),  
                vol.Optional(  
                    CONF_MAX_TOKENS,  
                    description={"suggested_value": options.get(CONF_MAX_TOKENS)},  
                    default=RECOMMENDED_MAX_TOKENS,  
                ): int,  
                vol.Optional(  
                    CONF_TOP_P,  
                    description={"suggested_value": options.get(CONF_TOP_P)},  
                    default=RECOMMENDED_TOP_P,  
                ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),  
                vol.Optional(  
                    CONF_TEMPERATURE,  
                    description={"suggested_value": options.get(CONF_TEMPERATURE)},  
                    default=RECOMMENDED_TEMPERATURE,  
                ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),  
                vol.Optional(  
                    CONF_REASONING_EFFORT,  
                    description={"suggested_value": options.get(CONF_REASONING_EFFORT)},  
                    default=RECOMMENDED_REASONING_EFFORT,  
                ): SelectSelector(  
                    SelectSelectorConfig(  
                        options=["low", "medium", "high"],  
                        translation_key=CONF_REASONING_EFFORT,  
                        mode=SelectSelectorMode.DROPDOWN,  
                    )  
                ),  
                vol.Optional(  
                    CONF_WEB_SEARCH,  
                    description={"suggested_value": options.get(CONF_WEB_SEARCH)},  
                    default=RECOMMENDED_WEB_SEARCH,  
                ): bool,  
                vol.Optional(  
                    CONF_WEB_SEARCH_CONTEXT_SIZE,  
                    description={"suggested_value": options.get(CONF_WEB_SEARCH_CONTEXT_SIZE)},  
                    default=RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,  
                ): SelectSelector(  
                    SelectSelectorConfig(  
                        options=["low", "medium", "high"],  
                        translation_key=CONF_WEB_SEARCH_CONTEXT_SIZE,  
                        mode=SelectSelectorMode.DROPDOWN,  
                    )  
                ),  
                vol.Optional(  
                    CONF_WEB_SEARCH_USER_LOCATION,  
                    description={  
                        "suggested_value": options.get(CONF_WEB_SEARCH_USER_LOCATION)  
                    },  
                    default=RECOMMENDED_WEB_SEARCH_USER_LOCATION,  
                ): bool,  
                vol.Optional(  
                    CONF_API_TIMEOUT,  
                    description={"suggested_value": options.get(CONF_API_TIMEOUT)},  
                    default=RECOMMENDED_API_TIMEOUT,  
                ): NumberSelector(NumberSelectorConfig(min=5, max=120, step=1)),  
            }  
        )  
        return schema  
  
    # ------------------------------------------------------------------ extra helper (facoltativo)  
    async def _approximate_location(self, hass: HomeAssistant) -> dict[str, str]:  
        """Stima la location dell’utente partendo dalla zone.home (facoltativa)."""  
        location: dict[str, str] = {}  
        zone_home = hass.states.get(ENTITY_ID_HOME)  
        if zone_home is None:  
            return location  
  
        api_base = self.config_entry.data[CONF_API_BASE]  
        root = normalize_azure_endpoint(api_base).rstrip("/").removesuffix("/openai")  
        client = AsyncAzureOpenAI(  
            api_key=self.config_entry.data[CONF_API_KEY],  
            api_version=APIVersionManager.best_for_model(""),  # any  
            azure_endpoint=root,  
            http_client=get_async_client(hass),  
        )  
  
        prompt = (  
            f"Where are the following coordinates located: "  
            f"({zone_home.attributes[ATTR_LATITUDE]}, {zone_home.attributes[ATTR_LONGITUDE]})?"  
        )  
  
        resp = await client.chat.completions.create(  
            model=self.config_entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),  
            messages=[{"role": "user", "content": prompt}],  
            max_tokens=32,  
        )  
        # risposta in plain-text, nessuna elaborazione ulteriore  
        location["raw"] = resp.choices[0].message.content  # type: ignore[index]  
        return location  