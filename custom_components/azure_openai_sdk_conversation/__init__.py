"""Init for Azure OpenAI SDK Conversation integration."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, CONF_API_KEY
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.httpx_client import get_async_client

from .utils import APIVersionManager
from .const import (
    DOMAIN,
    CONF_STATS_ENABLE,
    # logging constants used for informative log
    CONF_LOG_LEVEL,
    CONF_LOG_PAYLOAD_REQUEST,
    CONF_LOG_PAYLOAD_RESPONSE,
    CONF_LOG_SYSTEM_MESSAGE,
    CONF_LOG_MAX_PAYLOAD_CHARS,
    CONF_LOG_MAX_SSE_LINES,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_PAYLOAD_CHARS,
    DEFAULT_LOG_MAX_SSE_LINES,
)

PLATFORMS = [Platform.CONVERSATION]

_LOGGER = logging.getLogger(__name__)

# Schema for global configuration via configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_STATS_ENABLE): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store global config if present
    if DOMAIN in config:
        hass.data[DOMAIN]['global_config'] = config[DOMAIN]
        _LOGGER.info(
            "Azure OpenAI global config loaded: stats_enable=%s",
            config[DOMAIN].get(CONF_STATS_ENABLE)
        )
        
    return True


def normalize_azure_endpoint(value: str | None) -> str:
    """Normalize an Azure endpoint to 'scheme://host[:port]' without trailing slash or path."""
    s = (value or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = f"https://{s}"
    try:
        parsed = urlparse(s)
        scheme = (parsed.scheme or "https").lower()
        host = (parsed.hostname or "").lower()
        if not host:
            return s.rstrip("/")
        port = f":{parsed.port}" if parsed.port else ""
        return f"{scheme}://{host}{port}"
    except Exception:
        return s.rstrip("/")


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration and forward platforms.

    This version removes the runtime dependency on the `openai` Python SDK.
    It validates credentials via a lightweight HTTP GET to /openai/models.
    """
    data = entry.data
    api_base: str = (data.get("api_base") or "").rstrip("/")
    if not api_base:
        raise ConfigEntryNotReady("Missing api_base")

    model: str = data.get("chat_model") or ""

    # Deterministic recommended api-version (keeps your previous logic)
    api_version: str = (
        entry.options.get("api_version")
        or data.get("api_version")
        or APIVersionManager.best_for_model(model)
    )

    http = get_async_client(hass)
    url = f"{api_base}/openai/models"
    headers = {
        "api-key": data.get(CONF_API_KEY) or "",
        "Accept": "application/json",
    }

    try:
        resp = await http.get(
            url,
            params={"api-version": api_version},
            headers=headers,
            timeout=10,
        )
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Azure OpenAI at {api_base}: {err}"
        ) from err

    if resp.status_code in (401, 403):
        # Use simple redaction inline without importing from core.config
        api_key = data.get(CONF_API_KEY, "")
        redacted = f"{api_key[:3]}***{api_key[-3:]}" if len(api_key) > 8 else "***"
        raise ConfigEntryNotReady(
            f"Invalid Azure OpenAI credentials for {api_base} ({redacted})"
        )

    if resp.status_code >= 400:
        try:
            body = (await resp.aread()).decode("utf-8", "ignore")
        except Exception:
            body = f"HTTP {resp.status_code}"
        raise ConfigEntryNotReady(
            f"Azure OpenAI /models returned {resp.status_code}: {body}"
        )

    # No persistent SDK client required
    try:
        entry.runtime_data = None  # type: ignore[attr-defined]
    except Exception:
        pass

    # Informational log about current logging configuration
    opts = entry.options
    log_level = opts.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    log_req = bool(opts.get(CONF_LOG_PAYLOAD_REQUEST, False))
    log_res = bool(opts.get(CONF_LOG_PAYLOAD_RESPONSE, False))
    log_sys = bool(opts.get(CONF_LOG_SYSTEM_MESSAGE, False))
    max_chars = int(opts.get(CONF_LOG_MAX_PAYLOAD_CHARS, DEFAULT_LOG_MAX_PAYLOAD_CHARS))
    max_sse = int(opts.get(CONF_LOG_MAX_SSE_LINES, DEFAULT_LOG_MAX_SSE_LINES))
    debug_sse = bool(opts.get("debug_sse", False))
    debug_sse_lines = int(opts.get("debug_sse_lines", 10))

    _LOGGER.info(
        "Azure OpenAI conversation logging config: level=%s, request=%s, response=%s, system=%s, max_payload_chars=%s, max_sse_lines=%s, debug_sse=%s, debug_sse_lines=%s",
        log_level,
        log_req,
        log_res,
        log_sys,
        max_chars,
        max_sse,
        debug_sse,
        debug_sse_lines,
    )

    # Automatic reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug(
        "Azure OpenAI conversation set up (deployment=%s, api-version=%s)",
        model,
        api_version,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry and close resources (none persisted here)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        try:
            entry.runtime_data = None  # type: ignore[attr-defined]
        except Exception:
            pass
    return unloaded