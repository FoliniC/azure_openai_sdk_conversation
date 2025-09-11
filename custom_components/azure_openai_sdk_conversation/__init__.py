"""Azure OpenAI SDK Conversation – integration bootstrap."""  
  
from __future__ import annotations  
  
import base64  
import logging  
from mimetypes import guess_type  
from pathlib import Path  
from typing import Any  
  
import openai  
from openai.types.images_response import ImagesResponse  
from openai.types.responses import (  
    EasyInputMessageParam,  
    Response,  
    ResponseInputFileParam,  
    ResponseInputImageParam,  
    ResponseInputMessageContentListParam,  
    ResponseInputParam,  
    ResponseInputTextParam,  
)  
import voluptuous as vol  
  
from homeassistant.config_entries import ConfigEntry  
from homeassistant.config_entries import ConfigEntryState  
from homeassistant.const import CONF_API_KEY, Platform  
from homeassistant.core import (  
    HomeAssistant,  
    ServiceCall,  
    ServiceResponse,  
    SupportsResponse,  
)  
from homeassistant.exceptions import (  
    ConfigEntryNotReady,  
    HomeAssistantError,  
    ServiceValidationError,  
)  
from homeassistant.helpers import config_validation as cv, selector  
from homeassistant.helpers.httpx_client import get_async_client  
from homeassistant.helpers.typing import ConfigType  
  
from .const import (  
    CONF_API_BASE,  
    CONF_CHAT_MODEL,  
    CONF_FILENAMES,  
    CONF_MAX_TOKENS,  
    CONF_PROMPT,  
    CONF_REASONING_EFFORT,  
    CONF_TEMPERATURE,  
    CONF_TOP_P,  
    DOMAIN,  
    LOGGER,  
    RECOMMENDED_CHAT_MODEL,  
    RECOMMENDED_MAX_TOKENS,  
    RECOMMENDED_REASONING_EFFORT,  
    RECOMMENDED_TEMPERATURE,  
    RECOMMENDED_TOP_P,  
)  
  
__all__ = ["normalize_azure_endpoint"]  
  
SERVICE_GENERATE_IMAGE = "generate_image"  
SERVICE_GENERATE_CONTENT = "generate_content"  
  
PLATFORMS: tuple[Platform, ...] = (Platform.CONVERSATION,)  
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  
  
# ----------------------------------------------------------------------  
#  Quale parametro usa la libreria OpenAI?  
# ----------------------------------------------------------------------  
def _token_param() -> str:  
    return (  
        "max_tokens"  
        if "max_tokens" in getattr(openai, "__all__", [])  # type: ignore[attr-defined]  
        else "max_completion_tokens"  
    )  
  
def encode_file(file_path: str) -> tuple[str, str]:  
    """Return (mime_type, base64-encoded contents) for a file path."""  
    mime_type, _ = guess_type(file_path)  
    if mime_type is None:  
        mime_type = "application/octet-stream"  
    with open(file_path, "rb") as fp:  
        return mime_type, base64.b64encode(fp.read()).decode("utf-8")  
  
