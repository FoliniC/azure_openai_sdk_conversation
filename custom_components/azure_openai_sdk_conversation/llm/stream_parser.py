"""
Server-Sent Events (SSE) stream parser for Azure OpenAI APIs.

Parses SSE streams and yields structured events with type classification.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from ..core.logger import AgentLogger


class SSEStreamParser:
    """Parser for Server-Sent Events streams from Azure OpenAI."""
    
    def __init__(self, logger: AgentLogger) -> None:
        """
        Initialize SSE parser.
        
        Args:
            logger: Logger instance for debugging
        """
        self._logger = logger
    
    async def parse_stream(
        self,
        line_iterator: AsyncIterator[str],
    ) -> AsyncIterator[tuple[str, Any]]:
        """
        Parse SSE stream and yield (event_type, event_data) tuples.
        
        Args:
            line_iterator: Async iterator over raw lines from response
            
        Yields:
            Tuples of (event_type, event_data) where:
            - event_type: "delta" | "usage" | "error" | "done" | "unknown"
            - event_data: Parsed JSON dict or raw string
        """
        current_event: Optional[str] = None
        data_lines: list[str] = []
        
        async for raw_line in line_iterator:
            if raw_line is None:
                continue
            
            line = raw_line.rstrip("\n\r")
            
            # Empty line signals end of event
            if not line:
                if data_lines:
                    # Parse accumulated data
                    event_type, event_data = self._process_event(
                        current_event, data_lines
                    )
                    if event_type:
                        yield event_type, event_data
                    
                    # Reset for next event
                    current_event = None
                    data_lines = []
                continue
            
            # Comment line (ignore)
            if line.startswith(":"):
                continue
            
            # Event type line
            if line.startswith("event:"):
                current_event = line[6:].strip()
                continue
            
            # Data line
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
                continue
            
            # Unknown line format (log for debugging)
            self._logger.debug("Unknown SSE line format: %s", line[:100])
        
        # Process any remaining data
        if data_lines:
            event_type, event_data = self._process_event(current_event, data_lines)
            if event_type:
                yield event_type, event_data
    
    def _process_event(
        self,
        event_name: Optional[str],
        data_lines: list[str],
    ) -> tuple[Optional[str], Any]:
        """
        Process accumulated event data and classify event type.
        
        Args:
            event_name: Event name from "event:" line (if any)
            data_lines: Accumulated data lines
            
        Returns:
            Tuple of (event_type, parsed_data)
            Returns (None, None) if event should be skipped
        """
        if not data_lines:
            return None, None
        
        # Join data lines
        data_str = "\n".join(data_lines).strip()
        
        # Check for [DONE] marker
        if data_str == "[DONE]":
            return "done", {}
        
        # Try to parse as JSON
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            # Not JSON, return as raw string
            return "unknown", data_str
        
        # Classify event type based on content and event name
        event_type = self._classify_event(event_name, data)
        
        return event_type, data
    
    @staticmethod
    def _classify_event(event_name: Optional[str], data: Any) -> str:
        """
        Classify event type based on event name and data structure.
        
        Returns:
            "delta" | "usage" | "error" | "done" | "unknown"
        """
        if not isinstance(data, dict):
            return "unknown"
        
        # Use explicit event name if available
        if event_name:
            name_lower = event_name.lower()
            
            # Delta events (content streaming)
            if any(x in name_lower for x in [
                "delta", "output_text.delta", "message.delta", "content.delta"
            ]):
                return "delta"
            
            # Usage events (token counts)
            if "usage" in name_lower:
                return "usage"
            
            # Error events
            if "error" in name_lower:
                return "error"
            
            # Completion events
            if any(x in name_lower for x in [
                "done", "completed", "finish", "end"
            ]):
                return "done"
        
        # Infer from data structure
        
        # Check for error indicators
        if "error" in data:
            return "error"
        
        # Check for usage/token information
        if "usage" in data or any(k in data for k in [
            "prompt_tokens", "completion_tokens", "total_tokens",
            "input_tokens", "output_tokens"
        ]):
            return "usage"
        
        # Check for delta/content indicators
        if any(k in data for k in ["delta", "choices", "output", "content"]):
            # Check if it contains actual text content
            if SSEStreamParser._has_text_content(data):
                return "delta"
            
            # Check if it's a completion marker
            if SSEStreamParser._is_completion_marker(data):
                return "done"
        
        # Check for explicit type field
        event_type = data.get("type", data.get("event", "")).lower()
        if event_type:
            if "delta" in event_type or "content" in event_type:
                return "delta"
            elif "error" in event_type:
                return "error"
            elif "done" in event_type or "complete" in event_type:
                return "done"
        
        # Default to unknown
        return "unknown"
    
    @staticmethod
    def _has_text_content(data: dict) -> bool:
        """Check if data contains actual text content (not empty)."""
        def search_text(obj: Any, depth: int = 0) -> bool:
            if depth > 5:  # Prevent infinite recursion
                return False
            
            if isinstance(obj, str) and obj.strip():
                return True
            
            if isinstance(obj, dict):
                # Check common text fields
                for key in ["text", "content", "message"]:
                    if key in obj:
                        val = obj[key]
                        if isinstance(val, str) and val.strip():
                            return True
                        if search_text(val, depth + 1):
                            return True
                
                # Recursively search other fields
                for val in obj.values():
                    if search_text(val, depth + 1):
                        return True
            
            if isinstance(obj, list):
                for item in obj:
                    if search_text(item, depth + 1):
                        return True
            
            return False
        
        return search_text(data)
    
    @staticmethod
    def _is_completion_marker(data: dict) -> bool:
        """Check if data indicates completion/finish."""
        # Check choices[].finish_reason
        choices = data.get("choices", [])
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict):
                    finish_reason = choice.get("finish_reason")
                    if finish_reason and finish_reason != "null":
                        return True
        
        # Check for explicit done/complete flags
        return any(
            data.get(key) in [True, "done", "completed", "finished"]
            for key in ["done", "completed", "finished", "is_complete"]
        )