"""Conversation provider for Azure OpenAI with optional web-search context."""  
from __future__ import annotations  
  
from typing import Any  
import json  
import logging  
import re  
  
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
  
DOMAIN = "azure_openai_sdk_conversation"  
  
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
    self._timeout: int = int(conf.get("api_timeout", 30))  
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
  
    # Debug SSE  
    self._debug_sse: bool = bool(conf.get(CONF_DEBUG_SSE, False))  
    self._debug_sse_lines: int = int(conf.get(CONF_DEBUG_SSE_LINES, 10))  
  
    # Web Search opzionale  
    self._search: WebSearchClient | None = None  
    if conf.get(CONF_ENABLE_SEARCH):  
      self._search = WebSearchClient(  
        api_key=conf.get(CONF_BING_KEY, ""),  
        endpoint=conf.get(CONF_BING_ENDPOINT, WebSearchClient.BING_ENDPOINT_DEFAULT),  
        max_results=int(conf.get(CONF_BING_MAX, 5)),  
      )  
  
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
      sys_msg = await tmpl.async_render(  
        {  
          "azure": azure_ctx,  
          "exposed_entities": self._collect_exposed_entities(),  
        }  
      )  
    except Exception as err:  # noqa: BLE001  
      _LOGGER.debug("System message template render failed, will try regex fallback: %s", err)  
  
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
      if use_responses else  
      _chat_token_param_for_version(effective_version_for_mode)  
    )  
  
    azure_ctx = {  
      "endpoint": self._endpoint,  
      "deployment": self._deployment,  
      "model": self._deployment,  
      "api_version": effective_version_for_mode,  
      "mode": "responses" if use_responses else "chat",  
      "token_param": token_param,  
      "max_tokens": int(self._conf.get("max_tokens", 1024)),  
      "temperature": float(self._conf.get("temperature", 0.7)),  
      "api_timeout": self._timeout,  
      "search_enabled": bool(self._conf.get(CONF_ENABLE_SEARCH, False)),  
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
  
    messages_chat: list[dict[str, str]] = [{"role": "system", "content": sys_msg}]  
  
    # 1) Web-search (opzionale)  
    if self._search:  
      query = user_input.text  
      try:  
        search_md = await self._search.search(query)  
      except Exception as err:  # noqa: BLE001  
        _LOGGER.warning("Web search failed: %s", err)  
        search_md = ""  
      if search_md:  
        messages_chat.append(  
          {"role": "system", "content": "Real-time web search results:\n\n" + search_md}  
        )  
  
    # 2) Messaggio utente  
    messages_chat.append({"role": "user", "content": user_input.text})  
  
    _LOGGER.debug(  
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
          out: list[dict[str, Any]] = []  
          for m in msgs:  
            out.append(  
              {  
                "role": m["role"],  
                "content": [{"type": "input_text", "text": m["content"]}],  
              }  
            )  
          return out  
  
        def _responses_token_param_for_version_local(ver: str) -> str:  
          y, m, d = self._ver_date_tuple(ver)  
          return "max_output_tokens" if (y, m, d) >= (2025, 3, 1) else "max_completion_tokens"  
  
        attempted: set[str] = set()  
        res_token_param: str | None = None  
        use_messages_format = False  # prima tentativo con "input", poi (se serve) "messages+instructions"  
  
        while True:  
          if res_token_param is None:  
            res_token_param = _responses_token_param_for_version_local(next_version)  
  
          fmt = "messages" if use_messages_format else "input"  
          pair_key = f"{next_version}::{res_token_param}::fmt={fmt}"  
          if pair_key in attempted:  
            break  
          attempted.add(pair_key)  
  
          _LOGGER.debug(  
            "Calling Responses API api-version=%s with token param=%s (format=%s, effective)",  
            next_version,  
            res_token_param,  
            fmt,  
          )  
  
          # Costruzione payload (Responses 2025-03-01-preview: usare 'text.format' non 'response_format')  
          payload: dict[str, Any] = {  
            "model": self._deployment,  
            res_token_param: int(self._conf.get("max_tokens", 1024)),  
            "temperature": float(self._conf.get("temperature", 0.7)),  
            "stream": True,  
            "modalities": ["text"],  
            "text": {"format": "text"},  
          }  
          if use_messages_format:  
            # alcune implementazioni preferiscono "messages" e "instructions"  
            payload["messages"] = _to_input(messages_chat)  # mantiene i ruoli  
            payload["instructions"] = sys_msg  
          else:  
            payload["input"] = _to_input(messages_chat)  
  
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
              _LOGGER.error("Azure responses stream error: %s", msg)  
  
              # Retry: server impone 2025-03-01-preview (già impostiamo minimo, ma gestiamo comunque)  
              if (  
                ("Responses API is enabled only for api-version 2025-03-01-preview" in msg)  
                and next_version != "2025-03-01-preview"  
              ):  
                _LOGGER.debug("Retrying Responses with api-version=2025-03-01-preview")  
                next_version = "2025-03-01-preview"  
                res_token_param = None  
                continue  
  
              # Retry: cambio parametro token  
              if "Unsupported parameter: 'max_completion_tokens'" in msg and res_token_param != "max_output_tokens":  
                _LOGGER.debug("Retrying Responses switching token param to max_output_tokens")  
                res_token_param = "max_output_tokens"  
                continue  
              if "Unsupported parameter: 'max_output_tokens'" in msg and res_token_param != "max_completion_tokens":  
                _LOGGER.debug("Retrying Responses switching token param to max_completion_tokens")  
                res_token_param = "max_completion_tokens"  
                continue  
  
              # Se errore e non abbiamo provato l'altro formato, prova "messages"  
              if not use_messages_format:  
                _LOGGER.debug("Retrying Responses switching to messages+instructions format")  
                use_messages_format = True  
                continue  
  
              break  
  
            # Streaming OK: parser SSE con ricomposizione multiline  
            last_event: str | None = None  
            current_event: str | None = None  
            data_lines: list[str] = []  
            debug_samples: list[str] = []  
            debug_limit = self._debug_sse_lines if self._debug_sse else 0  
  
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
  
                if event_name in ("response.output_text.delta", "output_text.delta"):  
                  # delta o text al root o in data  
                  if "delta" in payload_obj or "text" in payload_obj:  
                    _consume(payload_obj)  
                  else:  
                    _consume(payload_obj.get("data"))  
                elif event_name in (  
                  "response.delta", "delta",  
                  "response.message.delta", "message.delta",  
                  "response.refusal.delta", "refusal.delta",  
                  "response.output_text",  
                ):  
                  _consume(payload_obj.get("delta") or payload_obj)  
                elif event_name in ("response.error",):  
                  _LOGGER.error("Azure responses error event: %s", payload_obj)  
                  break  
                elif event_name in ("response.completed", "message.completed", "response.finish", "response.output_text.done"):  
                  break  
  
                last_event = event_name or last_event  
                current_event = None  
                continue  
  
              if line.startswith(":"):  
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
                    _consume_tail(node.get("content"))  
                    _consume_tail(node.get("delta"))  
                    _consume_tail(node.get("data"))  
                    _consume_tail(node.get("output"))  
                _consume_tail(payload_obj)  
  
            if debug_samples:  
              _LOGGER.debug("Responses SSE sample (first %d messages):\n%s", len(debug_samples), "\n".join(debug_samples))  
  
            # Se non è uscito testo, prova formato alternativo prima, poi eventualmente fallback  
            if not text_out and not use_messages_format:  
              _LOGGER.debug("Responses stream produced no text, retrying with messages+instructions format")  
              use_messages_format = True  
              continue  
  
            # Fine ciclo Responses  
            break  
  
        # Fallback automatico: se non è arrivato testo, tenta una chiamata NON-streaming Responses  
        if not text_out:  
          _LOGGER.debug("Responses stream produced no text; trying non-stream Responses (format=%s)", "messages" if use_messages_format else "input")  
          text_out = await self._responses_non_stream(messages_chat, sys_msg, next_version, use_messages_format)  
          # Se ancora vuoto, e modalità 'auto' ma il modello NON è 'o*', si prova Chat  
          if not text_out and self._force_mode == "auto" and not (self._deployment or "").lower().startswith("o"):  
            _LOGGER.debug("Responses non-stream produced no text; falling back to Chat Completions")  
            text_out = await self._chat_completions_fallback(messages_chat)  
  
      else:  
        # Forza Chat immediatamente  
        text_out = await self._chat_completions_fallback(messages_chat)  
  
    except Exception as err:  # noqa: BLE001  
      _LOGGER.error("Azure streaming failed: %s", err)  
  
    # IntentResponse per HA  
    response = intent_helper.IntentResponse(language=getattr(user_input, "language", None))  
    response.async_set_speech(text_out or "")  
  
    return conversation.ConversationResult(  
      response=response,  
      conversation_id=user_input.conversation_id,  
    )  
  
  async def _responses_non_stream(self, messages_chat: list[dict[str, str]], sys_msg: str, api_version: str, use_messages_format: bool) -> str:  
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
      token_param: int(self._conf.get("max_tokens", 1024)),  
      "temperature": float(self._conf.get("temperature", 0.7)),  
      # esplicita modalità testo  
      "modalities": ["text"],  
      "text": {"format": "text"},  
    }  
    if use_messages_format:  
      payload["messages"] = _to_input(messages_chat)  
      payload["instructions"] = sys_msg  
    else:  
      payload["input"] = _to_input(messages_chat)  
  
    try:  
      resp = await self._http.post(  
        url,  
        params={"api-version": api_version},  
        headers=self._headers_json,  
        json=payload,  
        timeout=self._timeout,  
      )  
    except Exception as err:  # noqa: BLE001  
      _LOGGER.error("Azure responses (non-stream) request failed: %s", err)  
      return ""  
  
    if resp.status_code >= 400:  
      text_body = await resp.aread()  
      try:  
        err_json = json.loads(text_body.decode("utf-8", "ignore") or "{}")  
      except Exception:  
        err_json = {}  
      msg = err_json.get("error", {}).get("message") or text_body.decode("utf-8", "ignore") or f"HTTP {resp.status_code}"  
      _LOGGER.error("Azure responses (non-stream) error: %s", msg)  
      return ""  
  
    try:  
      obj = resp.json()  
    except Exception:  
      try:  
        obj = json.loads((await resp.aread()).decode("utf-8", "ignore"))  
      except Exception:  
        obj = None  
  
    if not isinstance(obj, dict):  
      return ""  
  
    # Estrazione generica di tutto il testo  
    out = []  
  
    def _acc(node: Any) -> None:  
      if node is None:  
        return  
      if isinstance(node, str):  
        out.append(node)  
        return  
      if isinstance(node, list):  
        for it in node:  
          _acc(it)  
        return  
      if isinstance(node, dict):  
        txt = node.get("text")  
        if isinstance(txt, str):  
          out.append(txt)  
        _acc(node.get("output"))  
        _acc(node.get("content"))  
        _acc(node.get("message"))  
        _acc(node.get("data"))  
        _acc(node.get("choices"))  
  
    _acc(obj)  
    text = "".join(out).strip()  
    _LOGGER.debug("Responses non-stream extracted %d chars", len(text))  
    return text  
  
  async def _chat_completions_fallback(self, messages_chat: list[dict[str, str]]) -> str:  
    """Esegue Chat Completions (stream) con gestione del parametro token dinamico."""  
    def _chat_token_param_for_version(ver: str) -> str:  
      y, m, d = self._ver_date_tuple(ver)  
      return "max_completion_tokens" if (y, m, d) >= (2025, 3, 1) else "max_tokens"  
  
    text_out = ""  
    url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"  
    next_version = self._api_version  
    token_param = _chat_token_param_for_version(next_version)  
    attempted: set[str] = set()  
  
    while True:  
      pair_key = f"{next_version}::{token_param}"  
      if pair_key in attempted:  
        break  
      attempted.add(pair_key)  
  
      payload: dict[str, Any] = {  
        "messages": messages_chat,  
        "temperature": float(self._conf.get("temperature", 0.7)),  
        "stream": True,  
        token_param: int(self._conf.get("max_tokens", 1024)),  
      }  
  
      _LOGGER.debug(  
        "Calling Chat Completions api-version=%s with token param=%s",  
        next_version,  
        token_param,  
      )  
  
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
          _LOGGER.error("Azure chat stream error: %s", msg)  
  
          # Retry cambio parametro  
          if "Unsupported parameter: 'max_tokens'" in msg and token_param != "max_completion_tokens":  
            _LOGGER.debug("Retrying Chat switching token param to max_completion_tokens")  
            token_param = "max_completion_tokens"  
            continue  
          if "Unsupported parameter: 'max_completion_tokens'" in msg and token_param != "max_tokens":  
            _LOGGER.debug("Retrying Chat switching token param to max_tokens")  
            token_param = "max_tokens"  
            continue  
  
          # Retry API version richiesta (caso raro per chat)  
          if ("api-version 2025-03-01-preview" in msg) and next_version != "2025-03-01-preview":  
            _LOGGER.debug("Retrying Chat with api-version=2025-03-01-preview")  
            next_version = "2025-03-01-preview"  
            token_param = _chat_token_param_for_version(next_version)  
            continue  
  
          break  
  
        # Stream OK  
        async for raw_line in resp.aiter_lines():  
          if not raw_line:  
            continue  
          line = raw_line.strip()  
          if not line or line.startswith(":"):  
            continue  
          if not line.startswith("data:"):  
            continue  
  
          data_str = line[5:].lstrip()  
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
  
  agent = AzureOpenAIConversationAgent(hass, conf=conf)  
  conversation.async_set_agent(hass, config_entry, agent)  