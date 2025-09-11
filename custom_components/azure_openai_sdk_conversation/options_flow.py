"""Options flow per Azure OpenAI SDK Conversation."""  
from __future__ import annotations  
  
from typing import Any  
  
import voluptuous as vol  
from homeassistant.config_entries import ConfigEntry, OptionsFlow  
from homeassistant.data_entry_flow import FlowResult  
from homeassistant.helpers.selector import (  
  SelectOptionDict,  
  SelectSelector,  
  SelectSelectorConfig,  
  SelectSelectorMode,  
  TextSelector,  
  TextSelectorConfig,  
  NumberSelector,  
  NumberSelectorConfig,  
  NumberSelectorMode,  
  BooleanSelector,  
)  
  
from .utils import APIVersionManager  
  
CONF_CONV_API_VERSION = "conversation_api_version"  
_SENTINEL_SAME = "__same__"  
  
# Chiavi opzioni supportate  
CONF_ENDPOINT = "endpoint"  
CONF_DEPLOYMENT = "deployment"  
CONF_SYSTEM_MESSAGE = "system_message"  
CONF_API_VERSION = "api_version"  
CONF_MAX_TOKENS = "max_tokens"  
CONF_TEMPERATURE = "temperature"  
CONF_API_TIMEOUT = "api_timeout"  
CONF_FORCE_MODE = "force_responses_mode"  
  
CONF_ENABLE_SEARCH = "enable_web_search"  
CONF_BING_KEY = "bing_api_key"  
CONF_BING_ENDPOINT = "bing_endpoint"  
CONF_BING_MAX = "bing_max_results"  
  
