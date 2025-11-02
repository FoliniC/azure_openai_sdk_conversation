# ============================================================================
# utils/search.py
# ============================================================================
"""Web search client (stub for future implementation)."""

from __future__ import annotations



class WebSearchClient:
    """Client for web search integration."""
    
    BING_ENDPOINT_DEFAULT = "https://api.bing.microsoft.com/v7.0/search"
    
    def __init__(
        self,
        api_key: str,
        endpoint: str | None = None,
        max_results: int = 5,
    ) -> None:
        """
        Initialize web search client.
        
        Args:
            api_key: Bing API key
            endpoint: Bing endpoint URL
            max_results: Maximum results to return
        """
        self._api_key = api_key
        self._endpoint = endpoint or self.BING_ENDPOINT_DEFAULT
        self._max_results = max_results
    
    async def search(self, query: str) -> str:
        """
        Execute web search and return formatted results.
        
        Args:
            query: Search query
            
        Returns:
            Formatted search results as markdown
        """
        # Stub implementation
        # TODO: Implement actual Bing API call
        return f"Web search results for: {query}\n\n*(Not implemented)*"
    
    async def close(self) -> None:
        """Clean up resources."""
        pass