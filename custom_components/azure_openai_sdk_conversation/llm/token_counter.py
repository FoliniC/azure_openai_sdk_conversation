"""
Token counting and estimation for Azure OpenAI models.

Provides both exact counting (from API usage field) and estimation
(heuristic-based for fallback).
"""

from __future__ import annotations

from typing import Any, Optional


class TokenCounter:
    """Token counter with estimation fallback."""
    
    # Heuristic: ~0.75 tokens per character for English text
    # Varies by language: English ~0.75, Italian ~0.70, code ~0.60
    CHARS_PER_TOKEN = {
        "default": 1.3,      # ~0.77 tokens/char
        "english": 1.3,
        "italian": 1.4,      # More verbose
        "code": 1.7,         # More compact
        "mixed": 1.35,
    }
    
    def estimate_tokens(
        self,
        prompt_messages: list[dict[str, Any]],
        completion_text: str,
        language: str = "default",
    ) -> dict[str, int]:
        """
        Estimate token counts using heuristics.
        
        Args:
            prompt_messages: List of message dicts (system, user, etc.)
            completion_text: Generated completion text
            language: Language hint for estimation accuracy
            
        Returns:
            Dict with {"prompt": int, "completion": int, "total": int}
        """
        chars_per_token = self.CHARS_PER_TOKEN.get(language, self.CHARS_PER_TOKEN["default"])
        
        # Estimate prompt tokens
        prompt_chars = 0
        for msg in prompt_messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt_chars += len(content)
            elif isinstance(content, list):
                # Handle content array (text + other modalities)
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text", "")
                        if isinstance(text, str):
                            prompt_chars += len(text)
        
        # Add overhead for message formatting (~4 tokens per message)
        prompt_tokens = int(prompt_chars / chars_per_token) + (len(prompt_messages) * 4)
        
        # Estimate completion tokens
        completion_tokens = int(len(completion_text) / chars_per_token)
        
        return {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
        }
    
    @staticmethod
    def extract_from_usage(usage_data: dict[str, Any]) -> dict[str, int]:
        """
        Extract token counts from API usage field.
        
        Args:
            usage_data: Usage dict from API response
            
        Returns:
            Dict with {"prompt": int, "completion": int, "total": int}
        """
        if not isinstance(usage_data, dict):
            return {"prompt": 0, "completion": 0, "total": 0}
        
        # Try various field names (API inconsistency)
        prompt = usage_data.get(
            "prompt_tokens",
            usage_data.get("input_tokens", 0)
        )
        
        completion = usage_data.get(
            "completion_tokens",
            usage_data.get("output_tokens", 0)
        )
        
        total = usage_data.get(
            "total_tokens",
            prompt + completion
        )
        
        return {
            "prompt": int(prompt),
            "completion": int(completion),
            "total": int(total),
        }
    
    def detect_language(self, text: str) -> str:
        """
        Detect language for better token estimation.
        
        Simple heuristic based on character patterns.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language hint: "english" | "italian" | "code" | "mixed" | "default"
        """
        if not text:
            return "default"
        
        # Count different character types
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        accented_chars = sum(1 for c in text if 'à' <= c <= 'ù' or 'À' <= c <= 'Ù')
        code_indicators = sum(1 for c in text if c in "{}[]();=<>")
        
        total = len(text)
        if total == 0:
            return "default"
        
        # Code detection
        if code_indicators / total > 0.15:
            return "code"
        
        # Italian detection (high accented chars)
        if accented_chars / total > 0.02:
            return "italian"
        
        # English detection (high ASCII, low accented)
        if ascii_chars / total > 0.95:
            return "english"
        
        # Mixed or unknown
        return "mixed"
    
    def count_with_fallback(
        self,
        usage_data: Optional[dict[str, Any]],
        prompt_messages: list[dict[str, Any]],
        completion_text: str,
    ) -> dict[str, int]:
        """
        Count tokens with automatic fallback to estimation.
        
        Tries to extract from usage_data first, falls back to estimation.
        
        Args:
            usage_data: Usage dict from API (may be None)
            prompt_messages: Prompt messages for estimation fallback
            completion_text: Completion text for estimation fallback
            
        Returns:
            Dict with {"prompt": int, "completion": int, "total": int}
        """
        if usage_data:
            counts = self.extract_from_usage(usage_data)
            if counts["total"] > 0:
                return counts
        
        # Fallback to estimation
        language = self.detect_language(completion_text)
        return self.estimate_tokens(prompt_messages, completion_text, language)