"""Detailed unit tests for TrendDiscoveryEngine logic."""

from datetime import UTC, datetime, timedelta

import pytest

from theo.domain.discoveries.models import CorpusSnapshotSummary
from theo.domain.discoveries.trend_engine import TrendDiscoveryEngine


class TestTrendEngineDetails:
    """Verify detailed logic of TrendDiscoveryEngine."""

    def test_format_timeframe(self):
        engine = TrendDiscoveryEngine()

        # Same day
        d1 = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        d2 = datetime(2023, 1, 1, 15, 0, tzinfo=UTC)
        assert engine._format_timeframe(d1, d2) == "01 Jan 2023"

        # Same month, same year
        d3 = datetime(2023, 1, 31, tzinfo=UTC)
        assert engine._format_timeframe(d1, d3) == "01 Jan – 31 Jan 2023"

        # Different month, same year
        d4 = datetime(2023, 2, 1, tzinfo=UTC)
        assert engine._format_timeframe(d1, d4) == "Jan 2023 – Feb 2023"

        # Different year
        d5 = datetime(2024, 1, 1, tzinfo=UTC)
        assert engine._format_timeframe(d1, d5) == "Jan 2023 – Jan 2024"

    def test_coerce_float_handles_edge_cases(self):
        engine = TrendDiscoveryEngine()

        assert engine._coerce_float(10) == 10.0
        assert engine._coerce_float("10.5") == 10.5
        assert engine._coerce_float(None) == 0.0
        assert engine._coerce_float("invalid") == 0.0
        assert engine._coerce_float(float("inf")) == 0.0
        assert engine._coerce_float(float("-inf")) == 0.0
        assert engine._coerce_float(float("nan")) == 0.0
        assert engine._coerce_float(-5.0) == 0.0 # Should be max(0, x)

    def test_detect_emerging_topic(self):
        """Topic appears only in the last snapshot."""
        engine = TrendDiscoveryEngine(min_percent_change=1.0)
        dates = [datetime(2023, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)]

        snapshots = [
            CorpusSnapshotSummary(dates[0], 10, {}, {}, {"topic_distribution": {"new_topic": 0}}),
            CorpusSnapshotSummary(dates[1], 10, {}, {}, {"topic_distribution": {"new_topic": 0}}),
            CorpusSnapshotSummary(dates[2], 10, {}, {}, {"topic_distribution": {"new_topic": 5}}),
        ]

        trends = engine.detect(snapshots)
        assert len(trends) == 1
        assert trends[0].metadata["trendData"]["topic"] == "new_topic"
        assert trends[0].metadata["trendData"]["change"] > 0
        assert trends[0].metadata["trendData"]["direction"] == "up"

    def test_detect_ignores_insufficient_data(self):
        """Topic with only 1 data point (and not emerging at the very end effectively)."""
        engine = TrendDiscoveryEngine()
        dates = [datetime(2023, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)]

        snapshots = [
            CorpusSnapshotSummary(dates[0], 10, {}, {}, {"topic_distribution": {"flash_pan": 5}}),
            CorpusSnapshotSummary(dates[1], 10, {}, {}, {"topic_distribution": {"flash_pan": 0}}),
            CorpusSnapshotSummary(dates[2], 10, {}, {}, {"topic_distribution": {"flash_pan": 0}}),
        ]

        trends = engine.detect(snapshots)
        assert len(trends) == 0

    def test_extract_distribution_priority(self):
        """Verify priority order of metadata fields."""
        engine = TrendDiscoveryEngine()
        date = datetime(2023, 1, 1, tzinfo=UTC)

        # Priority: topic_distribution > topic_counts > topic_frequencies
        snap = CorpusSnapshotSummary(
            snapshot_date=date,
            document_count=10,
            metadata={
                "topic_distribution": {"A": 10},
                "topic_counts": {"B": 20},
            }
        )
        dist, _ = engine._extract_distribution(snap)
        assert "a" in dist
        assert "b" not in dist

        # Fallback to counts
        snap2 = CorpusSnapshotSummary(
            snapshot_date=date,
            document_count=10,
            metadata={
                "topic_counts": {"B": 20},
            }
        )
        dist2, _ = engine._extract_distribution(snap2)
        assert "b" in dist2

    def test_extract_distribution_fallback_to_dominant_themes(self):
        """Verify fallback to dominant_themes top_topics."""
        engine = TrendDiscoveryEngine()
        date = datetime(2023, 1, 1, tzinfo=UTC)

        snap = CorpusSnapshotSummary(
            snapshot_date=date,
            document_count=10,
            dominant_themes={"top_topics": ["ThemeA", "ThemeB"]},
            metadata={}
        )
        dist, _ = engine._extract_distribution(snap)
        assert "themea" in dist
        assert "themeb" in dist
        assert dist["themea"] == 0.5
