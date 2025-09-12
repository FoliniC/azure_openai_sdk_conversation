"""Lightweight Bing Web Search helper for Azure OpenAI SDK Conversation."""  
from __future__ import annotations  
  
import logging  
from typing import List  
  
import httpx  
  
_LOGGER = logging.getLogger(__name__)  
  
BING_ENDPOINT_DEFAULT = "https://api.bing.microsoft.com/v7.0/search"  
  
  
class WebSearchClient:  
    """Very small wrapper around Bing Web Search REST API v7."""  
  
    def __init__(  
        self,  
        api_key: str,  
        endpoint: str = BING_ENDPOINT_DEFAULT,  
        *,  
        max_results: int = 5,  
        timeout: float = 10.0,  
    ) -> None:  
        self._api_key = api_key  
        self._endpoint = endpoint  
        self._max_results = max_results  
        self._timeout = timeout  
        self._client = httpx.AsyncClient(  
            headers={  
                "Ocp-Apim-Subscription-Key": self._api_key,  
                "User-Agent": "ha-azure-openai-search/1.0",  
            },  
            timeout=self._timeout,  
        )  
  
    async def close(self) -> None:  
        await self._client.aclose()  
  
    async def search(self, query: str) -> str | None:  
        """Run a web search and return a formatted markdown string."""  
        params = {  
            "q": query,  
            "mkt": "en-US",  
            "safeSearch": "Moderate",  
            "count": self._max_results,  
            "textFormat": "Raw",  
        }  
        try:  
            resp = await self._client.get(self._endpoint, params=params)  
            resp.raise_for_status()  
            data = resp.json()  
        except (httpx.HTTPError, ValueError) as err:  
            _LOGGER.warning("Web search failed: %s", err)  
            return None  
  
        web_pages = data.get("webPages", {}).get("value", [])  
        if not web_pages:  
            return None  
  
        # Convert top N results to a compact markdown list  
        lines: List[str] = []  
        for idx, item in enumerate(web_pages[: self._max_results], start=1):  
            title = item.get("name", "No title")  
            snippet = item.get("snippet", "").strip().replace("\n", " ")  
            url = item.get("url", "")  
            lines.append(f"{idx}. **{title}** – {snippet}  \n   {url}")  
  
        return "\n".join(lines)  