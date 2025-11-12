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
    """API version management and model recommendations."""

    # Map version -> metadata with 'since' as a tuple(year, month, day)
    _KNOWN: dict[str, dict[str, Any]] = {
        # Common examples (add/remove as needed)
        "2024-10-01-preview": {"since": (2024, 10, 1)},
        "2025-01-01-preview": {"since": (2025, 1, 1)},
        "2025-03-01-preview": {
            "since": (2025, 3, 1),
            "responses_min": True,  # Official Responses API from here on
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
        """List sorted by 'since' ascending, deterministic."""
        return sorted(
            cls._KNOWN.keys(),
            key=lambda v: cls._KNOWN.get(v, {}).get("since", cls._date_tuple(v)),
        )

    @classmethod
    def ensure_min(cls, ver: str, minimum: str) -> str:
        """Returns 'ver' if >= minimum, otherwise 'minimum'."""
        v = cls._date_tuple(ver)
        m = cls._date_tuple(minimum)
        return ver if v >= m else minimum

    @classmethod
    def best_for_model(cls, model: str | None, fallback: str | None = None) -> str:
        """
        Selects recommended version deterministically:
        - for 'o*' models, force at least 2025-03-01-preview (Responses),
        - otherwise use the last known (sorted by 'since') or fallback.
        """
        m = (model or "").strip().lower()
        if m.startswith("o"):
            if "2025-03-01-preview" in cls._KNOWN:
                return "2025-03-01-preview"
        # Not 'o*': choose the last known version
        versions = cls.known_versions()
        if versions:
            return versions[-1]
        return fallback or "2025-01-01-preview"


class TokenParamHelper:
    """Token parameter selector based on api-version."""

    @staticmethod
    def responses_token_param_for_version(ver: str) -> str:
        """Responses: from 2025-03-01-preview => max_output_tokens, otherwise max_completion_tokens."""
        y, m, d = APIVersionManager._date_tuple(ver)
        return (
            "max_output_tokens"
            if (y, m, d) >= (2025, 3, 1)
            else "max_completion_tokens"
        )

    @staticmethod
    def chat_token_param_for_version(ver: str) -> str:
        """Chat: from 2025-01-01-preview => max_completion_tokens, otherwise max_tokens."""
        y, m, d = APIVersionManager._date_tuple(ver)
        return "max_completion_tokens" if (y, m, d) >= (2025, 1, 1) else "max_tokens"


def redact_api_key(value: str | None) -> str:
    """Obscures an API key in logs/UI, leaving only the first/last 3 chars visible."""
    if not value:
        return ""
    val = str(value)
    if len(val) <= 8:
        return "*" * len(val)
    return f"{val[:3]}***{val[-3:]}"


class AzureOpenAILogger:
    """Thin wrapper for the logger, compatible with use in the validator."""

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
    Validator for Step 1 of the config flow:
    - verifies credentials by calling /openai/models,
    - determines the effective api_version and a consistent token_param for the model.
    """

    def __init__(
        self,
        hass: Any,
        api_key: str,
        api_base: str,
        chat_model: str,
        log: AzureOpenAILogger,
    ) -> None:
        self._hass = hass
        self._api_key = (api_key or "").strip()
        self._api_base = (api_base or "").rstrip("/")
        self._model = (chat_model or "").strip()
        self._log = log

    async def validate(self, api_version: str | None) -> dict[str, Any]:
        """Returns {'api_version': str, 'token_param': str} or raises an exception with messages useful for the UI."""
        # Normalize recommended api-version
        requested_version = (
            api_version or ""
        ).strip() or APIVersionManager.best_for_model(self._model)
        use_responses = self._model.lower().startswith("o")
        effective_version = (
            APIVersionManager.ensure_min(requested_version, "2025-03-01-preview")
            if use_responses
            else requested_version
        )

        base = self._api_base
        if "://" not in base:
            base = f"https://{base}"
        url = f"{base}/openai/models"

        http = get_async_client(self._hass)
        headers = {"api-key": self._api_key, "Accept": "application/json"}

        self._log.debug(
            "Validating Azure OpenAI credentials at %s (api-version=%s)",
            base,
            effective_version,
        )
        try:
            resp = await http.get(
                url,
                params={"api-version": effective_version},
                headers=headers,
                timeout=10,
            )
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
        Returns metadata for the second step (dynamic fields).
        Default values are aligned with RECOMMENDED_* constants; generic ranges are safe.
        """
        caps: dict[str, dict[str, Any]] = {
            "temperature": {
                "default": RECOMMENDED_TEMPERATURE,
                "min": 0.0,
                "max": 2.0,
                "step": 0.05,
            },
            "top_p": {
                "default": RECOMMENDED_TOP_P,
                "min": 0.0,
                "max": 1.0,
                "step": 0.01,
            },
            "max_tokens": {
                "default": RECOMMENDED_MAX_TOKENS,
                "min": 1,
                "max": 8192,
                "step": 1,
            },
            "reasoning_effort": {"default": RECOMMENDED_REASONING_EFFORT},
            "api_timeout": {
                "default": RECOMMENDED_API_TIMEOUT,
                "min": 5,
                "max": 120,
                "step": 1,
            },
            "exposed_entities_limit": {
                "default": RECOMMENDED_EXPOSED_ENTITIES_LIMIT,
                "min": 50,
                "max": 2000,
                "step": 10,
            },
            # New: early wait timeout for the first response chunk
            "early_timeout_seconds": {
                "default": RECOMMENDED_EARLY_TIMEOUT_SECONDS,
                "min": 1,
                "max": 60,
                "step": 1,
            },
        }
        # Note: you can expand with other specific fields in the future.
        return caps