# Debug SSE  
CONF_DEBUG_SSE = "debug_sse"  
CONF_DEBUG_SSE_LINES = "debug_sse_lines"  
  
  
class AzureOpenAIOptionsFlow(OptionsFlow):  
  """Gestione delle opzioni dell'integrazione."""  
  
  def __init__(self, config_entry: ConfigEntry) -> None:  
    self._entry = config_entry  
  
  async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:  
    """Schermata di opzioni avanzate."""  
    current = dict(self._entry.options)  
    data = dict(self._entry.data)  
  
    # Opzioni per api_version e conversation_api_version  
    versions = list(getattr(APIVersionManager, "_KNOWN", {}) or {})  
    if "2025-03-01-preview" not in versions:  
      versions.append("2025-03-01-preview")  
    versions = sorted(versions)  
  
    api_ver_options = [SelectOptionDict(label=v, value=v) for v in versions]  
  
    conv_api_options = [SelectOptionDict(label="Usa la stessa API version globale", value=_SENTINEL_SAME)]  
    conv_api_options.extend(SelectOptionDict(label=v, value=v) for v in versions)  
  
    # Opzioni per forza Responses/Chat  
    force_mode_options = [  
      SelectOptionDict(label="Automatico (in base al nome del deployment)", value="auto"),  
      SelectOptionDict(label="Forza Responses API", value="responses"),  
      SelectOptionDict(label="Forza Chat Completions", value="chat"),  
    ]  
  
    schema = vol.Schema(  
      {  
        # Endpoint e Deployment  
        vol.Optional(  
          CONF_ENDPOINT,  
          default=current.get(CONF_ENDPOINT, data.get("api_base", "")),  
        ): TextSelector(TextSelectorConfig(multiline=False)),  
        vol.Optional(  
          CONF_DEPLOYMENT,  
          default=current.get(CONF_DEPLOYMENT, data.get("chat_model", "")),  
        ): TextSelector(TextSelectorConfig(multiline=False)),  
  
        # System message  
        vol.Optional(  
          CONF_SYSTEM_MESSAGE,  
          default=current.get(CONF_SYSTEM_MESSAGE, "You are Home Assistant’s AI helper."),  
        ): TextSelector(TextSelectorConfig(multiline=True)),  
  
        # Versioni API  
        vol.Optional(  
          CONF_API_VERSION,  
          default=current.get(CONF_API_VERSION, data.get("api_version", "2025-03-01-preview")),  
        ): SelectSelector(SelectSelectorConfig(options=api_ver_options, mode=SelectSelectorMode.DROPDOWN)),  
        vol.Optional(  
          CONF_CONV_API_VERSION,  
          default=current.get(CONF_CONV_API_VERSION, _SENTINEL_SAME),  
        ): SelectSelector(SelectSelectorConfig(options=conv_api_options, mode=SelectSelectorMode.DROPDOWN)),  
  
        # Parametri modello  
        vol.Optional(  
          CONF_MAX_TOKENS,  
          default=current.get(CONF_MAX_TOKENS, 1024),  
        ): NumberSelector(NumberSelectorConfig(min=1, max=32768, step=1, mode=NumberSelectorMode.BOX)),  
        vol.Optional(  
          CONF_TEMPERATURE,  
          default=current.get(CONF_TEMPERATURE, 0.7),  
        ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.1, mode=NumberSelectorMode.BOX)),  
        vol.Optional(  
          CONF_API_TIMEOUT,  
          default=current.get(CONF_API_TIMEOUT, 30),  
        ): NumberSelector(NumberSelectorConfig(min=5, max=120, step=1, mode=NumberSelectorMode.BOX)),  
  
        # Forza modalità Responses/Chat  
        vol.Optional(  
          CONF_FORCE_MODE,  
          default=current.get(CONF_FORCE_MODE, "auto"),  
        ): SelectSelector(SelectSelectorConfig(options=force_mode_options, mode=SelectSelectorMode.DROPDOWN)),  
  
        # Web search  
        vol.Optional(  
          CONF_ENABLE_SEARCH,  
          default=current.get(CONF_ENABLE_SEARCH, False),  
        ): BooleanSelector(),  
        vol.Optional(  
          CONF_BING_KEY,  
          default=current.get(CONF_BING_KEY, ""),  
        ): TextSelector(TextSelectorConfig(multiline=False)),  
        vol.Optional(  
          CONF_BING_ENDPOINT,  
          default=current.get(CONF_BING_ENDPOINT, ""),  
        ): TextSelector(TextSelectorConfig(multiline=False)),  
        vol.Optional(  
          CONF_BING_MAX,  
          default=current.get(CONF_BING_MAX, 5),  
        ): NumberSelector(NumberSelectorConfig(min=1, max=25, step=1, mode=NumberSelectorMode.BOX)),  
  
        # Debug SSE  
        vol.Optional(  
          CONF_DEBUG_SSE,  
          default=current.get(CONF_DEBUG_SSE, False),  
        ): BooleanSelector(),  
        vol.Optional(  
          CONF_DEBUG_SSE_LINES,  
          default=current.get(CONF_DEBUG_SSE_LINES, 10),  
        ): NumberSelector(NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)),  
      }  
    )  
  
    if user_input is None:  
      return self.async_show_form(step_id="init", data_schema=schema)  
  
    # Salvataggio opzioni, preservando tutte le altre  
    new_options = dict(self._entry.options)  
  
    # Campi diretti  
    for key in (  
      CONF_ENDPOINT,  
      CONF_DEPLOYMENT,  
      CONF_SYSTEM_MESSAGE,  
      CONF_API_VERSION,  
      CONF_MAX_TOKENS,  
      CONF_TEMPERATURE,  
      CONF_API_TIMEOUT,  
      CONF_FORCE_MODE,  
      CONF_ENABLE_SEARCH,  
      CONF_BING_KEY,  
      CONF_BING_ENDPOINT,  
      CONF_BING_MAX,  
      CONF_DEBUG_SSE,  
      CONF_DEBUG_SSE_LINES,  
    ):  
      if key in user_input:  
        if user_input[key] in (None, ""):  
          new_options.pop(key, None)  
        else:  
          new_options[key] = user_input[key]  
  
    # conversation_api_version con sentinel  
    sel = user_input.get(CONF_CONV_API_VERSION, _SENTINEL_SAME)  
    if sel == _SENTINEL_SAME:  
      new_options.pop(CONF_CONV_API_VERSION, None)  
    else:  
      new_options[CONF_CONV_API_VERSION] = sel  
  
    return self.async_create_entry(title="", data=new_options)  