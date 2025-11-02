# ============================================================================
# utils/validators.py
# ============================================================================
"""Validators for Azure OpenAI configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .api_version import APIVersionManager


class AzureOpenAIValidator:
    """Validator for Azure OpenAI credentials and configuration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        api_base: str,
        model: str,
    ) -> None:
        """
        Initialize validator.

        Args:
            hass: Home Assistant instance
            api_key: Azure OpenAI API key
            api_base: API base URL
            model: Model/deployment name
        """
        self._hass = hass
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model

    async def validate(self, api_version: str | None = None) -> dict[str, Any]:
        """
        Validate credentials by calling /openai/models endpoint.

        Args:
            api_version: API version to use (optional)

        Returns:
            Dict with validated settings

        Raises:
            Exception if validation fails
        """
        # Determine API version
        if not api_version:
            api_version = APIVersionManager.best_for_model(self._model)

        # Build request
        url = f"{self._api_base}/openai/models"
        headers = {
            "api-key": self._api_key,
            "Accept": "application/json",
        }

        # Execute request
        http = get_async_client(self._hass)
        try:
            resp = await http.get(
                url,
                params={"api-version": api_version},
                headers=headers,
                timeout=10,
            )
        except Exception as err:
            raise Exception(f"Connection failed: {err}") from err

        # Check response
        if resp.status_code == 401 or resp.status_code == 403:
            raise Exception("Invalid API key (unauthorized)")

        if resp.status_code == 404:
            raise Exception("Deployment not found or invalid endpoint")

        if resp.status_code >= 400:
            body = await resp.aread()
            raise Exception(
                f"HTTP {resp.status_code}: {body.decode('utf-8', 'ignore')}"
            )

        # Determine token parameter
        model_lower = self._model.lower()
        if model_lower.startswith("o"):
            token_param = "max_output_tokens"
        else:
            # Based on API version
            parts = api_version.split("-")
            try:
                year = int(parts[0])
                month = int(parts[1])
                if (year, month) >= (2025, 1):
                    token_param = "max_completion_tokens"
                else:
                    token_param = "max_tokens"
            except (ValueError, IndexError):
                token_param = "max_tokens"

        return {
            "api_version": api_version,
            "token_param": token_param,
        }

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        """
        Get model capabilities metadata.

        Returns:
            Dict of parameter name -> metadata
        """
        return {
            "temperature": {
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
                "step": 0.05,
            },
            "top_p": {
                "default": 1.0,
                "min": 0.0,
                "max": 1.0,
                "step": 0.01,
            },
            "max_tokens": {
                "default": 512,
                "min": 1,
                "max": 8192,
                "step": 1,
            },
        }
