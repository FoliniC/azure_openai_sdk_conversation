"""Utility helpers for API versions and token parameter selection."""  
from __future__ import annotations  
  
from typing import Any  
import logging  
  
from homeassistant.helpers.httpx_client import get_async_client  
  
from .const import (  
    RECOMMENDED_MAX_TOKENS,  
    RECOMMENDED_REASONING_EFFORT,  
    RECOMMENDED_TEMPERATURE,  
    RECOMMENDED_TOP_P,  
    RECOMMENDED_API_TIMEOUT,  
    RECOMMENDED_EXPOSED_ENTITIES_LIMIT,  
    RECOMMENDED_EARLY_TIMEOUT_SECONDS,  
)  
  
  
class APIVersionManager:  
    """Gestione versioni API e raccomandazioni per modello."""  
  
    # Mappa version -> metadata con 'since' come tuple(year, month, day)  
    _KNOWN: dict[str, dict[str, Any]] = {  
        # Esempi comuni (aggiungi/rimuovi in base alle tue necessità)  
        "2024-10-01-preview": {"since": (2024, 10, 1)},  
        "2025-01-01-preview": {"since": (2025, 1, 1)},  
        "2025-03-01-preview": {  
            "since": (2025, 3, 1),  
            "responses_min": True,  # Responses API ufficiale da qui in poi  
        },  
    }  
  
    @classmethod  
    def _date_tuple(cls, ver: str) -> tuple[int, int, int]:  
        core = (ver or "").split("-preview")[0]  
        parts = core.split("-")  
        try:  
            return (int(parts[0]), int(parts[1]), int(parts[2]))  
        except Exception:  # noqa: BLE001  
            return (1900, 1, 1)  
  
    @classmethod  
    def known_versions(cls) -> list[str]:  
        """Lista ordinata per 'since' ascendente, deterministica."""  
        return sorted(  
            cls._KNOWN.keys(),  
            key=lambda v: cls._KNOWN.get(v, {}).get("since", cls._date_tuple(v)),  
        )  
  
    @classmethod  
    def ensure_min(cls, ver: str, minimum: str) -> str:  
        """Ritorna 'ver' se >= minimum, altrimenti 'minimum'."""  
        v = cls._date_tuple(ver)  
        m = cls._date_tuple(minimum)  
        return ver if v >= m else minimum  
  
    @classmethod  
    def best_for_model(cls, model: str | None, fallback: str | None = None) -> str:  
        """  
        Seleziona versione consigliata in modo deterministico:  
        - per modelli 'o*' forza almeno 2025-03-01-preview (Responses),  
        - altrimenti usa l'ultima nota (ordinata per 'since') o fallback.  
        """  
        m = (model or "").strip().lower()  
        if m.startswith("o"):  
            if "2025-03-01-preview" in cls._KNOWN:  
                return "2025-03-01-preview"  
        # Non 'o*': scegli l'ultima versione conosciuta  
        versions = cls.known_versions()  
        if versions:  
            return versions[-1]  
        return fallback or "2025-01-01-preview"  
  
  
class TokenParamHelper:  
    """Selettore del parametro token in base alla api-version."""  
  
    @staticmethod  
    def responses_token_param_for_version(ver: str) -> str:  
        """Responses: da 2025-03-01-preview => max_output_tokens, altrimenti max_completion_tokens."""  
        y, m, d = APIVersionManager._date_tuple(ver)  
        return "max_output_tokens" if (y, m, d) >= (2025, 3, 1) else "max_completion_tokens"  
  
    @staticmethod  
    def chat_token_param_for_version(ver: str) -> str:  
        """Chat: da 2025-01-01-preview => max_completion_tokens, altrimenti max_tokens."""  
        y, m, d = APIVersionManager._date_tuple(ver)  
        return "max_completion_tokens" if (y, m, d) >= (2025, 1, 1) else "max_tokens"  
  
  
def redact_api_key(value: str | None) -> str:  
    """Oscura una API key in log/UI, lasciando visibili solo i primi/ultimi 3 char."""  
    if not value:  
        return ""  
    val = str(value)  
    if len(val) <= 8:  
        return "*" * len(val)  
    return f"{val[:3]}***{val[-3:]}"  
  
  
