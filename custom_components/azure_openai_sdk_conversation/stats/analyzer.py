#!/usr/bin/env python3
"""
Advanced statistics analyzer for Azure OpenAI Conversation component.

Usage:
    python analyze_stats.py [options]

Options:
    --file PATH          Stats file path (default: .storage/azure_openai_stats_aggregated.json)
    --hours HOURS        Analysis period in hours (default: 24)
    --format FORMAT      Output format: text|json|csv (default: text)
    --export PATH        Export results to file
    --chart              Generate charts (requires matplotlib)
    --compare BASELINE   Compare with baseline file
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


class StatsAnalyzer:
    """Analyzer for aggregated statistics."""

    def __init__(self, stats_file: Path):
        self.stats_file = stats_file
        self.stats: List[Dict[str, Any]] = []
        self.load_stats()

    def load_stats(self) -> None:
        """Load statistics from JSON lines file."""
        if not self.stats_file.exists():
            raise FileNotFoundError(f"Stats file not found: {self.stats_file}")

        with open(self.stats_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    self.stats.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not self.stats:
            raise ValueError("No valid statistics found in file")

        print(f"Loaded {len(self.stats)} aggregated periods", file=sys.stderr)

    def filter_by_period(self, hours: int) -> List[Dict[str, Any]]:
        """Filter statistics by time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_ts = cutoff.timestamp()

        filtered = []
        for stat in self.stats:
            try:
                period_end = datetime.fromisoformat(stat["period_end"])
                if period_end.timestamp() >= cutoff_ts:
                    filtered.append(stat)
            except (KeyError, ValueError):
                continue

        return filtered

    def analyze(self, hours: int = 24) -> Dict[str, Any]:
        """Perform comprehensive analysis."""
        filtered = self.filter_by_period(hours)

        if not filtered:
            return {"period_hours": hours, "error": "No data available for this period"}

        analysis = {
            "period_hours": hours,
            "period_start": filtered[0]["period_start"],
            "period_end": filtered[-1]["period_end"],
            "summary": self._summarize(filtered),
            "performance": self._analyze_performance(filtered),
            "costs": self._analyze_costs(filtered),
            "routing": self._analyze_routing(filtered),
            "errors": self._analyze_errors(filtered),
            "recommendations": [],
        }

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)

        return analysis

    def _summarize(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        total_requests = sum(s["total_requests"] for s in stats)
        successful = sum(s["successful_requests"] for s in stats)
        failed = sum(s["failed_requests"] for s in stats)

        return {
            "total_requests": total_requests,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": (successful / total_requests * 100)
            if total_requests > 0
            else 0.0,
            "periods_analyzed": len(stats),
        }

    def _analyze_performance(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance metrics."""
        exec_times = []
        first_chunk_times = []

        for s in stats:
            if s["avg_execution_time_ms"] > 0:
                exec_times.append(s["avg_execution_time_ms"])
            if s.get("avg_first_chunk_time_ms", 0) > 0:
                first_chunk_times.append(s["avg_first_chunk_time_ms"])

        perf = {
            "avg_execution_time_ms": sum(exec_times) / len(exec_times)
            if exec_times
            else 0.0,
            "min_execution_time_ms": min(exec_times) if exec_times else 0.0,
            "max_execution_time_ms": max(exec_times) if exec_times else 0.0,
        }

        if first_chunk_times:
            perf["avg_first_chunk_time_ms"] = sum(first_chunk_times) / len(
                first_chunk_times
            )

        # Calculate percentiles
        if exec_times:
            sorted_times = sorted(exec_times)
            perf["p50_execution_time_ms"] = sorted_times[len(sorted_times) // 2]
            perf["p95_execution_time_ms"] = sorted_times[int(len(sorted_times) * 0.95)]
            perf["p99_execution_time_ms"] = sorted_times[int(len(sorted_times) * 0.99)]

        return perf

    def _analyze_costs(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze costs and token usage."""
        total_tokens = sum(s["total_tokens"] for s in stats)
        total_cost = sum(s["estimated_cost_usd"] for s in stats)
        llm_requests = sum(
            s["llm_chat_count"] + s["llm_responses_count"] for s in stats
        )

        return {
            "total_prompt_tokens": sum(s["total_prompt_tokens"] for s in stats),
            "total_completion_tokens": sum(s["total_completion_tokens"] for s in stats),
            "total_tokens": total_tokens,
            "avg_tokens_per_request": total_tokens / llm_requests
            if llm_requests > 0
            else 0.0,
            "total_cost_usd": total_cost,
            "avg_cost_per_request_usd": total_cost / llm_requests
            if llm_requests > 0
            else 0.0,
            "projected_monthly_cost_usd": (total_cost / len(stats))
            * 24
            * 30,  # Rough estimate
        }

    def _analyze_routing(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze request routing distribution."""
        total = sum(s["total_requests"] for s in stats)
        local = sum(s["local_intent_count"] for s in stats)
        chat = sum(s["llm_chat_count"] for s in stats)
        responses = sum(s["llm_responses_count"] for s in stats)

        return {
            "total_requests": total,
            "local_intent_count": local,
            "local_intent_percentage": (local / total * 100) if total > 0 else 0.0,
            "llm_chat_count": chat,
            "llm_chat_percentage": (chat / total * 100) if total > 0 else 0.0,
            "llm_responses_count": responses,
            "llm_responses_percentage": (responses / total * 100) if total > 0 else 0.0,
            "llm_total": chat + responses,
            "llm_percentage": ((chat + responses) / total * 100) if total > 0 else 0.0,
        }

    def _analyze_errors(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze error patterns."""
        total_errors = sum(s["failed_requests"] for s in stats)
        total_requests = sum(s["total_requests"] for s in stats)

        # Aggregate error types
        error_breakdown = defaultdict(int)
        for s in stats:
            for err_type, count in s.get("error_types", {}).items():
                error_breakdown[err_type] += count

        return {
            "total_errors": total_errors,
            "error_rate_percentage": (total_errors / total_requests * 100)
            if total_requests > 0
            else 0.0,
            "error_breakdown": dict(error_breakdown),
            "most_common_error": max(error_breakdown.items(), key=lambda x: x[1])[0]
            if error_breakdown
            else None,
        }

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Performance recommendations
        perf = analysis["performance"]
        if perf.get("avg_execution_time_ms", 0) > 3000:
            recommendations.append(
                "?? PERFORMANCE: Average execution time > 3s. "
                "Consider reducing max_tokens or switching to a faster model (e.g., gpt-4o-mini)."
            )

        if perf.get("avg_first_chunk_time_ms", 0) > 2000:
            recommendations.append(
                "?? UX: First chunk latency > 2s. "
                "Enable early_wait or optimize system prompt for faster initial response."
            )

        # Cost recommendations
        costs = analysis["costs"]
        if costs["projected_monthly_cost_usd"] > 100:
            recommendations.append(
                f"?? COST: Projected monthly cost ${costs['projected_monthly_cost_usd']:.2f}. "
                f"Consider optimizing token usage or increasing local intent handling."
            )

        if costs.get("avg_tokens_per_request", 0) > 800:
            recommendations.append(
                "?? TOKEN USAGE: High average tokens per request. "
                "Review system prompt length and consider MCP delta updates."
            )

        # Routing recommendations
        routing = analysis["routing"]
        if routing["local_intent_percentage"] < 20:
            recommendations.append(
                f"?? ROUTING: Only {routing['local_intent_percentage']:.1f}% handled locally. "
                f"Expand vocabulary/synonyms to increase local intent coverage."
            )

        # Error recommendations
        errors = analysis["errors"]
        if errors["error_rate_percentage"] > 5:
            recommendations.append(
                f"? ERRORS: Error rate {errors['error_rate_percentage']:.1f}% exceeds 5% threshold. "
                f"Most common: {errors.get('most_common_error', 'Unknown')}. Investigate root cause."
            )

        # Success message if everything looks good
        if not recommendations:
            recommendations.append(
                "? All metrics look healthy! No major issues detected."
            )

        return recommendations

    def format_output(self, analysis: Dict[str, Any], format: str = "text") -> str:
        """Format analysis results."""
        if format == "json":
            return json.dumps(analysis, indent=2, ensure_ascii=False)

        elif format == "csv":
            return self._format_csv(analysis)

        else:  # text
            return self._format_text(analysis)

    def _format_text(self, analysis: Dict[str, Any]) -> str:
        """Format as human-readable text report."""
        lines = [
            "=" * 80,
            "Azure OpenAI Conversation - Statistics Report",
            "=" * 80,
            f"\nPeriod: Last {analysis['period_hours']} hours",
            f"From: {analysis['period_start']}",
            f"To:   {analysis['period_end']}",
            "\n" + "=" * 80,
            "\n?? SUMMARY",
            "-" * 80,
        ]

        summary = analysis["summary"]
        lines.extend(
            [
                f"Total Requests:      {summary['total_requests']:,}",
                f"Successful:          {summary['successful_requests']:,} ({summary['success_rate']:.1f}%)",
                f"Failed:              {summary['failed_requests']:,}",
                f"Periods Analyzed:    {summary['periods_analyzed']}",
            ]
        )

        lines.extend(
            [
                "\n" + "=" * 80,
                "\n? PERFORMANCE",
                "-" * 80,
            ]
        )

        perf = analysis["performance"]
        lines.extend(
            [
                f"Avg Execution Time:  {perf['avg_execution_time_ms']:.1f}ms",
                f"Min Execution Time:  {perf['min_execution_time_ms']:.1f}ms",
                f"Max Execution Time:  {perf['max_execution_time_ms']:.1f}ms",
            ]
        )

        if "p95_execution_time_ms" in perf:
            lines.extend(
                [
                    f"P50 (Median):        {perf['p50_execution_time_ms']:.1f}ms",
                    f"P95:                 {perf['p95_execution_time_ms']:.1f}ms",
                    f"P99:                 {perf['p99_execution_time_ms']:.1f}ms",
                ]
            )

        if "avg_first_chunk_time_ms" in perf:
            lines.append(
                f"Avg First Chunk:     {perf['avg_first_chunk_time_ms']:.1f}ms"
            )

        lines.extend(
            [
                "\n" + "=" * 80,
                "\n?? COSTS & TOKENS",
                "-" * 80,
            ]
        )

        costs = analysis["costs"]
        lines.extend(
            [
                f"Total Tokens:         {costs['total_tokens']:,}",
                f"  Prompt:             {costs['total_prompt_tokens']:,}",
                f"  Completion:         {costs['total_completion_tokens']:,}",
                f"Avg Tokens/Request:   {costs['avg_tokens_per_request']:.1f}",
                f"Total Cost:           ${costs['total_cost_usd']:.4f}",
                f"Avg Cost/Request:     ${costs['avg_cost_per_request_usd']:.6f}",
                f"Projected Monthly:    ${costs['projected_monthly_cost_usd']:.2f}",
            ]
        )

        lines.extend(
            [
                "\n" + "=" * 80,
                "\n?? ROUTING",
                "-" * 80,
            ]
        )

        routing = analysis["routing"]
        lines.extend(
            [
                f"Local Intent:         {routing['local_intent_count']:,} ({routing['local_intent_percentage']:.1f}%)",
                f"LLM Chat:             {routing['llm_chat_count']:,} ({routing['llm_chat_percentage']:.1f}%)",
                f"LLM Responses:        {routing['llm_responses_count']:,} ({routing['llm_responses_percentage']:.1f}%)",
                f"Total LLM:            {routing['llm_total']:,} ({routing['llm_percentage']:.1f}%)",
            ]
        )

        lines.extend(
            [
                "\n" + "=" * 80,
                "\n? ERRORS",
                "-" * 80,
            ]
        )

        errors = analysis["errors"]
        lines.extend(
            [
                f"Total Errors:         {errors['total_errors']:,}",
                f"Error Rate:           {errors['error_rate_percentage']:.2f}%",
            ]
        )

        if errors.get("error_breakdown"):
            lines.append("\nError Breakdown:")
            for err_type, count in sorted(
                errors["error_breakdown"].items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {err_type:30} {count:,}")

        lines.extend(
            [
                "\n" + "=" * 80,
                "\n?? RECOMMENDATIONS",
                "-" * 80,
            ]
        )

        for rec in analysis["recommendations"]:
            lines.append(f"\n{rec}")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)

    def _format_csv(self, analysis: Dict[str, Any]) -> str:
        """Format as CSV."""
        rows = [
            "metric,value,unit",
            f"period_hours,{analysis['period_hours']},hours",
            f"total_requests,{analysis['summary']['total_requests']},count",
            f"success_rate,{analysis['summary']['success_rate']:.2f},%",
            f"avg_execution_time,{analysis['performance']['avg_execution_time_ms']:.1f},ms",
            f"total_tokens,{analysis['costs']['total_tokens']},tokens",
            f"total_cost,{analysis['costs']['total_cost_usd']:.4f},usd",
            f"local_intent_percentage,{analysis['routing']['local_intent_percentage']:.1f},%",
            f"error_rate,{analysis['errors']['error_rate_percentage']:.2f},%",
        ]
        return "\n".join(rows)

    def compare_with_baseline(
        self, baseline_file: Path, hours: int = 24
    ) -> Dict[str, Any]:
        """Compare current stats with a baseline."""
        baseline_analyzer = StatsAnalyzer(baseline_file)

        current = self.analyze(hours)
        baseline = baseline_analyzer.analyze(hours)

        comparison = {
            "current": current,
            "baseline": baseline,
            "delta": {},
        }

        # Calculate deltas
        for metric in [
            "avg_execution_time_ms",
            "total_cost_usd",
            "error_rate_percentage",
        ]:
            sections = {
                "avg_execution_time_ms": "performance",
                "total_cost_usd": "costs",
                "error_rate_percentage": "errors",
            }
            section = sections[metric]

            curr_val = current[section].get(metric, 0)
            base_val = baseline[section].get(metric, 0)
            delta = curr_val - base_val
            delta_pct = (delta / base_val * 100) if base_val > 0 else 0

            comparison["delta"][metric] = {
                "absolute": delta,
                "percentage": delta_pct,
                "improved": delta < 0
                if "error" in metric or "time" in metric or "cost" in metric
                else delta > 0,
            }

        return comparison


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Azure OpenAI Conversation statistics"
    )
    parser.add_argument(
        "--file",
        default=".storage/azure_openai_stats_aggregated.json",
        help="Stats file path",
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Analysis period in hours"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--export", help="Export results to file")
    parser.add_argument("--compare", help="Compare with baseline file")

    args = parser.parse_args()

    try:
        analyzer = StatsAnalyzer(Path(args.file))

        if args.compare:
            result = analyzer.compare_with_baseline(Path(args.compare), args.hours)
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            analysis = analyzer.analyze(args.hours)
            output = analyzer.format_output(analysis, args.format)

        if args.export:
            with open(args.export, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Results exported to {args.export}", file=sys.stderr)
        else:
            print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
