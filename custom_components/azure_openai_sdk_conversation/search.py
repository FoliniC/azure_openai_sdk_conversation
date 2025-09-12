"""Simple web search client used to enrich prompts."""  
from __future__ import annotations  
  
from typing import Any, Optional  
import json  
import httpx  
  
  
class WebSearchClient:  
  """Thin wrapper around Bing Web Search."""  
  
  BING_ENDPOINT_DEFAULT = "https://api.bing.microsoft.com/v7.0/search"  
  
  def __init__(self, api_key: str, endpoint: Optional[str] = None, max_results: int = 5) -> None:  
    self._api_key = api_key or ""  
    self._endpoint = (endpoint or self.BING_ENDPOINT_DEFAULT).rstrip("/")  
    self._max_results = max_results  
    self._client: httpx.AsyncClient | None = None  
  
  async def _client_async(self) -> httpx.AsyncClient:  
    if self._client is None:  
      self._client = httpx.AsyncClient(timeout=15)  
    return self._client  
  
  async def close(self) -> None:  
    if self._client is not None:  
      await self._client.aclose()  
      self._client = None  
  
  async def search(self, query: str) -> str:  
    """Return a small Markdown block with top search results; JSON parsed without blocking the loop."""  
    if not self._api_key or not query:  
      return ""  
  
    client = await self._client_async()  
    headers = {  
      "Ocp-Apim-Subscription-Key": self._api_key,  
      "Accept": "application/json",  
    }  
    params = {"q": query, "count": max(1, int(self._max_results or 5))}  
    url = self._endpoint  
  
    try:  
      resp = await client.get(url, headers=headers, params=params)  
    except Exception:  
      return ""  
  
    if resp.status_code >= 400:  
      # Non logghiamo dettagli sensibili qui  
      return ""  
  
    # Evita Response.json() (sincrono): usa aread + json.loads  
    raw = await resp.aread()  
    try:  
      data = json.loads(raw.decode("utf-8", "ignore"))  
    except Exception:  
      return ""  
  
    web_pages = (data or {}).get("webPages", {})  
    items: list[dict[str, Any]] = web_pages.get("value") or []  
    if not items:  
      return ""  
  
    lines = ["Top results:"]  
    for it in items[: self._max_results]:  
      name = it.get("name") or ""  
      url = it.get("url") or ""  
      snippet = it.get("snippet") or ""  
      if name and url:  
        lines.append(f"- [{name}]({url}) — {snippet}")  
  
    return "\n".join(lines)  