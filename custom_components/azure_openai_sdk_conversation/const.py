# File: /usr/share/hassio/homeassistant/custom_components/azure_openai_sdk_conversation/const.py  
"""Costanti per l'integrazione Azure OpenAI SDK Conversation."""  
from __future__ import annotations  
  
from typing import Final, List  
from homeassistant.const import Platform  
  
# Dominio dell'integrazione  
DOMAIN: Final[str] = "azure_openai_sdk_conversation"  
  
# Piattaforme supportate  
PLATFORMS: Final[List[Platform]] = [Platform.CONVERSATION]  
  
# Chiavi di configurazione (schema/entry) - convenzione CONF_*  
CONF_API_BASE: Final[str] = "api_base"            # Es: https://<resource>.openai.azure.com  
CONF_API_KEY: Final[str] = "api_key"  
CONF_CHAT_MODEL: Final[str] = "chat_model"        # Nome deployment (Azure) o model  
CONF_DEPLOYMENT: Final[str] = CONF_CHAT_MODEL     # Alias usato in alcune versioni del flow  
CONF_API_VERSION: Final[str] = "api_version"      # Es: 2025-01-01-preview / 2025-03-01-preview  
CONF_TOKEN_PARAM: Final[str] = "token_param"      # max_tokens / max_completion_tokens / max_output_tokens  
CONF_SYSTEM_PROMPT: Final[str] = "system_prompt"  
CONF_PROMPT: Final[str] = "prompt"                # Alias richiesto dal config_flow (backcompat)  
  
# Parametri modello come CONF_* (usati in config_flow/options_flow)  
CONF_TEMPERATURE: Final[str] = "temperature"  
CONF_TOP_P: Final[str] = "top_p"  
CONF_MAX_TOKENS: Final[str] = "max_tokens"  
CONF_API_TIMEOUT: Final[str] = "api_timeout"  
CONF_REASONING_EFFORT: Final[str] = "reasoning_effort"  
CONF_EXPOSED_ENTITIES_LIMIT: Final[str] = "exposed_entities_limit"  
  
# Impostazioni di ricerca web (se supportate dal flow/options)  
CONF_WEB_SEARCH: Final[str] = "web_search"  
CONF_WEB_SEARCH_CONTEXT_SIZE: Final[str] = "web_search_context_size"  
CONF_WEB_SEARCH_USER_LOCATION: Final[str] = "web_search_user_location"  
  
# Flag per UI/flow (es. schema "preset consigliato")  
CONF_RECOMMENDED: Final[str] = "recommended"  
  
# Impostazioni log  
CONF_LOG_LEVEL: Final[str] = "log_level"  # none | error | info | trace  
CONF_LOG_PAYLOAD_REQUEST: Final[str] = "log_payload_request"  
CONF_LOG_PAYLOAD_RESPONSE: Final[str] = "log_payload_response"  
CONF_LOG_SYSTEM_MESSAGE: Final[str] = "log_system_message"  
CONF_LOG_MAX_PAYLOAD_CHARS: Final[str] = "log_max_payload_chars"  
CONF_LOG_MAX_SSE_LINES: Final[str] = "log_max_sse_lines"  
  
LOG_LEVEL_NONE: Final[str] = "none"  
LOG_LEVEL_ERROR: Final[str] = "error"  
LOG_LEVEL_INFO: Final[str] = "info"  
LOG_LEVEL_TRACE: Final[str] = "trace"  
  
DEFAULT_LOG_LEVEL: Final[str] = LOG_LEVEL_ERROR  
DEFAULT_LOG_MAX_PAYLOAD_CHARS: Final[int] = 12000  
DEFAULT_LOG_MAX_SSE_LINES: Final[int] = 10  
  
# Early wait configurabile (nuove chiavi)  
CONF_EARLY_WAIT_ENABLE: Final[str] = "early_wait_enable"  
CONF_EARLY_WAIT_SECONDS: Final[str] = "early_wait_seconds"  
  
# Vocabolario / sinonimi  
CONF_VOCABULARY_ENABLE: Final[str] = "vocabulary_enable"  
CONF_SYNONYMS_FILE: Final[str] = "synonyms_file"  
  
# Utterances log (nuove chiavi corrette)  
CONF_LOG_UTTERANCES: Final[str] = "log_utterances"  
CONF_UTTERANCES_LOG_PATH: Final[str] = "utterances_log_path"  
  
# Retrocompatibilità: chiavi/alias legacy  
CONF_EARLY_TIMEOUT_SECONDS: Final[str] = "early_timeout_seconds"  # alias legacy per early wait seconds  
  
