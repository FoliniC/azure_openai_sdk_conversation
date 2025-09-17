"""Conversation provider for Azure OpenAI with optional web-search context."""  
from __future__ import annotations  
  
from typing import Any  
import json  
import logging  
import re  
  
from homeassistant.helpers import llm  
from homeassistant.components import conversation  
from homeassistant.components.conversation import AbstractConversationAgent, ConversationInput  
from homeassistant.config_entries import ConfigEntry  
from homeassistant.const import CONF_API_KEY  
from homeassistant.core import HomeAssistant  
from homeassistant.helpers.httpx_client import get_async_client  
from homeassistant.helpers.typing import HomeAssistantType  
from homeassistant.helpers.entity_platform import AddEntitiesCallback  
from homeassistant.helpers import intent as intent_helper  
from homeassistant.helpers.template import Template as HATemplate  
from homeassistant.helpers import (  
    area_registry as ar,  
    entity_registry as er,  
    device_registry as dr,  
)  
  
from .search import WebSearchClient  
from .const import (  
    CONF_WEB_SEARCH,  
    CONF_WEB_SEARCH_CONTEXT_SIZE,  
    CONF_WEB_SEARCH_USER_LOCATION,  
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,  
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
)  
  
DOMAIN = "azure_openai_sdk_conversation"  
  
# Opzioni legacy/extra per retrocompatibilità  
CONF_ENABLE_SEARCH = "enable_web_search"  
CONF_BING_KEY = "bing_api_key"  
CONF_BING_ENDPOINT = "bing_endpoint"  
CONF_BING_MAX = "bing_max_results"  
  
# opzioni extra  
CONF_CONV_API_VERSION = "conversation_api_version"  
CONF_FORCE_MODE = "force_responses_mode"  
  
# altre chiavi opzioni configurabili  
CONF_ENDPOINT = "endpoint"  
CONF_DEPLOYMENT = "deployment"  
  
# Debug SSE  
CONF_DEBUG_SSE = "debug_sse"  
CONF_DEBUG_SSE_LINES = "debug_sse_lines"  
  
# Sentinel opzione "usa stessa api_version globale"  
_SENTINEL_SAME = "__same__"  
  
