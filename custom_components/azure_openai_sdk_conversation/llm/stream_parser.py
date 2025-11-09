"""
SSE Stream Parser with tool call accumulation and debugging.

Properly handles streaming tool call arguments from delta fragments.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolCallAccumulator:
    """Accumulator for streaming tool call arguments."""

    id: str
    function_name: str
    arguments_fragments: list[str] = field(default_factory=list)

    @property
    def accumulated_arguments(self) -> str:
        """Get the accumulated argument string."""
        return "".join(self.arguments_fragments)

    def add_argument_fragment(self, fragment: str) -> None:
        """Add an argument fragment."""
        self.arguments_fragments.append(fragment)

    def is_complete(self) -> bool:
        """Check if we have a complete JSON object."""
        args = self.accumulated_arguments.strip()
        if not args:
            # Empty arguments can be valid if the function has no params,
            # but the model should send '{}'. We'll be lenient.
            return True
        try:
            json.loads(args)
            return True
        except json.JSONDecodeError:
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI tool call dict."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.function_name,
                "arguments": self.accumulated_arguments,
            },
        }


@dataclass
class ChoiceAccumulator:
    """Accumulator for a single choice with potential tool calls."""

    index: int
    content_fragments: list[str] = field(default_factory=list)
    # Use a list to store tool calls in order based on their index
    tool_calls: list[ToolCallAccumulator] = field(default_factory=list)
    finish_reason: Optional[str] = None

    @property
    def accumulated_content(self) -> str:
        """Get the accumulated content."""
        return "".join(self.content_fragments)

    def add_content_fragment(self, fragment: str) -> None:
        """Add a content fragment."""
        if fragment:
            self.content_fragments.append(fragment)

    def process_tool_call_delta(self, delta: dict[str, Any]) -> None:
        """Process a tool call delta chunk from the stream."""
        index = delta.get("index")
        if index is None:
            return

        # Ensure the list of accumulators is long enough
        while len(self.tool_calls) <= index:
            self.tool_calls.append(ToolCallAccumulator(id="", function_name=""))

        accumulator = self.tool_calls[index]

        # The 'id' is usually sent only in the first delta for a tool call
        if "id" in delta and delta["id"]:
            accumulator.id = delta["id"]

        function_delta = delta.get("function", {})
        if function_delta:
            # The 'name' is also usually in the first delta
            if "name" in function_delta and function_delta["name"]:
                accumulator.function_name = function_delta["name"]

            # 'arguments' fragments are streamed in subsequent deltas
            if "arguments" in function_delta:
                accumulator.add_argument_fragment(function_delta["arguments"])

    def get_complete_tool_calls(self) -> list[dict[str, Any]]:
        """Get all complete and valid tool calls from this choice."""
        complete = []
        for tool_call in self.tool_calls:
            # A tool call is only valid if it has an ID and name and the arguments are valid JSON
            if tool_call.id and tool_call.function_name and tool_call.is_complete():
                complete.append(tool_call.to_dict())
        return complete


class SSEStreamParser:
    """Parser for Azure OpenAI SSE streaming responses."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the parser."""
        self._logger = logger or LOGGER

    def parse_stream(
        self,
        stream_lines: list[str],
    ) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
        """Parse a complete SSE stream from collected lines.

        Args:
            stream_lines: List of SSE lines collected from response

        Returns:
            Tuple of (content_text, tool_calls, token_counts)
        """
        accumulators: dict[int, ChoiceAccumulator] = {}
        token_counts = {"prompt": 0, "completion": 0, "total": 0}

        for line in stream_lines:
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue

            if "[DONE]" in line:
                break

            data_str = line[6:]
            try:
                delta = json.loads(data_str)
            except json.JSONDecodeError:
                self._logger.warning("Failed to parse SSE delta: %s", data_str)
                continue

            for choice in delta.get("choices", []):
                index = choice.get("index", 0)
                if index not in accumulators:
                    accumulators[index] = ChoiceAccumulator(index=index)

                acc = accumulators[index]

                if "finish_reason" in choice:
                    acc.finish_reason = choice.get("finish_reason")

                if "delta" in choice:
                    delta_obj = choice["delta"]
                    if delta_obj.get("content"):
                        acc.add_content_fragment(delta_obj["content"])

                    for tool_call_delta in delta_obj.get("tool_calls", []):
                        acc.process_tool_call_delta(tool_call_delta)

            if "usage" in delta and delta["usage"]:
                usage = delta["usage"]
                if "prompt_tokens" in usage:
                    token_counts["prompt"] = usage["prompt_tokens"]
                if "completion_tokens" in usage:
                    token_counts["completion"] = usage["completion_tokens"]
                if "total_tokens" in usage:
                    token_counts["total"] = usage["total_tokens"]

        primary_choice = accumulators.get(0)
        if not primary_choice:
            return "", [], token_counts

        complete_tool_calls = primary_choice.get_complete_tool_calls()

        # Debug logging
        for tool_call in primary_choice.tool_calls:
            if tool_call.is_complete():
                self._logger.debug(
                    "Complete tool call parsed: id=%s, name=%s, args=%s",
                    tool_call.id,
                    tool_call.function_name,
                    tool_call.accumulated_arguments,
                )
            else:
                self._logger.warning(
                    "Incomplete tool call parsed: id=%s, name=%s, args=%s",
                    tool_call.id,
                    tool_call.function_name,
                    tool_call.accumulated_arguments,
                )

        return (
            primary_choice.accumulated_content,
            complete_tool_calls,
            token_counts,
        )
