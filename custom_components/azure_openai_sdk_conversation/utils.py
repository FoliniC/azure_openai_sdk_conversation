"""Utility helpers for Azure OpenAI SDK Conversation."""  
from __future__ import annotations  
  
import asyncio  
import json  
import logging  
import re  
import time  
from collections import OrderedDict  
from datetime import datetime, timedelta  
from typing import Any, Dict, Optional, Tuple  
  
import openai  
from openai import AsyncAzureOpenAI  
from homeassistant.core import HomeAssistant  
from homeassistant.helpers.httpx_client import get_async_client  
  
_LOGGER = logging.getLogger(__name__)  
  
  
# ---------------------------------------------------------------------------  
#  Small generic LRU cache with TTL – simple & dependency-free  
# ---------------------------------------------------------------------------  
class _LRUTTL(OrderedDict):  
  """Very small LRU-cache with TTL."""  
  
  def __init__(self, maxlen: int = 32, ttl: int = 3600) -> None:  
    super().__init__()  
    self._maxlen = maxlen  
    self._ttl = ttl  
  
  def get(self, key: str) -> Any | None:  # noqa: D401  
    item = super().get(key)  
    if not item:  
      return None  
    value, ts = item  
    if time.time() - ts > self._ttl:  
      super().__delitem__(key)  
      return None  
    # refresh ordering  
    super().__delitem__(key)  
    super().__setitem__(key, (value, ts))  
    return value  
  
  def set(self, key: str, value: Any) -> None:  
    if key in self:  
      super().__delitem__(key)  
    elif len(self) >= self._maxlen:  
      self.popitem(last=False)  
    super().__setitem__(key, (value, time.time()))  
  
  
_CAPS_CACHE: _LRUTTL = _LRUTTL(maxlen=64, ttl=4 * 3600)  # 4 h cache  
  
  
# ---------------------------------------------------------------------------  
#  API-VERSION MANAGER  
# ---------------------------------------------------------------------------  
class APIVersionManager:  
  """Gestisce versioni note, estrazione da errori e mapping token-param."""  
  
  _RE_VERSION = re.compile(r"(\d{4}-\d{2}-\d{2}(?:-preview)?)")  
  
  # Ordine d'inserimento conta per best_for_model: prima la più recente consigliata  
  _KNOWN: dict[str, dict[str, Any]] = {  
    "2025-03-01-preview": {  
      "supports_o1": True,  
      "supports_web_search": True,  
      "token_param": "max_completion_tokens",  
      "since": datetime(2025, 3, 1),  
    },  
    "2025-01-01-preview": {  
      "supports_o1": True,  
      "supports_web_search": True,  
      "token_param": "max_completion_tokens",  
      "since": datetime(2025, 1, 1),  
    },  
    "2024-12-01-preview": {  
      "supports_o1": True,  
      "supports_web_search": False,  
      "token_param": "max_tokens",  
      "since": datetime(2024, 12, 1),  
    },  
    "2024-10-01-preview": {  
      "supports_o1": False,  
      "supports_web_search": False,  
      "token_param": "max_tokens",  
      "since": datetime(2024, 10, 1),  
    },  
    "2024-08-06": {  
      "supports_o1": False,  
      "supports_web_search": True,  
      "token_param": "max_tokens",  
      "since": datetime(2024, 8, 6),  
    },  
  }  
  
  @classmethod  
  def extract_version_from_error(cls, msg: str | None) -> str | None:  
    if not msg:  
      return None  
    found = cls._RE_VERSION.search(msg)  
    return found.group(1) if found else None  
  
  @classmethod  
  def best_for_model(cls, model: str) -> str:  
    # Preferisci la più recente che supporta "o*" (o1, o3, ...)  
    if model.lower().startswith("o"):  
      for ver, info in cls._KNOWN.items():  
        if info.get("supports_o1"):  
          return ver  
    # Default consigliato  
    return "2025-03-01-preview"  
  
  @classmethod  
  def token_param(cls, api_version: str) -> str:  
    return cls._KNOWN.get(api_version, {}).get("token_param", "max_tokens")  
  
  
# ---------------------------------------------------------------------------  
#  LOGGER  
# ---------------------------------------------------------------------------  
class AzureOpenAILogger:  
  """Logger con sanitizzazione automatica dei dati sensibili."""  
  
  _SENSITIVE = ("key", "token", "authorization", "secret", "password")  
  
  def __init__(self, name: str) -> None:  
    self._log = logging.getLogger(name)  
  
  # --- sanitisation helpers -------------------------------------------------  
  def _clean(self, obj: Any) -> Any:  
    if isinstance(obj, dict):  
      return {  
        k: "***" if any(s in k.lower() for s in self._SENSITIVE) else self._clean(v)  
        for k, v in obj.items()  
      }  
    if isinstance(obj, list):  
      return [self._clean(it) for it in obj]  
    return obj  
  
  # --- public logging helpers ----------------------------------------------  
  def debug_api(self, method: str, endpoint: str, params: dict[str, Any]) -> None:  
    self._log.debug("API %s %s – params=%s", method, endpoint, self._clean(params))  
  
  def debug_resp(self, status: int, data: Any) -> None:  
    self._log.debug("API RESP %s – %s", status, str(self._clean(data))[:500])  
  
  def error(self, err: Exception, ctx: dict[str, Any] | None = None) -> None:  
    self._log.error("%s – ctx=%s", err, self._clean(ctx or {}))  
  
  
