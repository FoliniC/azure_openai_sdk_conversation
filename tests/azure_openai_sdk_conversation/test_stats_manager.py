"""Tests for the statistics manager."""
import asyncio
import json
import pytest
from datetime import datetime, timezone
from custom_components.azure_openai_sdk_conversation.stats.manager import StatsManager
from custom_components.azure_openai_sdk_conversation.stats.metrics import RequestMetrics

@pytest.fixture
def stats_manager(hass, tmp_path):
    stats_file = tmp_path / "stats.jsonl"
    return StatsManager(hass, str(stats_file), aggregation_interval_minutes=1)

@pytest.mark.anyio
async def test_record_request(stats_manager):
    metrics = RequestMetrics(
        timestamp=datetime.now(timezone.utc).isoformat(),
        conversation_id="test_conv",
        execution_time_ms=100.0,
        handler="local_intent",
        original_text="hello",
        normalized_text="hello",
        success=True
    )
    await stats_manager.record_request(metrics)
    assert len(stats_manager._current_metrics) == 1

@pytest.mark.anyio
async def test_aggregate_and_persist(stats_manager, hass):
    metrics = RequestMetrics(
        timestamp=datetime.now(timezone.utc).isoformat(),
        conversation_id="test_conv",
        execution_time_ms=100.0,
        handler="llm_chat",
        original_text="hello",
        normalized_text="hello",
        success=True,
        total_tokens=10,
        prompt_tokens=5,
        completion_tokens=5,
        model="gpt-4o-mini"
    )
    await stats_manager.record_request(metrics)
    
    # Trigger aggregation
    await stats_manager._aggregate_and_persist()
    
    assert len(stats_manager._current_metrics) == 0
    assert stats_manager._stats_file.exists()
    
    with open(stats_manager._stats_file, "r") as f:
        line = f.readline()
        data = json.loads(line)
        assert data["total_requests"] == 1
        assert data["total_tokens"] == 10
        assert data["estimated_cost_usd"] > 0