_LOGGER = logging.getLogger(__name__)  
  
  
class AzureOpenAIConversationAgent(AbstractConversationAgent):  
    """Conversation agent che usa Azure OpenAI; può includere risultati web."""  
  
    def __init__(self, hass: HomeAssistantType, conf: dict[str, Any]) -> None:  
        super().__init__()  
        self._hass = hass  
        self._conf = conf  
        self._http = get_async_client(hass)  
  
        # Endpoint e parametri Azure  
        self._endpoint: str = (conf.get(CONF_ENDPOINT) or conf.get("api_base", "")).rstrip("/")  
        self._deployment: str = conf.get(CONF_DEPLOYMENT) or conf.get("chat_model", "")  
        self._api_version: str = self._normalize_api_version(conf)  
        self._timeout: int = self._coerce_int(conf.get("api_timeout"), 30)  
        self._force_mode: str = conf.get(CONF_FORCE_MODE, "auto")  # auto|responses|chat  
  
        self._headers_json = {  
            "api-key": conf[CONF_API_KEY],  
            "Content-Type": "application/json",  
        }  
        self._headers_sse = {  
            "api-key": conf[CONF_API_KEY],  
            "Content-Type": "application/json",  
            "Accept": "text/event-stream",  
            "Connection": "keep-alive",  
            "Cache-Control": "no-cache",  
        }  
  
        # Impostazioni logging  
        self._log_level: str = str(conf.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)).strip().lower()  
        self._log_payload_request: bool = bool(conf.get(CONF_LOG_PAYLOAD_REQUEST, False))  
        self._log_payload_response: bool = bool(conf.get(CONF_LOG_PAYLOAD_RESPONSE, False))  
        self._log_system_message: bool = bool(conf.get(CONF_LOG_SYSTEM_MESSAGE, False))  
        self._log_max_payload_chars: int = self._coerce_int(conf.get(CONF_LOG_MAX_PAYLOAD_CHARS), DEFAULT_LOG_MAX_PAYLOAD_CHARS)  
        self._log_max_sse_lines: int = self._coerce_int(conf.get(CONF_LOG_MAX_SSE_LINES), DEFAULT_LOG_MAX_SSE_LINES)  
  
        # Debug SSE  
        self._debug_sse: bool = self._coerce_bool(conf.get(CONF_DEBUG_SSE), False)  
        self._debug_sse_lines: int = self._coerce_int(conf.get(CONF_DEBUG_SSE_LINES), 10)  
  
        # Web Search opzionale: supporto sia a chiave legacy (enable_web_search) sia a nuova (web_search)  
        enable_search = self._coerce_bool(conf.get(CONF_ENABLE_SEARCH) or conf.get(CONF_WEB_SEARCH), False)  
        self._search: WebSearchClient | None = None  
        if enable_search:  
            self._search = WebSearchClient(  
                api_key=str(conf.get(CONF_BING_KEY, "")),  
                endpoint=conf.get(CONF_BING_ENDPOINT, WebSearchClient.BING_ENDPOINT_DEFAULT),  
                max_results=self._coerce_int(conf.get(CONF_BING_MAX), 5),  
            )  
  
    # -------------------- helpers: logging wrappers --------------------  
    @property  
    def _lvl(self) -> int:  
        if self._log_level == LOG_LEVEL_TRACE:  
            return 3  
        if self._log_level == LOG_LEVEL_INFO:  
            return 2  
        if self._log_level == LOG_LEVEL_ERROR:  
            return 1  
        return 0  # none  
  
    def _log_debug(self, msg: str, *args: Any) -> None:  
        if self._lvl >= 3:  
            _LOGGER.debug(msg, *args)  
  
    def _log_info(self, msg: str, *args: Any) -> None:  
        if self._lvl >= 2:  
            _LOGGER.info(msg, *args)  
  
    def _log_warn(self, msg: str, *args: Any) -> None:  
        if self._lvl >= 1:  
            _LOGGER.warning(msg, *args)  
  
    def _log_error(self, msg: str, *args: Any) -> None:  
        if self._lvl >= 1:  
            _LOGGER.error(msg, *args)  
  
    def _should_log_payload_request(self) -> bool:  
        return self._lvl >= 2 and self._log_payload_request  
  
    def _should_log_payload_response(self) -> bool:  
        return self._lvl >= 2 and self._log_payload_response  
  
    def _should_log_system_message(self) -> bool:  
        return self._lvl >= 2 and self._log_system_message  
  
    @staticmethod  
    def _safe_json(obj: Any, max_len: int = 12000) -> str:  
        try:  
            s = json.dumps(obj, ensure_ascii=False)  
        except Exception:  
            try:  
                s = str(obj)  
            except Exception:  
                s = "<unserializable>"  
        if len(s) > max_len:  
            return f"{s[:max_len]}... (truncated)"  
        return s  
  
    # -------------------- helpers: coercion --------------------  
    @staticmethod  
    def _coerce_int(value: Any, default: int) -> int:  
        try:  
            if isinstance(value, bool):  
                return int(value)  
            if isinstance(value, (int, float)):  
                return int(value)  
            if isinstance(value, str):  
                v = value.strip()  
                if not v:  
                    return default  
                return int(float(v))  
        except Exception:  
            return default  
        return default  
  
    @staticmethod  
    def _coerce_float(value: Any, default: float) -> float:  
        try:  
            if isinstance(value, bool):  
                return float(int(value))  
            if isinstance(value, (int, float)):  
                return float(value)  
            if isinstance(value, str):  
                v = value.strip()  
                if not v:  
                    return default  
                return float(v)  
        except Exception:  
            return default  
        return default  
  
    @staticmethod  
    def _coerce_bool(value: Any, default: bool) -> bool:  
        if isinstance(value, bool):  
            return value  
        if isinstance(value, (int, float)):  
            return value != 0  
        if isinstance(value, str):  
            v = value.strip().lower()  
            if v in ("1", "true", "on", "yes", "y", "si", "s"):  
                return True  
            if v in ("0", "false", "off", "no", "n"):  
                return False  
        return default  
  
    # -------------------- version helpers --------------------  
    @staticmethod  
    def _normalize_api_version(conf: dict[str, Any]) -> str:  
        """Ritorna la api-version effettiva da usare, normalizzando il sentinel."""  
        conv_ver = conf.get(CONF_CONV_API_VERSION)  
        if not conv_ver or str(conv_ver).strip() in (_SENTINEL_SAME, ""):  
            base = conf.get("api_version")  
            return base or "2025-03-01-preview"  
        return str(conv_ver).strip()  
  
    @staticmethod  
    def _ver_date_tuple(ver: str) -> tuple[int, int, int]:  
        core = (ver or "").split("-preview")[0]  
        parts = core.split("-")  
        try:  
            return (int(parts[0]), int(parts[1]), int(parts[2]))  
        except Exception:  # noqa: BLE001  
            return (1900, 1, 1)  
  
    def _ensure_min_version(self, ver: str, minimum: str) -> str:  
        """Ritorna 'ver' se >= minimum altrimenti 'minimum'."""  
        v = self._ver_date_tuple(ver)  
        m = self._ver_date_tuple(minimum)  
        return ver if v >= m else minimum  
  
    # -------------------- token param helpers --------------------  
    def _chat_token_param_initial(self) -> str:  
        """Determina il parametro token iniziale per Chat, evitando un primo tentativo errato."""  
        # 1) Preferisci quanto validato/salvato in config (se disponibile)  
        tp = str(self._conf.get("token_param") or "").strip()  
        if tp in ("max_tokens", "max_completion_tokens"):  
            return tp  
        # 2) Euristica per famiglie di modelli recenti che richiedono max_completion_tokens anche su 2025-01  
        model = (self._deployment or "").lower()  
        if model.startswith("gpt-5") or model.startswith("gpt-4.1") or model.startswith("gpt-4.2"):  
            return "max_completion_tokens"  
        # 3) Fallback alla regola per api-version  
        y, m, d = self._ver_date_tuple(self._api_version)  
        return "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"  
  
    # -------------------- entity collection --------------------  
    def _collect_exposed_entities(self) -> list[dict[str, Any]]:  
        """Costruisce una lista di entità per il template: entity_id, name, state, area, aliases[]."""  
        area_reg = ar.async_get(self._hass)  
        ent_reg = er.async_get(self._hass)  
        dev_reg = dr.async_get(self._hass)  
  
        out: list[dict[str, Any]] = []  
        for st in self._hass.states.async_all():  
            area_name = ""  
            entry = ent_reg.async_get(st.entity_id)  
            area_id = None  
            if entry:  
                area_id = entry.area_id  
                if not area_id and entry.device_id:  
                    dev = dev_reg.async_get(entry.device_id)  
                    if dev and dev.area_id:  
                        area_id = dev.area_id  
            if area_id:  
                area = area_reg.async_get_area(area_id)  
                if area and area.name:  
                    area_name = area.name  
            out.append(  
                {  
                    "entity_id": st.entity_id,  
                    "name": st.name or st.entity_id,  
                    "state": st.state,  
                    "area": area_name,  
                    "aliases": [],  # alias non disponibili qui  
                }  
            )  
        return out  
  
    @staticmethod  
    def _format_val(val: Any) -> str:  
        if isinstance(val, (str, int, float, bool)) or val is None:  
            return str(val)  
        try:  
            return json.dumps(val, ensure_ascii=False)  
        except Exception:  # noqa: BLE001  
            return str(val)  
  
    async def _render_system_message(self, raw_sys_msg: str, azure_ctx: dict[str, Any]) -> str:  
        """Renderizza il system_message; fallback: sostituzione regex per {{ azure.* }}."""  
        sys_msg = raw_sys_msg  
  
        # 1) Prova render Jinja con HATemplate (azure + exposed_entities)  
        try:  
            tmpl = HATemplate(raw_sys_msg, hass=self._hass)  
            sys_msg = tmpl.async_render(  
                {  
                    "azure": azure_ctx,  
                    "exposed_entities": self._collect_exposed_entities(),  
                }  
            )  
        except Exception as err:  # noqa: BLE001  
            self._log_debug("System message template render failed, will try regex fallback: %s", err)  
  
        # 2) Fallback: sostituisci tutti i {{ azure.xxx }} rimasti  
        pat = re.compile(r"{{\s*azure\.([a-zA-Z0-9_]+)\s*}}")  
        if pat.search(sys_msg):  
  
            def _sub(m: re.Match[str]) -> str:  
                key = m.group(1)  
                return self._format_val(azure_ctx.get(key, ""))  
  
            sys_msg = pat.sub(_sub, sys_msg)  
        return sys_msg  
  
    @property  
    def supported_languages(self) -> list[str]:  
        return ["en", "it"]  
  
    async def async_process(self, user_input: ConversationInput):  
        """Return the assistant response (non streaming per HA)."""  
        # Selezione endpoint: Responses per modelli "o*" o se forzato; Chat altrimenti  
        if self._force_mode == "responses":  
            use_responses = True  
        elif self._force_mode == "chat":  
            use_responses = False  
        else:  
            use_responses = bool(self._deployment and self._deployment.lower().startswith("o"))  
  
        # Prepara contesto 'azure' per il templating del system_message  
        def _responses_token_param_for_version(ver: str) -> str:  
            y, m, d = self._ver_date_tuple(ver)  
            return "max_output_tokens" if (y, m, d) >= (2025, 3, 1) else "max_completion_tokens"  
  
        def _chat_token_param_for_version(ver: str) -> str:  
            y, m, d = self._ver_date_tuple(ver)  
            return "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"  
  
        effective_version_for_mode = (  
            self._ensure_min_version(self._api_version, "2025-03-01-preview") if use_responses else self._api_version  
        )  
        token_param = (  
            _responses_token_param_for_version(effective_version_for_mode)  
            if use_responses  
            else self._chat_token_param_initial()  
        )  
  
        search_enabled = self._coerce_bool(self._conf.get(CONF_ENABLE_SEARCH) or self._conf.get(CONF_WEB_SEARCH, False), False)  
        default_ctx_size = RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE if search_enabled else 0  
        web_ctx_size = self._coerce_int(self._conf.get(CONF_WEB_SEARCH_CONTEXT_SIZE), default_ctx_size)  
        if web_ctx_size < 0:  
            web_ctx_size = 0  
        if search_enabled and web_ctx_size == 0:  
            # assicuriamo un minimo se la ricerca è abilitata  
            web_ctx_size = RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE  
  
        azure_ctx = {  
            "endpoint": self._endpoint,  
            "deployment": self._deployment,  
            "model": self._deployment,  
            "api_version": effective_version_for_mode,  
            "mode": "responses" if use_responses else "chat",  
            "token_param": token_param,  
            "max_tokens": self._coerce_int(self._conf.get("max_tokens"), 1024),  
            "temperature": self._coerce_float(self._conf.get("temperature"), 0.7),  
            "api_timeout": self._timeout,  
            "search_enabled": search_enabled,  
            "web_search_context_size": web_ctx_size,  
            "web_search_user_location": self._coerce_bool(self._conf.get(CONF_WEB_SEARCH_USER_LOCATION), False),  
            "debug_sse": self._debug_sse,  
        }  
  
        # System message personalizzabile + template (con fallback regex) e blocco identità se necessario  
        raw_sys_msg = self._conf.get("system_message") or "You are Home Assistant’s AI helper."  
        sys_msg = await self._render_system_message(raw_sys_msg, azure_ctx)  
  
        unresolved_azure = bool(re.search(r"{{\s*azure\.", sys_msg))  
        contains_azure = ("azure." in raw_sys_msg)  
        if unresolved_azure or not contains_azure:  
            identity_text = (  
                "Identità: assistente per Home Assistant.\n"  
                f"Endpoint: {azure_ctx['endpoint']}\n"  
                f"Deployment/Model: {azure_ctx['deployment']}\n"  
                f"API version: {azure_ctx['api_version']}\n"  
                f"Mode: {azure_ctx['mode']}\n"  
                f"Token param: {azure_ctx['token_param']}\n"  
                f"Max tokens: {azure_ctx['max_tokens']}\n"  
                f"Temperature: {azure_ctx['temperature']}\n"  
                f"Timeout: {azure_ctx['api_timeout']}s\n"  
                f"Web search: {azure_ctx['search_enabled']}"  
            )  
            sys_msg = f"{sys_msg}\n\n{identity_text}"  
  
        if self._should_log_system_message():  
            self._log_info("System prompt sent to model:\n%s", sys_msg)  
  
        messages_chat: list[dict[str, str]] = [{"role": "system", "content": sys_msg}]  
  
        # 1) Web-search (opzionale)  
        if self._search and search_enabled:  
            query = user_input.text  
            try:  
                search_md = await self._search.search(query)  
            except Exception as err:  # noqa: BLE001  
                self._log_warn("Web search failed: %s", err)  
                search_md = ""  
            if search_md:  
                messages_chat.append({"role": "system", "content": "Real-time web search results:\n\n" + search_md})  
  
        # 2) Messaggio utente  
        messages_chat.append({"role": "user", "content": user_input.text})  
  
        self._log_debug(  
            "Starting conversation using %s API (deployment=%s, api-version configured=%s)",  
            "Responses" if use_responses else "Chat",  
            self._deployment,  
            self._api_version,  
        )  
  
        text_out = ""  
        try:  
            if use_responses:  
                # Responses API: impone minimo "2025-03-01-preview"  
                next_version = self._ensure_min_version(self._api_version, "2025-03-01-preview")  
                url = f"{self._endpoint}/openai/responses"  
  
                # Converte i messaggi chat nello schema Responses: content(type=input_text)  
                def _to_input(msgs: list[dict[str, str]]) -> list[dict[str, Any]]:  
                    out_items: list[dict[str, Any]] = []  
                    for m in msgs:  
                        out_items.append(  
                            {  
                                "role": m["role"],  
                                "content": [{"type": "input_text", "text": m["content"]}],  
                            }  
                        )  
                    return out_items  
  
                attempted: set[str] = set()  
                res_token_param: str | None = None  
                use_messages_format = False  # prima tentativo con "input", poi (se serve) "messages+instructions"  
  
                while True:  
                    if res_token_param is None:  
                        # determina token param per versione corrente  
                        y, mn, d = self._ver_date_tuple(next_version)  
                        res_token_param = "max_output_tokens" if (y, mn, d) >= (2025, 3, 1) else "max_completion_tokens"  
  
                    fmt = "messages" if use_messages_format else "input"  
                    pair_key = f"{next_version}::{res_token_param}::fmt={fmt}"  
                    if pair_key in attempted:  
                        break  
                    attempted.add(pair_key)  
  
                    self._log_debug(  
                        "Calling Responses API api-version=%s with token param=%s (format=%s, stream)",  
                        next_version,  
                        res_token_param,  
                        fmt,  
                    )  
  
                    payload: dict[str, Any] = {  
                        "model": self._deployment,  
                        res_token_param: self._coerce_int(self._conf.get("max_tokens"), 1024),  
                        "temperature": self._coerce_float(self._conf.get("temperature"), 0.7),  
                        "stream": True,  
                        "modalities": ["text"],  
                        "text": {"format": "text"},  
                    }  
                    if use_messages_format:  
                        payload["messages"] = _to_input(messages_chat)  # mantiene i ruoli  
                        payload["instructions"] = sys_msg  
                    else:  
                        payload["input"] = _to_input(messages_chat)  
  
                    if self._should_log_payload_request():  
                        self._log_info("Request payload (Responses %s): %s", fmt, self._safe_json(payload, self._log_max_payload_chars))  
  
                    async with self._http.stream(  
                        "POST",  
                        url,  
                        params={"api-version": next_version},  
                        headers=self._headers_sse,  
                        json=payload,  
                        timeout=self._timeout,  
                    ) as resp:  
                        if resp.status_code >= 400:  
                            body = await resp.aread()  
                            text_body = body.decode("utf-8", "ignore")  
                            try:  
                                err_json = json.loads(text_body or "{}")  
                            except Exception:  
                                err_json = {}  
                            msg = err_json.get("error", {}).get("message") or text_body or f"HTTP {resp.status_code}"  
                            self._log_error("Azure responses stream error: %s", msg)  
  
                            # Retry: server impone 2025-03-01-preview  
                            if (  
                                "Responses API is enabled only for api-version 2025-03-01-preview" in msg  
                                and next_version != "2025-03-01-preview"  
                            ):  
                                self._log_debug("Retrying Responses with api-version=2025-03-01-preview")  
                                next_version = "2025-03-01-preview"  
                                res_token_param = None  
                                continue  
  
                            # Retry: cambio parametro token  
                            if "Unsupported parameter: 'max_completion_tokens'" in msg and res_token_param != "max_output_tokens":  
                                self._log_debug("Retrying Responses switching token param to max_output_tokens")  
                                res_token_param = "max_output_tokens"  
                                continue  
                            if "Unsupported parameter: 'max_output_tokens'" in msg and res_token_param != "max_completion_tokens":  
                                self._log_debug("Retrying Responses switching token param to max_completion_tokens")  
                                res_token_param = "max_completion_tokens"  
                                continue  
  
                            # Se errore e non abbiamo provato l'altro formato, prova "messages"  
                            if not use_messages_format:  
                                self._log_debug("Retrying Responses switching to messages+instructions format")  
                                use_messages_format = True  
                                continue  
  
                            # nessun'altra strategia disponibile  
                            break  
  
                        # Streaming OK: parser SSE con ricomposizione multiline  
                        last_event: str | None = None  
                        current_event: str | None = None  
                        data_lines: list[str] = []  
                        debug_samples: list[str] = []  
                        collect_sse_samples = self._debug_sse or self._should_log_payload_response()  
                        if collect_sse_samples:  
                            debug_limit = self._debug_sse_lines if self._debug_sse else self._log_max_sse_lines  
                        else:  
                            debug_limit = 0  
  
                        async for raw_line in resp.aiter_lines():  
                            if raw_line is None:  
                                continue  
                            line = raw_line.rstrip("\n\r")  
  
                            if not line:  
                                # fine messaggio SSE -> processa blocco  
                                if not data_lines:  
                                    continue  
                                data_str = "\n".join(data_lines).strip()  
                                data_lines = []  
                                if debug_limit > 0 and len(debug_samples) < debug_limit:  
                                    debug_samples.append(f"event={current_event or last_event} data={data_str[:500]}")  
                                if not data_str or data_str == "[DONE]":  
                                    break  
                                try:  
                                    payload_obj = json.loads(data_str)  
                                except Exception:  
                                    current_event = None  
                                    continue  
  
                                event_name = (  
                                    payload_obj.get("type")  
                                    or payload_obj.get("event")  
                                    or current_event  
                                    or last_event  
                                )  
  
                                def _consume(node: Any) -> None:  
                                    nonlocal text_out  
                                    if node is None:  
                                        return  
                                    if isinstance(node, str):  
                                        text_out += node  
                                        return  
                                    if isinstance(node, list):  
                                        for it in node:  
                                            _consume(it)  
                                        return  
                                    if isinstance(node, dict):  
                                        txt = node.get("text")  
                                        if isinstance(txt, str):  
                                            text_out += txt  
                                        _consume(node.get("content"))  
                                        _consume(node.get("delta"))  
                                        _consume(node.get("data"))  
                                        _consume(node.get("output"))  
                                        _consume(node.get("message"))  
  
                                # Alcuni eventi portano direttamente delta  
                                if event_name in (  
                                    "response.output_text.delta",  
                                    "output_text.delta",  
                                    "response.delta",  
                                    "delta",  
                                    "response.message.delta",  
                                    "message.delta",  
                                    "response.refusal.delta",  
                                    "refusal.delta",  
                                    "response.output_text",  
                                ):  
                                    _consume(payload_obj.get("delta") or payload_obj)  
                                elif event_name in ("response.error",):  
                                    self._log_error("Azure responses error event: %s", payload_obj)  
                                    break  
                                elif event_name in (  
                                    "response.completed",  
                                    "message.completed",  
                                    "response.finish",  
                                    "response.output_text.done",  
                                ):  
                                    # Fine  
                                    pass  
  
                                last_event = event_name or last_event  
                                current_event = None  
                                continue  
  
                            if line.startswith(":"):  # commento SSE  
                                continue  
                            if line.startswith("event:"):  
                                current_event = line[6:].strip()  
                                continue  
                            if line.startswith("data:"):  
                                data_lines.append(line[5:].lstrip())  
                                continue  
  
                        # Flush finale se rimane un blocco  
                        if data_lines:  
                            data_str = "\n".join(data_lines).strip()  
                            if debug_limit > 0 and len(debug_samples) < debug_limit:  
                                debug_samples.append(f"event={current_event or last_event} data={data_str[:500]}")  
                            try:  
                                payload_obj = json.loads(data_str)  
                            except Exception:  
                                payload_obj = None  
  
                            if isinstance(payload_obj, dict):  
                                def _consume_tail(node: Any) -> None:  
                                    nonlocal text_out  
                                    if node is None:  
                                        return  
                                    if isinstance(node, str):  
                                        text_out += node  
                                        return  
                                    if isinstance(node, list):  
                                        for it in node:  
                                            _consume_tail(it)  
                                        return  
                                    if isinstance(node, dict):  
                                        txt = node.get("text")  
                                        if isinstance(txt, str):  
                                            text_out += txt  
                                        _consume_tail(node.get("output"))  
                                        _consume_tail(node.get("content"))  
                                        _consume_tail(node.get("message"))  
                                        _consume_tail(node.get("data"))  
                                        _consume_tail(node.get("delta"))  
                                _consume_tail(payload_obj)  
  
                        if debug_samples and collect_sse_samples:  
                            self._log_info(  
                                "Responses SSE sample (first %d messages):\n%s",  
                                len(debug_samples),  
                                "\n".join(debug_samples),  
                            )  
  
                        # Se non è uscito testo, prova formato alternativo prima, poi eventualmente fallback  
                        if not text_out and not use_messages_format:  
                            self._log_debug(  
                                "Responses stream produced no text, retrying with messages+instructions format"  
                            )  
                            use_messages_format = True  
                            continue  
  
                        # Fine ciclo Responses  
                        break  
  
                # Fallback automatico: se non è arrivato testo, tenta una chiamata NON-streaming Responses  
                if not text_out:  
                    self._log_debug(  
                        "Responses stream produced no text; trying non-stream Responses (format=%s)",  
                        "messages" if use_messages_format else "input",  
                    )  
                    text_out = await self._responses_non_stream(messages_chat, sys_msg, next_version, use_messages_format)  
  
                # Se ancora vuoto, e modalità 'auto' ma il modello NON è 'o*', si prova Chat  
                if not text_out and self._force_mode == "auto" and not (self._deployment or "").lower().startswith("o"):  
                    self._log_debug("Responses non-stream produced no text; falling back to Chat Completions")  
                    text_out = await self._chat_completions_fallback(messages_chat)  
            else:  
                # Forza Chat immediatamente  
                text_out = await self._chat_completions_fallback(messages_chat)  
        except Exception as err:  # noqa: BLE001  
            self._log_error("Azure conversation processing failed: %s", err)  
  
        # Logga testo risposta finale (se richiesto)  
        if self._should_log_payload_response() and text_out:  
            self._log_info("Response text: %s", text_out)  
  
        # IntentResponse per HA  
        response = intent_helper.IntentResponse(language=getattr(user_input, "language", None))  
        response.async_set_speech(text_out or "")  
  
        return conversation.ConversationResult(  
            response=response,  
            conversation_id=user_input.conversation_id,  
        )  
  
    async def _responses_non_stream(  
        self, messages_chat: list[dict[str, str]], sys_msg: str, api_version: str, use_messages_format: bool  
    ) -> str:  
        """Esegue una chiamata Responses non-stream e restituisce il testo aggregato."""  
        url = f"{self._endpoint}/openai/responses"  
  
        def _to_input(msgs: list[dict[str, str]]) -> list[dict[str, Any]]:  
            out: list[dict[str, Any]] = []  
            for m in msgs:  
                out.append(  
                    {  
                        "role": m["role"],  
                        "content": [{"type": "input_text", "text": m["content"]}],  
                    }  
                )  
            return out  
  
        def _responses_token_param_for_version(ver: str) -> str:  
            y, m, d = self._ver_date_tuple(ver)  
            return "max_output_tokens" if (y, m, d) >= (2025, 3, 1) else "max_completion_tokens"  
  
        token_param = _responses_token_param_for_version(api_version)  
  
        payload: dict[str, Any] = {  
            "model": self._deployment,  
            token_param: self._coerce_int(self._conf.get("max_tokens"), 1024),  
            "temperature": self._coerce_float(self._conf.get("temperature"), 0.7),  
            # esplicita modalità testo  
            "modalities": ["text"],  
            "text": {"format": "text"},  
        }  
        if use_messages_format:  
            payload["messages"] = _to_input(messages_chat)  
            payload["instructions"] = sys_msg  
        else:  
            payload["input"] = _to_input(messages_chat)  
  
        if self._should_log_payload_request():  
            self._log_info(  
                "Request payload (Responses non-stream %s): %s",  
                "messages" if use_messages_format else "input",  
                self._safe_json(payload, self._log_max_payload_chars),  
            )  
  
        try:  
            resp = await self._http.post(  
                url,  
                params={"api-version": api_version},  
                headers=self._headers_json,  
                json=payload,  
                timeout=self._timeout,  
            )  
        except Exception as err:  # noqa: BLE001  
            self._log_error("Azure responses (non-stream) request failed: %s", err)  
            return ""  
  
        if resp.status_code >= 400:  
            text_body = await resp.aread()  
            try:  
                err_json = json.loads(text_body.decode("utf-8", "ignore") or "{}")  
            except Exception:  
                err_json = {}  
            msg = err_json.get("error", {}).get("message") or text_body.decode("utf-8", "ignore") or f"HTTP {resp.status_code}"  
            self._log_error("Azure responses (non-stream) error: %s", msg)  
            return ""  
  
        # Estrazione generica di tutto il testo  
        try:  
            obj = resp.json()  
        except Exception:  
            try:  
                obj = json.loads((await resp.aread()).decode("utf-8", "ignore"))  
            except Exception:  
                obj = None  
  
        if self._should_log_payload_response() and obj is not None:  
            self._log_info("Response payload (Responses non-stream): %s", self._safe_json(obj, self._log_max_payload_chars))  
  
        if not isinstance(obj, dict):  
            return ""  
        out_parts: list[str] = []  
  
        def _acc(node: Any) -> None:  
            if node is None:  
                return  
            if isinstance(node, str):  
                out_parts.append(node)  
                return  
            if isinstance(node, list):  
                for it in node:  
                    _acc(it)  
                return  
            if isinstance(node, dict):  
                txt = node.get("text")  
                if isinstance(txt, str):  
                    out_parts.append(txt)  
                _acc(node.get("output"))  
                _acc(node.get("content"))  
                _acc(node.get("message"))  
                _acc(node.get("data"))  
                _acc(node.get("choices"))  
  
        _acc(obj)  
        text = "".join(out_parts).strip()  
        self._log_debug("Responses non-stream extracted %d chars", len(text))  
        return text  
  
    async def _chat_completions_fallback(self, messages_chat: list[dict[str, str]]) -> str:  
        """Esegue Chat Completions (stream) con gestione del parametro token dinamico."""  
        def _chat_token_param_for_version(ver: str) -> str:  
            y, m, d = self._ver_date_tuple(ver)  
            return "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"  
  
        text_out = ""  
        url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"  
        next_version = self._api_version  
        token_param = self._chat_token_param_initial()  
        attempted: set[str] = set()  
  
        while True:  
            pair_key = f"{next_version}::{token_param}"  
            if pair_key in attempted:  
                break  
            attempted.add(pair_key)  
  
            payload: dict[str, Any] = {  
                "messages": messages_chat,  
                "temperature": self._coerce_float(self._conf.get("temperature"), 0.7),  
                "stream": True,  
                token_param: self._coerce_int(self._conf.get("max_tokens"), 1024),  
            }  
  
            self._log_debug(  
                "Calling Chat Completions api-version=%s with token param=%s",  
                next_version,  
                token_param,  
            )  
  
            if self._should_log_payload_request():  
                self._log_info("Request payload (Chat Completions): %s", self._safe_json(payload, self._log_max_payload_chars))  
  
            async with self._http.stream(  
                "POST",  
                url,  
                params={"api-version": next_version},  
                headers=self._headers_sse,  
                json=payload,  
                timeout=self._timeout,  
            ) as resp:  
                if resp.status_code >= 400:  
                    body = await resp.aread()  
                    txt = body.decode("utf-8", "ignore")  
                    try:  
                        err_json = json.loads(txt or "{}")  
                    except Exception:  
                        err_json = {}  
                    msg = err_json.get("error", {}).get("message") or txt or f"HTTP {resp.status_code}"  
                    self._log_error("Azure chat stream error: %s", msg)  
  
                    # Retry cambio parametro  
                    if "Unsupported parameter: 'max_tokens'" in msg and token_param != "max_completion_tokens":  
                        self._log_debug("Retrying Chat switching token param to max_completion_tokens")  
                        token_param = "max_completion_tokens"  
                        continue  
                    if "Unsupported parameter: 'max_completion_tokens'" in msg and token_param != "max_tokens":  
                        self._log_debug("Retrying Chat switching token param to max_tokens")  
                        token_param = "max_tokens"  
                        continue  
  
                    # Retry API version richiesta (caso raro per chat)  
                    if ("api-version 2025-03-01-preview" in msg) and next_version != "2025-03-01-preview":  
                        self._log_debug("Retrying Chat with api-version=2025-03-01-preview")  
                        next_version = "2025-03-01-preview"  
                        token_param = _chat_token_param_for_version(next_version)  
                        continue  
  
                    break  
  
                # Stream OK  
                sse_samples: list[str] = []  
                collect_samples = self._should_log_payload_response() or self._debug_sse  
                if collect_samples:  
                    debug_limit = self._debug_sse_lines if self._debug_sse else self._log_max_sse_lines  
                else:  
                    debug_limit = 0  
  
                async for raw_line in resp.aiter_lines():  
                    if not raw_line:  
                        continue  
                    line = raw_line.strip()  
                    if not line or line.startswith(":"):  
                        continue  
                    if not line.startswith("data:"):  
                        continue  
  
                    data_str = line[5:].lstrip()  
                    if collect_samples and debug_limit > 0 and len(sse_samples) < debug_limit and data_str and data_str != "[DONE]":  
                        sse_samples.append(data_str[:500])  
  
                    if not data_str or data_str == "[DONE]":  
                        break  
                    try:  
                        chunk = json.loads(data_str)  
                    except Exception:  
                        continue  
  
                    try:  
                        choices = chunk.get("choices") or []  
                        if not choices:  
                            continue  
                        delta = choices[0].get("delta") or {}  
                        content = delta.get("content")  
                        if content:  
                            text_out += str(content)  
                    except Exception:  
                        continue  
  
                if sse_samples and collect_samples:  
                    self._log_info("Chat Completions SSE sample (first %d lines):\n%s", len(sse_samples), "\n".join(sse_samples))  
            break  
  
        return text_out  
  
    async def async_close(self) -> None:  
        """Clean up network clients."""  
        if self._search:  
            await self._search.close()  
  
  