# ---------------------------------------------------------------------------  
#  VALIDATOR  (retry automatico + gestione errors)  
# ---------------------------------------------------------------------------  
class AzureOpenAIValidator:  
  """Convalida credenziali/deployment provando versioni & token-param diversi."""  
  
  _RETRY_BACKOFF = (0.2, 0.5, 1.0)  # sec  
  
  def __init__(  
    self,  
    hass: HomeAssistant,  
    api_key: str,  
    api_base: str,  
    deployment: str,  
    logger: AzureOpenAILogger | None = None,  
  ) -> None:  
    from . import normalize_azure_endpoint  
  
    self._hass = hass  
    self._api_key = api_key  
    self._endpoint = normalize_azure_endpoint(api_base).rstrip("/").removesuffix("/openai")  
    self._deployment = deployment  
    self._log = logger or AzureOpenAILogger(__name__)  
    self._successful: dict[str, Any] | None = None  
  
  # ------------------------------------------------------------------ helpers  
  async def _probe(  
    self,  
    api_version: str,  
    token_param: str,  
  ) -> bool:  
    client = AsyncAzureOpenAI(  
      api_key=self._api_key,  
      api_version=api_version,  
      azure_endpoint=self._endpoint,  
      http_client=get_async_client(self._hass),  
    )  
    payload = {  
      "model": self._deployment,  
      "messages": [  
        {"role": "system", "content": "ping"},  
        {"role": "user", "content": "ping"},  
      ],  
      token_param: 10,  
    }  
    self._log.debug_api("POST", "/chat/completions", {"ver": api_version, **payload})  
    await client.chat.completions.create(**payload)  # noqa: S101  
    return True  
  
  # ------------------------------------------------------------------ public  
  async def validate(self, initial_version: str | None = None) -> dict[str, Any]:  
    versions: list[str] = []  
    if initial_version:  
      versions.append(initial_version)  
    best = APIVersionManager.best_for_model(self._deployment)  
    if best not in versions:  
      versions.append(best)  
    versions.extend([v for v in APIVersionManager._KNOWN if v not in versions])  
  
    last_exc: Exception | None = None  
  
    for api_version in versions:  
      for token_param in (  
        APIVersionManager.token_param(api_version),  
        "max_completion_tokens",  
        "max_tokens",  
      ):  
        try:  
          await self._probe(api_version, token_param)  
          self._successful = {  
            "api_version": api_version,  
            "token_param": token_param,  
          }  
          return self._successful  
        except openai.BadRequestError as err:  
          # prova a estrarre versione suggerita  
          suggested = APIVersionManager.extract_version_from_error(str(err))  
          if suggested and suggested not in versions:  
            versions.insert(0, suggested)  
          last_exc = err  
        except openai.AuthenticationError as err:  
          raise  # irrecoverable  
        except Exception as err:  # pylint: disable=broad-except  
          last_exc = err  
      await asyncio.sleep(self._RETRY_BACKOFF[min(len(self._RETRY_BACKOFF) - 1, versions.index(api_version))])  
  
    raise last_exc or RuntimeError("Unable to validate credentials")  
  
  # ---------------------------------------------------------------- capabilities  
  async def capabilities(self) -> dict[str, dict[str, Any]]:  
    if not self._successful:  
      raise RuntimeError("validate() not executed")  
  
    cache_key = f"{self._endpoint}:{self._deployment}:{self._successful['api_version']}"  
    if (caps := _CAPS_CACHE.get(cache_key)) is not None:  
      return caps  
  
    client = AsyncAzureOpenAI(  
      api_key=self._api_key,  
      api_version=self._successful["api_version"],  
      azure_endpoint=self._endpoint,  
      http_client=get_async_client(self._hass),  
    )  
    items = []  
    try:  
      if hasattr(client, "deployments"):  
        resp = await client.deployments.list()  
      else:  
        resp = await client.models.list()  
      items = getattr(resp, "data", [])  
    except Exception as err:  # pylint: disable=broad-except  
      self._log.error(err, {"stage": "caps"})  
  
    params: dict[str, dict[str, Any]] = {}  
    for obj in items:  
      if obj.id != self._deployment:  
        continue  
      caps = getattr(obj, "capabilities", None)  
      if not caps:  
        break  
      sampling = getattr(caps, "sampling_parameters", None)  
      if not sampling:  
        break  
      for itm in sampling:  
        name = itm.get("name")  
        if name:  
          params[name] = {  
            "default": itm.get("default"),  
            "min": itm.get("minimum"),  
            "max": itm.get("maximum"),  
            "step": itm.get("step"),  
          }  
      break  
  
    _CAPS_CACHE.set(cache_key, params)  
    return params  