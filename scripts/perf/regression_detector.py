"""Utilities for detecting regressions in pytest execution times.

This module provides functions to detect performance regressions by comparing
current test timings against stored baselines. When run as a CLI tool, it will
exit with code 1 if regressions exceeding the threshold are detected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def save_baseline(destination: Path, results: Dict[str, float]) -> Path:
    """Persist the baseline metrics to ``destination``."""

    destination.write_text(json.dumps(results, indent=2, sort_keys=True))
    return destination


def load_baseline(source: Path) -> Dict[str, float]:
    """Load an existing baseline file, returning an empty mapping if missing."""

    if not source.exists():
        return {}
    try:
        return json.loads(source.read_text())
    except json.JSONDecodeError:
        return {}


def detect_performance_regressions(
    baseline_file: Path, current_results: Dict[str, float]
) -> Dict[str, object]:
    """Detect regressions between baseline metrics and ``current_results``."""

    if not baseline_file.exists():
        save_baseline(baseline_file, current_results)
        return {"status": "baseline_created", "regressions": []}

    baseline = load_baseline(baseline_file)
    regressions: List[Dict[str, object]] = []
    improvements = 0

    for test_name, current_time in current_results.items():
        baseline_time = baseline.get(test_name)
        if baseline_time is None:
            continue

        if baseline_time == 0:
            continue

        change_ratio = current_time / baseline_time
        if change_ratio > 1.3:
            regressions.append(
                {
                    "test": test_name,
                    "baseline": baseline_time,
                    "current": current_time,
                    "regression_percent": ((current_time - baseline_time) / baseline_time)
                    * 100,
                }
            )
        elif change_ratio < 0.9:
            improvements += 1

    return {
        "status": "analysis_complete",
        "regressions": regressions,
        "improvement_count": improvements,
    }


def enforce_regression_threshold(
    baseline_file: Path,
    current_file: Path,
    *,
    threshold: float = 1.3,
    fail_on_regression: bool = True,
) -> int:
    """Check for regressions and optionally fail with exit code 1.

    Args:
        baseline_file: Path to JSON file with baseline timings.
        current_file: Path to JSON file with current run timings.
        threshold: Ratio above which a test is considered regressed (default 1.3 = 30%).
        fail_on_regression: If True, return exit code 1 when regressions found.

    Returns:
        Exit code: 0 if no regressions, 1 if regressions detected and fail_on_regression=True.
    """
    if not current_file.exists():
        print(f"ERROR: Current results file not found: {current_file}")
        return 1

    try:
        current_results = json.loads(current_file.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse current results: {e}")
        return 1

    # Handle nested structure from profile_marker_suites.py output
    if "test_durations" in current_results:
        current_results = current_results["test_durations"]

    result = detect_performance_regressions(baseline_file, current_results)

    print(f"Status: {result['status']}")
    print(f"Improvements: {result.get('improvement_count', 0)}")

    regressions = result.get("regressions", [])
    if regressions:
        print(f"\n{'='*60}")
        print(f"PERFORMANCE REGRESSIONS DETECTED: {len(regressions)}")
        print(f"{'='*60}")
        for reg in regressions:
            print(
                f"  - {reg['test']}: "
                f"{reg['baseline']:.3f}s -> {reg['current']:.3f}s "
                f"(+{reg['regression_percent']:.1f}%)"
            )
        print(f"{'='*60}\n")

        if fail_on_regression:
            print("CI FAILURE: Performance regression threshold exceeded.")
            return 1

    print("No performance regressions detected.")
    return 0


def main() -> int:
    """CLI entrypoint for regression detection."""
    parser = argparse.ArgumentParser(
        description="Detect performance regressions in pytest execution times."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("perf_metrics/pytest_marker_baselines.json"),
        help="Path to baseline JSON file (default: perf_metrics/pytest_marker_baselines.json)",
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to current run's JSON file with timing data",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.3,
        help="Regression threshold ratio (default: 1.3 = 30%% slower)",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print warnings but don't fail on regressions",
    )

    args = parser.parse_args()

    return enforce_regression_threshold(
        args.baseline,
        args.current,
        threshold=args.threshold,
        fail_on_regression=not args.warn_only,
    )


if __name__ == "__main__":
    sys.exit(main())
