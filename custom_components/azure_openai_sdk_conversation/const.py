"""Constants for Azure OpenAI SDK Conversation integration."""  
from __future__ import annotations  
  
import logging

# Logger
LOGGER = logging.getLogger(__name__)

# Integration domain  
DOMAIN = "azure_openai_sdk_conversation"  
  
# Configuration keys  
CONF_API_BASE = "api_base"  
CONF_API_KEY = "api_key"  
CONF_CHAT_MODEL = "chat_model"  
CONF_MAX_TOKENS = "max_tokens"  
CONF_PROMPT = "prompt"  
CONF_REASONING_EFFORT = "reasoning_effort"  
CONF_RECOMMENDED = "recommended"  
CONF_TEMPERATURE = "temperature"  
CONF_TOP_P = "top_p"  
CONF_WEB_SEARCH = "web_search"  
CONF_WEB_SEARCH_CITY = "web_search_city"  
CONF_WEB_SEARCH_CONTEXT_SIZE = "web_search_context_size"  
CONF_WEB_SEARCH_COUNTRY = "web_search_country"  
CONF_WEB_SEARCH_REGION = "web_search_region"  
CONF_WEB_SEARCH_TIMEZONE = "web_search_timezone"  
CONF_WEB_SEARCH_USER_LOCATION = "web_search_user_location"  
CONF_API_TIMEOUT = "api_timeout"  
CONF_API_VERSION = "api_version"  
CONF_FILENAMES = "filenames"  
  
# Recommended values for configuration options  
RECOMMENDED_CHAT_MODEL = "o1"  
RECOMMENDED_MAX_TOKENS = 300  
RECOMMENDED_REASONING_EFFORT = "medium"  
RECOMMENDED_TEMPERATURE = 1.0  
RECOMMENDED_TOP_P = 1.0  
RECOMMENDED_WEB_SEARCH = False  
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE = "medium"  
RECOMMENDED_WEB_SEARCH_USER_LOCATION = True  
RECOMMENDED_API_TIMEOUT = 30  
  
# Models with specific capabilities or restrictions  
UNSUPPORTED_MODELS = frozenset(  
    {  
        "gpt-4o-realtime-preview",  
        "gpt-4o-realtime-preview-2024-10-01",  
    }  
)  
WEB_SEARCH_MODELS = frozenset(  
    {  
        "gpt-4o",  
        "gpt-4o-2024-05-13",  
        "gpt-4o-2024-08-06",  
        "gpt-4o-mini",  
        "gpt-4o-mini-2024-07-18",  
    }  
)  