# Chiavi errori per UI/config flow  
ERROR_CANNOT_CONNECT: Final[str] = "cannot_connect"  
ERROR_INVALID_AUTH: Final[str] = "invalid_auth"  
ERROR_INVALID_DEPLOYMENT: Final[str] = "invalid_deployment"  
ERROR_UNKNOWN: Final[str] = "unknown"  
  
# Alias per opzioni (backcompat con versioni precedenti che usano OPT_*)  
OPT_TEMPERATURE: Final[str] = CONF_TEMPERATURE  
OPT_TOP_P: Final[str] = CONF_TOP_P  
OPT_MAX_TOKENS: Final[str] = CONF_MAX_TOKENS  
OPT_API_TIMEOUT: Final[str] = CONF_API_TIMEOUT  
OPT_REASONING_EFFORT: Final[str] = CONF_REASONING_EFFORT  
OPT_EXPOSED_ENTITIES_LIMIT: Final[str] = CONF_EXPOSED_ENTITIES_LIMIT  
  
# Prompt di sistema di default (puoi personalizzarlo nelle opzioni dell'entry)  
DEFAULT_SYSTEM_PROMPT: Final[str] = (  
    "Sei un assistente conversazionale integrato in Home Assistant. "  
    "Rispondi in modo conciso e utile nella lingua dell'utente: {{ user_language }}. "  
    "Nome della casa: {{ name }}. "  
    "Istruzioni:\n"  
    "- Non inventare entità o stati che non conosci.\n"  
    "- Se non hai abbastanza contesto, chiedi una breve chiarificazione.\n"  
    "- Se la richiesta non riguarda la casa, rispondi comunque in modo utile e sintetico.\n\n"  
    "Messaggio utente: {{ user_text }}"  
)  
  
# Valori raccomandati per i parametri modello e opzioni  
RECOMMENDED_CHAT_MODEL: Final[str] = "gpt-4o-mini"          # Deployment consigliato di default  
RECOMMENDED_TEMPERATURE: Final[float] = 0.7  
RECOMMENDED_TOP_P: Final[float] = 1.0  
RECOMMENDED_MAX_TOKENS: Final[int] = 512  
RECOMMENDED_API_TIMEOUT: Final[int] = 30  
RECOMMENDED_REASONING_EFFORT: Final[str] = "medium"         # per modelli 'o*' (o1, o3, ecc.)  
RECOMMENDED_EXPOSED_ENTITIES_LIMIT: Final[int] = 500  
  
# Raccomandazioni per ricerca web (se abilitata dall'integrazione)  
RECOMMENDED_WEB_SEARCH: Final[bool] = False  
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE: Final[int] = 2000  
RECOMMENDED_WEB_SEARCH_USER_LOCATION: Final[bool] = False  
  
# Raccomandazioni Early Wait e Vocabolario  
RECOMMENDED_EARLY_WAIT_ENABLE: Final[bool] = True  
RECOMMENDED_EARLY_WAIT_SECONDS: Final[int] = 5  
RECOMMENDED_VOCABULARY_ENABLE: Final[bool] = True  
  
# Retrocompatibilità: alias legacy per recommended early timeout  
RECOMMENDED_EARLY_TIMEOUT_SECONDS: Final[int] = RECOMMENDED_EARLY_WAIT_SECONDS  
  
__all__ = [  
    # Domain / platforms  
    "DOMAIN",  
    "PLATFORMS",  
    # Config keys (CONF_*)  
    "CONF_API_BASE",  
    "CONF_API_KEY",  
    "CONF_CHAT_MODEL",  
    "CONF_DEPLOYMENT",  
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
    # Early wait + Vocabolario + Utterances  
    "CONF_EARLY_WAIT_ENABLE",  
    "CONF_EARLY_WAIT_SECONDS",  
    "CONF_VOCABULARY_ENABLE",  
    "CONF_SYNONYMS_FILE",  
    "CONF_LOG_UTTERANCES",  
    "CONF_UTTERANCES_LOG_PATH",  
    # Retrocompatibilità (alias)  
    "CONF_EARLY_TIMEOUT_SECONDS",  
    "RECOMMENDED_EARLY_TIMEOUT_SECONDS",  
    # Error keys  
    "ERROR_CANNOT_CONNECT",  
    "ERROR_INVALID_AUTH",  
    "ERROR_INVALID_DEPLOYMENT",  
    "ERROR_UNKNOWN",  
    # Option aliases (OPT_*)  
    "OPT_TEMPERATURE",  
    "OPT_TOP_P",  
    "OPT_MAX_TOKENS",  
    "OPT_API_TIMEOUT",  
    "OPT_REASONING_EFFORT",  
    "OPT_EXPOSED_ENTITIES_LIMIT",  
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
]  