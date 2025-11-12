"""
Advanced statistics manager for Azure OpenAI SDK Conversation.

Tracks:
- Execution time per request
- Token usage (prompt + completion)
- Local intent vs LLM routing
- Error rates and types
- API performance metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)


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
    error_types: Dict[str, int] = None

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

    def __post_init__(self):
        if self.error_types is None:
            self.error_types = {}


class StatsManager:
    """
    Manages collection, aggregation, and persistence of statistics.
    """

    def __init__(
        self,
        hass: Any,
        stats_file: str,
        aggregation_interval_minutes: int = 60,
    ) -> None:
        """
        Initialize the statistics manager.

        Args:
            hass: Home Assistant instance
            stats_file: Path to statistics JSON file
            aggregation_interval_minutes: How often to aggregate and persist stats
        """
        self._hass = hass
        self._stats_file = Path(stats_file)
        self._interval = aggregation_interval_minutes

        # In-memory buffer for current period
        self._current_metrics: list[RequestMetrics] = []
        self._period_start = datetime.now(timezone.utc)

        # Aggregation task
        self._aggregation_task: Optional[asyncio.Task] = None

        # Thread-safe lock
        self._lock = asyncio.Lock()

        # Pricing (example rates for gpt-4o-mini, adjust as needed)
        self._pricing = {
            "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
            "gpt-4o": {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
            "gpt-4": {"prompt": 30.00 / 1_000_000, "completion": 60.00 / 1_000_000},
            "o1-preview": {
                "prompt": 15.00 / 1_000_000,
                "completion": 60.00 / 1_000_000,
            },
            "o1-mini": {"prompt": 3.00 / 1_000_000, "completion": 12.00 / 1_000_000},
        }

        _LOGGER.info(
            "StatsManager initialized: file=%s, interval=%dm",
            self._stats_file,
            self._interval,
        )

    async def start(self) -> None:
        """Start the periodic aggregation task."""
        if self._aggregation_task is None:
            self._aggregation_task = asyncio.create_task(self._periodic_aggregation())
            _LOGGER.info("StatsManager: periodic aggregation started")

    async def stop(self) -> None:
        """Stop the aggregation task and flush remaining data."""
        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass
            self._aggregation_task = None

        # Flush any remaining metrics
        await self._aggregate_and_persist()
        _LOGGER.info("StatsManager: stopped and flushed")

    async def record_request(self, metrics: RequestMetrics) -> None:
        """Record metrics for a single request."""
        async with self._lock:
            self._current_metrics.append(metrics)

            # Debug log for high-level monitoring
            _LOGGER.debug(
                "Stats recorded: handler=%s, time=%.1fms, success=%s, tokens=%s",
                metrics.handler,
                metrics.execution_time_ms,
                metrics.success,
                metrics.total_tokens or "N/A",
            )

    async def _periodic_aggregation(self) -> None:
        """Periodically aggregate and persist statistics."""
        while True:
            try:
                await asyncio.sleep(self._interval * 60)
                await self._aggregate_and_persist()
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("StatsManager: aggregation error: %r", err)

    async def _aggregate_and_persist(self) -> None:
        """Aggregate current metrics and append to stats file."""
        async with self._lock:
            if not self._current_metrics:
                return

            now = datetime.now(timezone.utc)
            stats = self._aggregate(self._current_metrics, self._period_start, now)

            # Write to file
            await self._write_stats(stats)

            # Reset for next period
            self._current_metrics.clear()
            self._period_start = now

            _LOGGER.info(
                "Stats aggregated: period=%s to %s, requests=%d, local=%d, llm=%d, errors=%d",
                stats.period_start,
                stats.period_end,
                stats.total_requests,
                stats.local_intent_count,
                stats.llm_chat_count + stats.llm_responses_count,
                stats.failed_requests,
            )

    def _aggregate(
        self,
        metrics: list[RequestMetrics],
        start: datetime,
        end: datetime,
    ) -> AggregatedStats:
        """Aggregate a list of request metrics into summary statistics."""
        stats = AggregatedStats(
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            error_types={},
        )

        if not metrics:
            return stats

        stats.total_requests = len(metrics)

        exec_times = []
        first_chunk_times = []

        for m in metrics:
            # Routing
            if m.handler == "local_intent":
                stats.local_intent_count += 1
            elif m.handler == "llm_chat":
                stats.llm_chat_count += 1
            elif m.handler == "llm_responses":
                stats.llm_responses_count += 1

            # Success/failure
            if m.success:
                stats.successful_requests += 1
            else:
                stats.failed_requests += 1
                err_type = m.error_type or "unknown"
                stats.error_types[err_type] = stats.error_types.get(err_type, 0) + 1

            # Performance
            exec_times.append(m.execution_time_ms)
            if m.first_chunk_time_ms is not None:
                first_chunk_times.append(m.first_chunk_time_ms)

            # Tokens
            if m.total_tokens:
                stats.total_prompt_tokens += m.prompt_tokens or 0
                stats.total_completion_tokens += m.completion_tokens or 0
                stats.total_tokens += m.total_tokens

        # Performance stats
        if exec_times:
            stats.avg_execution_time_ms = sum(exec_times) / len(exec_times)
            stats.min_execution_time_ms = min(exec_times)
            stats.max_execution_time_ms = max(exec_times)

        if first_chunk_times:
            stats.avg_first_chunk_time_ms = sum(first_chunk_times) / len(
                first_chunk_times
            )

        # Token averages
        llm_requests = stats.llm_chat_count + stats.llm_responses_count
        if llm_requests > 0:
            stats.avg_tokens_per_request = stats.total_tokens / llm_requests

        # Cost estimation (simplified - uses first model found)
        model_for_cost = None
        for m in metrics:
            if m.model:
                model_for_cost = m.model.lower()
                break

        if model_for_cost and stats.total_tokens > 0:
            pricing = self._get_pricing(model_for_cost)
            prompt_cost = stats.total_prompt_tokens * pricing["prompt"]
            completion_cost = stats.total_completion_tokens * pricing["completion"]
            stats.estimated_cost_usd = prompt_cost + completion_cost

        # Tool calling metrics
        tool_iterations_list = []
        all_tools_called = set()

        for m in metrics:
            # Tool calls
            if m.tools_called:
                stats.total_tool_calls += len(m.tools_called)
                all_tools_called.update(m.tools_called)

            # Tool iterations
            if m.tool_iterations > 0:
                tool_iterations_list.append(m.tool_iterations)
                stats.max_tool_iterations = max(
                    stats.max_tool_iterations, m.tool_iterations
                )

            # Tool errors
            if m.tool_errors:
                stats.tool_error_count += len(m.tool_errors)

        # Store unique tools
        stats.unique_tools_called = all_tools_called

        # Average iterations
        if tool_iterations_list:
            stats.avg_tool_iterations = sum(tool_iterations_list) / len(
                tool_iterations_list
            )

        return stats

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a model (with fuzzy matching)."""
        model_lower = model.lower()

        # Exact match
        if model_lower in self._pricing:
            return self._pricing[model_lower]

        # Fuzzy match
        for key in self._pricing:
            if key in model_lower:
                return self._pricing[key]

        # Default fallback (gpt-4o-mini pricing)
        return self._pricing.get(
            "gpt-4o-mini", {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000}
        )

    async def _write_stats(self, stats: AggregatedStats) -> None:
        """Append aggregated stats to JSON lines file."""

        def _write():
            self._stats_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._stats_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(stats), ensure_ascii=False) + "\n")

        try:
            await self._hass.async_add_executor_job(_write)
        except Exception as err:
            _LOGGER.error("Failed to write stats to %s: %r", self._stats_file, err)

    async def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get a summary of statistics for the last N hours.

        Returns a dict with aggregated metrics suitable for display.
        """

        def _read() -> list[AggregatedStats]:
            if not self._stats_file.exists():
                return []

            cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            stats_list = []

            with open(self._stats_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        period_end = datetime.fromisoformat(
                            data["period_end"]
                        ).timestamp()
                        if period_end >= cutoff:
                            stats_list.append(AggregatedStats(**data))
                    except Exception:
                        continue

            return stats_list

        try:
            stats_list = await self._hass.async_add_executor_job(_read)
        except Exception as err:
            _LOGGER.error("Failed to read stats summary: %r", err)
            return {}

        if not stats_list:
            return {
                "period_hours": hours,
                "total_requests": 0,
                "message": "No data available for this period",
            }

        # Aggregate across all periods
        total_requests = sum(s.total_requests for s in stats_list)
        local_count = sum(s.local_intent_count for s in stats_list)
        llm_count = sum(s.llm_chat_count + s.llm_responses_count for s in stats_list)
        failed = sum(s.failed_requests for s in stats_list)

        total_tokens_all = sum(s.total_tokens for s in stats_list)
        total_cost = sum(s.estimated_cost_usd for s in stats_list)

        avg_exec_times = [
            s.avg_execution_time_ms for s in stats_list if s.avg_execution_time_ms > 0
        ]
        avg_exec_time = (
            sum(avg_exec_times) / len(avg_exec_times) if avg_exec_times else 0.0
        )

        # Error types aggregation
        all_errors = defaultdict(int)
        for s in stats_list:
            for err_type, count in s.error_types.items():
                all_errors[err_type] += count
        # Tool calling summary
        total_tool_calls_all = sum(s.total_tool_calls for s in stats_list)
        unique_tools_all = set()
        for s in stats_list:
            unique_tools_all.update(s.unique_tools_called)

        avg_iterations_list = [
            s.avg_tool_iterations for s in stats_list if s.avg_tool_iterations > 0
        ]
        avg_iterations = (
            sum(avg_iterations_list) / len(avg_iterations_list)
            if avg_iterations_list
            else 0.0
        )

        return {
            "period_hours": hours,
            "total_requests": total_requests,
            "local_intent_count": local_count,
            "local_intent_percentage": (local_count / total_requests * 100)
            if total_requests > 0
            else 0.0,
            "llm_count": llm_count,
            "llm_percentage": (llm_count / total_requests * 100)
            if total_requests > 0
            else 0.0,
            "failed_requests": failed,
            "error_rate_percentage": (failed / total_requests * 100)
            if total_requests > 0
            else 0.0,
            "error_types": dict(all_errors),
            "avg_execution_time_ms": round(avg_exec_time, 2),
            "total_tokens": total_tokens_all,
            "estimated_cost_usd": round(total_cost, 4),
            "total_tool_calls": total_tool_calls_all,
            "unique_tools_called": list(unique_tools_all),
            "avg_tool_iterations": round(avg_iterations, 2),
            "tool_error_count": sum(s.tool_error_count for s in stats_list),
        }