async def async_setup_entry(  
    hass: HomeAssistant,  
    config_entry: ConfigEntry,  
    async_add_entities: AddEntitiesCallback,  
) -> None:  
    """Set up the conversation platform for the Azure OpenAI integration."""  
    # Mixa data e options per fornire all'agente tutte le opzioni modificabili  
    conf: dict[str, Any] = {  
        CONF_API_KEY: config_entry.data[CONF_API_KEY],  
        # fallback legacy per chiavi principali  
        "api_base": config_entry.data.get("api_base", ""),  
        "chat_model": config_entry.data.get("chat_model", ""),  
        "api_version": config_entry.data.get("api_version"),  
        **config_entry.options,  
    }  
  
    # Normalizza il system prompt  
    sys_prompt = (  
        conf.get("system_message")  
        or conf.get("system_prompt")  
        or conf.get("prompt")  
        or llm.DEFAULT_INSTRUCTIONS_PROMPT  
    )  
    conf["system_message"] = sys_prompt  
  
    agent = AzureOpenAIConversationAgent(hass, conf=conf)  
  
    # Compat con diverse versioni dell’API conversation  
    try:  
        conversation.async_set_agent(hass, config_entry, agent)  
    except TypeError:  
        try:  
            conversation.async_set_agent(hass, agent)  # firma più vecchia  
        except TypeError:  
            conversation.async_register_agent(  
                hass,  
                agent_id=f"{DOMAIN}.{config_entry.entry_id}",  
                agent=agent,  
            )  