# ----------------------------------------------------------------------  
#  SERVICEs  
# ----------------------------------------------------------------------  
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  
    """Register services – executed even if no config entries exist."""  
  
    # ---------- SERVICE generate_image ---------------------------------  
    async def render_image(call: ServiceCall) -> ServiceResponse:  
        entry_id: str = call.data["config_entry"]  
        entry = hass.config_entries.async_get_entry(entry_id)  
        if (  
            entry is None  
            or entry.domain != DOMAIN  
            or entry.state != ConfigEntryState.LOADED  
        ):  
            raise ServiceValidationError(  
                translation_domain=DOMAIN,  
                translation_key="invalid_config_entry",  
                translation_placeholders={"config_entry": entry_id},  
            )  
  
        client: openai.AsyncOpenAI = entry.runtime_data  # type: ignore[attr-defined]  
        try:  
            response: ImagesResponse = await client.images.generate(  
                model="dall-e-3",  
                prompt=call.data[CONF_PROMPT],  
                size=call.data["size"],  
                quality=call.data["quality"],  
                style=call.data["style"],  
                response_format="url",  
                n=1,  
            )  
        except openai.OpenAIError as err:  
            raise HomeAssistantError(f"Error generating image: {err}") from err  
  
        if not response.data or not response.data[0].url:  
            raise HomeAssistantError("No image returned")  
  
        return response.data[0].model_dump(exclude={"b64_json"})  
  
    # ---------- SERVICE generate_content -------------------------------  
    async def send_prompt(call: ServiceCall) -> ServiceResponse:  
        entry_id: str = call.data["config_entry"]  
        entry = hass.config_entries.async_get_entry(entry_id)  
        if (  
            entry is None  
            or entry.domain != DOMAIN  
            or entry.state != ConfigEntryState.LOADED  
        ):  
            raise ServiceValidationError(  
                translation_domain=DOMAIN,  
                translation_key="invalid_config_entry",  
                translation_placeholders={"config_entry": entry_id},  
            )  
  
        model: str = entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)  
        client: openai.AsyncOpenAI = entry.runtime_data  # type: ignore[attr-defined]  
  
        # ---- build message content ------------------------------------  
        content: ResponseInputMessageContentListParam = [  
            ResponseInputTextParam(type="input_text", text=call.data[CONF_PROMPT])  
        ]  
  
        if CONF_FILENAMES in call.data:  
  
            is_allowed = getattr(  
                hass.config,  
                "is_allowed_external_path",  
                hass.config.is_allowed_path,  
            )  
  
            def append_files() -> None:  
                for filename in call.data[CONF_FILENAMES]:  
                    if not is_allowed(filename):  
                        raise HomeAssistantError(  
                            f"Cannot read `{filename}` – not in allowlist."  
                        )  
                    if not Path(filename).exists():  
                        raise HomeAssistantError(f"`{filename}` does not exist")  
  
                    mime_type, b64_file = encode_file(filename)  
                    if mime_type.startswith("image/"):  
                        content.append(  
                            ResponseInputImageParam(  
                                type="input_image",  
                                image_url=f"data:{mime_type};base64,{b64_file}",  
                                detail="auto",  
                            )  
                        )  
                    elif mime_type == "application/pdf":  
                        content.append(  
                            ResponseInputFileParam(  
                                type="input_file",  
                                filename=Path(filename).name,  
                                file_data=f"data:{mime_type};base64,{b64_file}",  
                            )  
                        )  
                    else:  
                        raise HomeAssistantError(  
                            f"Unsupported file type '{mime_type}' for {filename}"  
                        )  
  
            await hass.async_add_executor_job(append_files)  
  
        messages: ResponseInputParam = [  
            EasyInputMessageParam(type="message", role="user", content=content)  
        ]  
  
        try:  
            model_args: dict[str, Any] = {  
                "model": model,  
                "input": messages,  
                _token_param(): entry.options.get(  
                    CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS  
                ),  
                "top_p": entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),  
                "temperature": entry.options.get(  
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE  
                ),  
                "user": call.context.user_id,  
                "store": False,  
            }  
            if model.startswith("o"):  
                model_args["reasoning"] = {  
                    "effort": entry.options.get(  
                        CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT  
                    )  
                }  
  
            response: Response = await client.responses.create(**model_args)  
        except (openai.OpenAIError, FileNotFoundError) as err:  
            raise HomeAssistantError(f"Error generating content: {err}") from err  
  
        return {"text": response.output_text}  
  
    # ---------- register ------------------------------------------------  
    hass.services.async_register(  
        DOMAIN,  
        SERVICE_GENERATE_CONTENT,  
        send_prompt,  
        schema=vol.Schema(  
            {  
                vol.Required("config_entry"): selector.ConfigEntrySelector(  
                    {"integration": DOMAIN}  
                ),  
                vol.Required(CONF_PROMPT): cv.string,  
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(  
                    cv.ensure_list, [cv.string]  
                ),  
            }  
        ),  
        supports_response=SupportsResponse.ONLY,  
    )  
  
    hass.services.async_register(  
        DOMAIN,  
        SERVICE_GENERATE_IMAGE,  
        render_image,  
        schema=vol.Schema(  
            {  
                vol.Required("config_entry"): selector.ConfigEntrySelector(  
                    {"integration": DOMAIN}  
                ),  
                vol.Required(CONF_PROMPT): cv.string,  
                vol.Optional("size", default="1024x1024"): vol.In(  
                    ("1024x1024", "1024x1792", "1792x1024")  
                ),  
                vol.Optional("quality", default="standard"): vol.In(("standard", "hd")),  
                vol.Optional("style", default="vivid"): vol.In(("vivid", "natural")),  
            }  
        ),  
        supports_response=SupportsResponse.ONLY,  
    )  
  
    return True  
  
# ----------------------------------------------------------------------  
#  CONFIG-ENTRY life-cycle  
# ----------------------------------------------------------------------  
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  
    """Create AsyncOpenAI client and load platform."""  
    api_base: str = entry.options.get(CONF_API_BASE) or entry.data[CONF_API_BASE]  
  
    client = openai.AsyncOpenAI(  
        base_url=f"{api_base.rstrip('/')}/openai",  
        default_query={"api-version": "2025-01-01-preview"},  
        api_key=entry.data[CONF_API_KEY],  
        http_client=get_async_client(hass),  
    )  
    entry.runtime_data = client  # type: ignore[attr-defined]  
  
    try:  
        await client.with_options(timeout=10).models.list()  
    except openai.AuthenticationError as err:  
        LOGGER.error("Invalid Azure OpenAI credentials: %s", err)  
        raise ConfigEntryNotReady from err  
    except openai.OpenAIError:  
        pass  
  
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)  
    # Ricarica automatica quando cambiano le opzioni  
    entry.async_on_unload(  
        entry.add_update_listener(_async_entry_updated)  
    )  
  
    return True  
  
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  
    """Unload entry and close HTTP client."""  
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)  
    if unloaded:  
        client: openai.AsyncOpenAI = entry.runtime_data  # type: ignore[attr-defined]  
        if hasattr(client, "aclose"):  
            await client.aclose()  # type: ignore[attr-defined]  
        else:  # openai ≥ 2.x  
            await hass.async_add_executor_job(client.close)  
        entry.runtime_data = None  # type: ignore[attr-defined]  
    return unloaded  
  
# ----------------------------------------------------------------------  
#  Helper – normalizza endpoint Azure  
# ----------------------------------------------------------------------  
def normalize_azure_endpoint(uri: str) -> str:  
    """Ensure URL ends with `/openai` (Azure style)."""  
    uri = uri.rstrip("/")  
    return f"{uri}/openai" if not uri.endswith("/openai") else uri  
  
# ----------------------------------------  
#  Opzioni cambiate? ricarica il config-entry  
# ----------------------------------------  
async def _async_entry_updated(  
    hass: HomeAssistant,  
    entry: ConfigEntry,  
) -> None:  
    await hass.config_entries.async_reload(entry.entry_id)  