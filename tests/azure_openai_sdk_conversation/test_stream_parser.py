"""Tests for the SSE stream parser."""

import json

import pytest

from custom_components.azure_openai_sdk_conversation.llm.stream_parser import (
    SSEStreamParser,
    ToolCallAccumulator,
)


@pytest.fixture
def parser():
    """SSEStreamParser instance."""
    return SSEStreamParser()


def test_accumulator_partials():
    """Test accumulating partial JSON arguments."""
    acc = ToolCallAccumulator(id="1", function_name="test")
    acc.add_argument_fragment('{"')
    assert not acc.is_complete()
    acc.add_argument_fragment('key": "val"}')
    assert acc.is_complete()
    assert json.loads(acc.accumulated_arguments) == {"key": "val"}


def test_parse_stream_basic_content(parser):
    """Test parsing basic content from SSE stream."""
    lines = [
        'data: {"choices": [{"index": 0, "delta": {"content": "Hello"}}]}',
        'data: {"choices": [{"index": 0, "delta": {"content": " world!"}}]}',
        "data: [DONE]",
    ]

    content, tool_calls, tokens = parser.parse_stream(lines)

    assert content == "Hello world!"
    assert tool_calls == []


def test_parse_stream_tool_calls(parser):
    """Test parsing tool calls from SSE stream."""
    # Ensure every delta has index and correct structure
    lines = [
        # Chunk 1: Define ID and function name
        'data: {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_123", "type": "function", "function": {"name": "test_tool", "arguments": ""}}]}}]}',
        # Chunk 2: Argument fragment 1
        'data: {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\\"foo\\": "}}]}}]}',
        # Chunk 3: Argument fragment 2
        'data: {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\\"bar\\"}"}}]}}]}',
        "data: [DONE]",
    ]

    content, tool_calls, tokens = parser.parse_stream(lines)

    assert len(tool_calls) == 1
    call = tool_calls[0]
    assert call["id"] == "call_123"
    assert call["function"]["name"] == "test_tool"
    assert json.loads(call["function"]["arguments"]) == {"foo": "bar"}