class AzureOpenAILogger:  
    """Sottile wrapper per il logger, compatibile con l'uso nel validator."""  
  
    def __init__(self, name: str) -> None:  
        self._log = logging.getLogger(name)  
  
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:  
        self._log.debug(msg, *args, **kwargs)  
  
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:  
        self._log.info(msg, *args, **kwargs)  
  
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:  
        self._log.warning(msg, *args, **kwargs)  
  
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:  
        self._log.error(msg, *args, **kwargs)  
  
    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:  
        self._log.exception(msg, *args, **kwargs)  
  
  
class AzureOpenAIValidator:  
    """  
    Validator per Step 1 del config flow:  
    - verifica credenziali chiamando /openai/models,  
    - determina api_version effettiva e token_param coerenti con il modello.  
    """  
  
    def __init__(self, hass: Any, api_key: str, api_base: str, chat_model: str, log: AzureOpenAILogger) -> None:  
        self._hass = hass  
        self._api_key = (api_key or "").strip()  
        self._api_base = (api_base or "").rstrip("/")  
        self._model = (chat_model or "").strip()  
        self._log = log  
  
    async def validate(self, api_version: str | None) -> dict[str, Any]:  
        """Ritorna {'api_version': str, 'token_param': str} o solleva un'eccezione con messaggi utili alla UI."""  
        # Normalizza api-version consigliata  
        requested_version = (api_version or "").strip() or APIVersionManager.best_for_model(self._model)  
        use_responses = self._model.lower().startswith("o")  
        effective_version = APIVersionManager.ensure_min(requested_version, "2025-03-01-preview") if use_responses else requested_version  
  
        base = self._api_base  
        if "://" not in base:  
            base = f"https://{base}"  
        url = f"{base}/openai/models"  
  
        http = get_async_client(self._hass)  
        headers = {"api-key": self._api_key, "Accept": "application/json"}  
  
        self._log.debug("Validating Azure OpenAI credentials at %s (api-version=%s)", base, effective_version)  
        try:  
            resp = await http.get(url, params={"api-version": effective_version}, headers=headers, timeout=10)  
        except Exception as err:  # noqa: BLE001  
            raise Exception(f"cannot_connect: {err}") from err  
  
        if resp.status_code in (401, 403):  
            raise Exception("invalid_auth: unauthorized/forbidden (401/403)")  
        if resp.status_code == 404:  
            text = (await resp.aread()).decode("utf-8", "ignore")  
            raise Exception(f"invalid_deployment or not found (404): {text}")  
        if resp.status_code >= 400:  
            text = (await resp.aread()).decode("utf-8", "ignore")  
            raise Exception(f"unknown: HTTP {resp.status_code}: {text}")  
  
        token_param = (  
            TokenParamHelper.responses_token_param_for_version(effective_version)  
            if use_responses  
            else TokenParamHelper.chat_token_param_for_version(effective_version)  
        )  
        return {"api_version": effective_version, "token_param": token_param}  
  
    async def capabilities(self) -> dict[str, dict[str, Any]]:  
        """  
        Ritorna metadati per il secondo step (campi dinamici).  
        Valori di default allineati alle costanti RECOMMENDED_*; range generici sicuri.  
        """  
        caps: dict[str, dict[str, Any]] = {  
            "temperature": {"default": RECOMMENDED_TEMPERATURE, "min": 0.0, "max": 2.0, "step": 0.05},  
            "top_p": {"default": RECOMMENDED_TOP_P, "min": 0.0, "max": 1.0, "step": 0.01},  
            "max_tokens": {"default": RECOMMENDED_MAX_TOKENS, "min": 1, "max": 8192, "step": 1},  
            "reasoning_effort": {"default": RECOMMENDED_REASONING_EFFORT},  
            "api_timeout": {"default": RECOMMENDED_API_TIMEOUT, "min": 5, "max": 120, "step": 1},  
            "exposed_entities_limit": {"default": RECOMMENDED_EXPOSED_ENTITIES_LIMIT, "min": 50, "max": 2000, "step": 10},  
            # Nuovo: early wait timeout per primo chunk di risposta  
            "early_timeout_seconds": {"default": RECOMMENDED_EARLY_TIMEOUT_SECONDS, "min": 1, "max": 60, "step": 1},  
        }  
        # Nota: puoi espandere con altri campi specifici in futuro.  
        return caps  