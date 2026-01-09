"""Tests for the statistics analyzer."""

import json

import pytest

from custom_components.azure_openai_sdk_conversation.stats.analyzer import StatsAnalyzer


@pytest.fixture
def stats_file(tmp_path):
    f = tmp_path / "stats.jsonl"
    data = [
        {
            "period_start": "2025-01-01T00:00:00+00:00",
            "period_end": "2025-01-01T01:00:00+00:00",
            "total_requests": 10,
            "successful_requests": 9,
            "failed_requests": 1,
            "avg_execution_time_ms": 500.0,
            "total_tokens": 1000,
            "total_prompt_tokens": 600,
            "total_completion_tokens": 400,
            "estimated_cost_usd": 0.01,
            "llm_chat_count": 5,
            "llm_responses_count": 3,
            "local_intent_count": 2,
            "error_types": {"TimeoutError": 1},
        },
        {
            "period_start": "2026-01-07T10:00:00+00:00",
            "period_end": "2026-01-07T11:00:00+00:00",
            "total_requests": 20,
            "successful_requests": 20,
            "failed_requests": 0,
            "avg_execution_time_ms": 400.0,
            "total_tokens": 2000,
            "total_prompt_tokens": 1200,
            "total_completion_tokens": 800,
            "estimated_cost_usd": 0.02,
            "llm_chat_count": 10,
            "llm_responses_count": 5,
            "local_intent_count": 5,
            "error_types": {},
        },
    ]
    with open(f, "w") as f_out:
        for entry in data:
            f_out.write(json.dumps(entry) + "\n")
    return f


def test_analyzer_load(stats_file):
    analyzer = StatsAnalyzer(stats_file)
    assert len(analyzer.stats) == 2


def test_analyzer_analyze(stats_file):
    analyzer = StatsAnalyzer(stats_file)
    # Use a large number of hours to include all test data
    analysis = analyzer.analyze(hours=100000)

    assert "summary" in analysis
    assert analysis["summary"]["total_requests"] == 30
    assert analysis["summary"]["successful_requests"] == 29
    assert analysis["costs"]["total_tokens"] == 3000
    assert analysis["routing"]["local_intent_count"] == 7


def test_analyzer_format_output(stats_file):
    analyzer = StatsAnalyzer(stats_file)
    analysis = analyzer.analyze(hours=100000)

    text_out = analyzer.format_output(analysis, format="text")
    assert "SUMMARY" in text_out
    assert "30" in text_out

    json_out = analyzer.format_output(analysis, format="json")
    data = json.loads(json_out)
    assert data["summary"]["total_requests"] == 30

    csv_out = analyzer.format_output(analysis, format="csv")
    assert "total_requests,30,count" in csv_out


def test_analyzer_compare(stats_file, tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    with open(baseline, "w") as f:
        f.write(
            json.dumps(
                {
                    "period_start": "2025-01-01T00:00:00+00:00",
                    "period_end": "2025-01-01T01:00:00+00:00",
                    "total_requests": 10,
                    "successful_requests": 10,
                    "failed_requests": 0,
                    "avg_execution_time_ms": 300.0,
                    "total_tokens": 500,
                    "total_prompt_tokens": 300,
                    "total_completion_tokens": 200,
                    "estimated_cost_usd": 0.005,
                    "llm_chat_count": 5,
                    "llm_responses_count": 5,
                    "local_intent_count": 0,
                    "error_types": {},
                }
            )
            + "\n"
        )

    analyzer = StatsAnalyzer(stats_file)
    comparison = analyzer.compare_with_baseline(baseline, hours=100000)

    assert "delta" in comparison
    assert "avg_execution_time_ms" in comparison["delta"]
