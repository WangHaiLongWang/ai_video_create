"""Benchmark reporter — collects results and generates a Markdown report.

Usage from tests:
    from backend.tests.performance.benchmark_reporter import BenchmarkCollector

    collector = BenchmarkCollector()
    collector.record("compiler.linear_100", summary_dict)
    collector.record("scheduler.throughput_100", summary_dict)
    collector.save_report("reports/performance-benchmark.md")

Can also be used as a lightweight pytest plugin if desired; however the
primary interface is the ``BenchmarkCollector`` class that test code
calls explicitly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    """Single benchmark result entry."""
    name: str
    category: str
    summary: dict[str, Any]
    assertions: list[str] = field(default_factory=list)
    passed: bool = True
    timestamp: str = ""


class BenchmarkCollector:
    """Collect benchmark results and generate a formatted Markdown report."""

    def __init__(self) -> None:
        self.results: list[BenchmarkResult] = []
        self._now = datetime.now(timezone.utc).isoformat()

    def record(
        self,
        name: str,
        summary: dict[str, Any],
        *,
        category: str = "general",
        assertions: list[str] | None = None,
        passed: bool = True,
    ) -> None:
        """Record a single benchmark result.

        Args:
            name: Benchmark identifier (e.g. ``compiler.linear_100``).
            summary: Timing / memory statistics dict.
            category: Grouping label (compiler, scheduler, api, worker, memory).
            assertions: Human-readable assertion descriptions.
            passed: Whether the benchmark assertions passed.
        """
        self.results.append(
            BenchmarkResult(
                name=name,
                category=category,
                summary=summary,
                assertions=assertions or [],
                passed=passed,
                timestamp=self._now,
            )
        )

    # ------------------------------------------------------------------
    #  Report generation
    # ------------------------------------------------------------------

    def save_report(self, path: str | Path) -> Path:
        """Generate and save the Markdown report.

        Returns the resolved ``Path`` of the written file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("# Performance Benchmark Report")
        lines.append("")
        lines.append(f"**Generated:** {self._now}")
        lines.append("")

        # Overview table
        lines.append("## Overview")
        lines.append("")
        lines.append("| Benchmark | Category | Avg (ms) | P95 (ms) | P99 (ms) | Passed |")
        lines.append("|-----------|----------|----------|----------|----------|--------|")
        for r in self.results:
            avg_ms = r.summary.get("avg_s", 0) * 1000
            p95_ms = r.summary.get("p95_s", 0) * 1000
            p99_ms = r.summary.get("p99_s", 0) * 1000
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.name} | {r.category} | {avg_ms:.2f} | {p95_ms:.2f} | {p99_ms:.2f} | {status} |"
            )
        lines.append("")

        # Detailed sections
        categories: dict[str, list[BenchmarkResult]] = {}
        for r in self.results:
            categories.setdefault(r.category, []).append(r)

        for cat, items in categories.items():
            lines.append(f"## {cat.title()}")
            lines.append("")
            for r in items:
                lines.append(f"### {r.name}")
                lines.append("")
                # Summary table
                lines.append("| Metric | Value |")
                lines.append("|--------|-------|")
                for key, val in r.summary.items():
                    if key.endswith("_s"):
                        display_key = key.replace("_s", " (ms)")
                        display_val = f"{val * 1000:.2f}"
                    elif key.endswith("_bytes"):
                        display_key = key.replace("_bytes", " (MB)")
                        display_val = f"{val / (1024 * 1024):.2f}"
                    elif key.endswith("_mb"):
                        display_key = key
                        display_val = f"{val:.2f}"
                    else:
                        display_key = key
                        display_val = str(val)
                    lines.append(f"| {display_key} | {display_val} |")
                lines.append("")

                if r.assertions:
                    lines.append("**Assertions:**")
                    for a in r.assertions:
                        status_mark = "PASS" if r.passed else "FAIL"
                        lines.append(f"- [{status_mark}] {a}")
                    lines.append("")

        # Summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total benchmarks: **{total}**")
        lines.append(f"- Passed: **{passed}**")
        lines.append(f"- Failed: **{total - passed}**")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path.resolve()

    def save_json(self, path: str | Path) -> Path:
        """Save raw results as JSON for programmatic consumption."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated": self._now,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "summary": r.summary,
                    "assertions": r.assertions,
                    "passed": r.passed,
                    "timestamp": r.timestamp,
                }
                for r in self.results
            ],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path.resolve()


# ---------------------------------------------------------------------------
# Singleton collector (used across tests in a session)
# ---------------------------------------------------------------------------

_collector: BenchmarkCollector | None = None


def get_collector() -> BenchmarkCollector:
    """Return the session-level BenchmarkCollector singleton."""
    global _collector
    if _collector is None:
        _collector = BenchmarkCollector()
    return _collector


def reset_collector() -> None:
    """Reset the singleton (for test isolation)."""
    global _collector
    _collector = None
