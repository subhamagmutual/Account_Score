"""Unit tests for score monitoring."""

import pytest
import pandas as pd
import numpy as np
import json
import tempfile
from pathlib import Path

from src.account_score.monitoring import ScoreMonitor, DistributionMetrics


class TestDistributionMetrics:
    """Test DistributionMetrics dataclass."""

    def test_creation(self):
        """Test creating metrics."""
        m = DistributionMetrics(
            mean=5.0, median=5.0, std=1.5, min=1.0, max=10.0,
            p25=4.0, p50=5.0, p75=6.0, p90=8.0, p95=9.0,
            gini=0.15, count=1000, null_count=0
        )
        assert m.mean == 5.0
        assert m.gini == 0.15
        assert m.count == 1000

    def test_to_dict(self):
        """Test conversion to dict."""
        m = DistributionMetrics(
            mean=5.0, median=5.0, std=1.5, min=1.0, max=10.0,
            p25=4.0, p50=5.0, p75=6.0, p90=8.0, p95=9.0,
            gini=0.15, count=1000, null_count=0
        )
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d['mean'] == 5.0

    def test_from_dict(self):
        """Test creation from dict."""
        d = {
            'mean': 5.0, 'median': 5.0, 'std': 1.5, 'min': 1.0, 'max': 10.0,
            'p25': 4.0, 'p50': 5.0, 'p75': 6.0, 'p90': 8.0, 'p95': 9.0,
            'gini': 0.15, 'count': 1000, 'null_count': 0
        }
        m = DistributionMetrics.from_dict(d)
        assert m.mean == 5.0


class TestScoreMonitor:
    """Test ScoreMonitor class."""

    @pytest.fixture
    def normal_scores(self):
        """Generate normally distributed scores."""
        np.random.seed(42)
        return pd.Series(np.random.normal(loc=5.0, scale=1.5, size=1000))

    @pytest.fixture
    def monitor(self):
        """Create monitor instance."""
        return ScoreMonitor(alert_threshold=0.05)

    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.alert_threshold == 0.05
        assert monitor.baseline is None
        assert len(monitor.history) == 0

    def test_calculate_metrics(self, monitor, normal_scores):
        """Test metric calculation."""
        metrics = monitor.calculate_metrics(normal_scores)

        assert isinstance(metrics, DistributionMetrics)
        assert 4.5 < metrics.mean < 5.5  # Should be around 5
        assert metrics.count == 1000
        assert metrics.null_count == 0
        assert metrics.gini > 0  # Should be positive

    def test_gini_calculation(self, monitor):
        """Test Gini coefficient calculation."""
        # Perfect equality: all same value
        equal_scores = pd.Series([5.0] * 100)
        metrics = monitor.calculate_metrics(equal_scores)
        assert metrics.gini == 0.0

        # With variance: should be positive
        varied_scores = pd.Series(np.arange(1, 11) * 10)
        metrics = monitor.calculate_metrics(varied_scores)
        assert metrics.gini > 0

    def test_analyze_dataframe(self, monitor):
        """Test analyzing multiple columns."""
        df = pd.DataFrame({
            'score1': np.random.normal(5, 1.5, 100),
            'score2': np.random.normal(6, 2.0, 100),
            'other': np.random.normal(50, 10, 100),
        })

        metrics = monitor.analyze_dataframe(df, ['score1', 'score2'])

        assert 'score1' in metrics
        assert 'score2' in metrics
        assert 'other' not in metrics
        assert metrics['score1'].count == 100

    def test_baseline_operations(self, monitor, normal_scores):
        """Test setting and loading baseline."""
        metrics = monitor.calculate_metrics(normal_scores)
        baseline = {'scores': metrics}

        monitor.set_baseline(baseline)
        assert monitor.baseline is not None
        assert 'scores' in monitor.baseline

    def test_baseline_save_load(self, monitor, normal_scores):
        """Test saving and loading baseline from file."""
        metrics = monitor.calculate_metrics(normal_scores)
        baseline = {'scores': metrics}
        monitor.set_baseline(baseline)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'baseline.json'

            # Save
            monitor.save_baseline(str(filepath))
            assert filepath.exists()

            # Load
            monitor2 = ScoreMonitor()
            monitor2.load_baseline(str(filepath))
            assert monitor2.baseline is not None
            assert 'scores' in monitor2.baseline

    def test_compare_to_baseline_no_change(self, monitor, normal_scores):
        """Test comparison when no change."""
        baseline_metrics = monitor.calculate_metrics(normal_scores)
        monitor.set_baseline({'scores': baseline_metrics})

        current_metrics = monitor.calculate_metrics(normal_scores)
        comparison = monitor.compare_to_baseline({'scores': current_metrics})

        assert comparison['total_alerts'] == 0
        assert len(comparison['alerts']) == 0

    def test_compare_to_baseline_with_shift(self, monitor, normal_scores):
        """Test comparison when distribution shifts."""
        baseline_metrics = monitor.calculate_metrics(normal_scores)
        monitor.set_baseline({'scores': baseline_metrics})

        # Create shifted distribution
        shifted_scores = normal_scores + 2.0  # Shift up by 2
        current_metrics = monitor.calculate_metrics(shifted_scores)
        comparison = monitor.compare_to_baseline({'scores': current_metrics})

        # Should alert on mean change
        assert comparison['total_alerts'] > 0
        assert any('mean' in a['metric'] for a in comparison['alerts'])

    def test_history_tracking(self, monitor, normal_scores):
        """Test tracking history over time."""
        metrics1 = monitor.calculate_metrics(normal_scores)
        monitor.add_to_history('2026-01-01', {'scores': metrics1})

        metrics2 = monitor.calculate_metrics(normal_scores * 1.1)
        monitor.add_to_history('2026-01-02', {'scores': metrics2})

        assert len(monitor.history) == 2
        assert monitor.history[0]['timestamp'] == '2026-01-01'

    def test_null_handling(self, monitor):
        """Test handling of null values."""
        scores_with_nulls = pd.Series([1, 2, np.nan, 4, 5, np.nan, 7, 8, 9, 10])
        metrics = monitor.calculate_metrics(scores_with_nulls)

        assert metrics.count == 8  # Non-null count
        assert metrics.null_count == 2
        assert not np.isnan(metrics.mean)

    def test_pct_change_calculation(self):
        """Test percentage change calculation."""
        assert ScoreMonitor._pct_change(5.0, 5.5) == pytest.approx(0.10)
        assert ScoreMonitor._pct_change(5.0, 4.5) == pytest.approx(-0.10)
        assert ScoreMonitor._pct_change(0.0, 1.0) == 0.0  # Avoid division by zero
