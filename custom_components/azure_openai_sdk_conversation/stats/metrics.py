"""
Dataclasses for statistics metrics.

Defines the data structures for tracking request-level and aggregated statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    timestamp: str
    conversation_id: str
    execution_time_ms: float

    # Routing
    handler: str  # "local_intent" | "llm_chat" | "llm_responses"

    # User input
    original_text: str
    normalized_text: str

    # Token usage (if LLM)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # LLM specifics
    model: Optional[str] = None
    api_version: Optional[str] = None
    temperature: Optional[float] = None

    # Result
    success: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Response
    response_length: int = 0
    first_chunk_time_ms: Optional[float] = None

    # Tool calling statistics
    total_tool_calls: int = 0
    unique_tools_called: set[str] = field(default_factory=set)
    avg_tool_iterations: float = 0.0
    max_tool_iterations: int = 0
    tool_error_count: int = 0


@dataclass
class AggregatedStats:
    """Aggregated statistics over a time period."""

    period_start: str
    period_end: str

    # Request counts
    total_requests: int = 0
    local_intent_count: int = 0
    llm_chat_count: int = 0
    llm_responses_count: int = 0

    # Success/failure
    successful_requests: int = 0
    failed_requests: int = 0

    # Error breakdown
    error_types: dict[str, int] = field(default_factory=dict)

    # Performance
    avg_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    avg_first_chunk_time_ms: float = 0.0

    # Token usage
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_request: float = 0.0

    # Cost estimation (Azure OpenAI pricing)
    estimated_cost_usd: float = 0.0
