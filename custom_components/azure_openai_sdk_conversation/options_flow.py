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
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,  
    RECOMMENDED_MAX_TOKENS,  
    RECOMMENDED_REASONING_EFFORT,  
    RECOMMENDED_TEMPERATURE,  
    RECOMMENDED_TOP_P,  
    RECOMMENDED_WEB_SEARCH,  
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,  
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,  
)  
from .utils import APIVersionManager  
  
_LOGGER = logging.getLogger(__name__)  
  
  
class AzureOpenAIOptionsFlow(OptionsFlow):  
    """Handle options flow for Azure OpenAI SDK Conversation."""  
  
    def __init__(self, config_entry: ConfigEntry) -> None:  
        """Initialize options flow."""  
        self.config_entry = config_entry  
  
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  
        """Manage the options."""  
        if user_input is not None:  
            return self.async_create_entry(title="", data=user_input)  
  
        schema = vol.Schema(  
            {  
                vol.Optional(  
                    CONF_RECOMMENDED,  
                    default=self.config_entry.options.get(CONF_RECOMMENDED, False),  
                ): BooleanSelector(),  
                vol.Optional(  
                    CONF_PROMPT,  
                    default=self.config_entry.options.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT),  
                ): TemplateSelector(),  
                vol.Optional(  
                    CONF_TEMPERATURE,  
                    default=self.config_entry.options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),  
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
                    default=self.config_entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),  
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
                    default=self.config_entry.options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),  
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
            }  
        )  
  
        # Aggiungi opzioni per modelli "o*" (reasoning)  
        model = self.config_entry.data.get("chat_model", "").lower()  
        if model.startswith("o"):  
            schema = schema.extend(  
                {  
                    vol.Optional(  
                        CONF_REASONING_EFFORT,  
                        default=self.config_entry.options.get(CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT),  
                    ): SelectSelector(  
                        SelectSelectorConfig(  
                            options=["low", "medium", "high"],  
                            mode=SelectSelectorMode.DROPDOWN,  
                        )  
                    ),  
                }  
            )  
  
        # Opzioni avanzate per API version  
        current_version = self.config_entry.options.get(  
            CONF_API_VERSION, self.config_entry.data.get(CONF_API_VERSION, "2025-03-01-preview")  
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
  
        # Opzioni per web search (se implementato)  
        schema = schema.extend(  
            {  
                vol.Optional(  
                    CONF_WEB_SEARCH,  
                    default=self.config_entry.options.get(CONF_WEB_SEARCH, RECOMMENDED_WEB_SEARCH),  
                ): BooleanSelector(),  
            }  
        )  
        if self.config_entry.options.get(CONF_WEB_SEARCH, False):  
            schema = schema.extend(  
                {  
                    vol.Optional(  
                        CONF_WEB_SEARCH_CONTEXT_SIZE,  
                        default=self.config_entry.options.get(  
                            CONF_WEB_SEARCH_CONTEXT_SIZE, RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE  
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
                            CONF_WEB_SEARCH_USER_LOCATION, RECOMMENDED_WEB_SEARCH_USER_LOCATION  
                        ),  
                    ): BooleanSelector(),  
                }  
            )  
  
        return self.async_show_form(step_id="init", data_schema=schema)  
  
  
@callback  
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  
    """Get the options flow for this handler."""  
    return AzureOpenAIOptionsFlow(config_entry)  