"""Unit tests for PSI calculation."""

import pytest
import pandas as pd
import numpy as np

from src.account_score.monitoring.psi import PSICalculator


class TestPSICalculator:
    """Test PSI calculation."""

    @pytest.fixture
    def baseline_scores(self):
        """Create baseline scores."""
        np.random.seed(42)
        return pd.Series(np.random.normal(loc=5.0, scale=1.5, size=1000))

    def test_calculate_identical_distributions(self, baseline_scores):
        """PSI should be ~0 for identical distributions."""
        psi = PSICalculator.calculate(baseline_scores, baseline_scores)
        assert psi < 0.05  # Should be very close to 0

    def test_calculate_shifted_distribution(self, baseline_scores):
        """PSI should increase with shifted distribution."""
        baseline_scores_copy = baseline_scores.copy()

        # Small shift
        small_shift = baseline_scores + 0.5
        psi_small = PSICalculator.calculate(baseline_scores_copy, small_shift)

        # Large shift
        large_shift = baseline_scores + 2.0
        psi_large = PSICalculator.calculate(baseline_scores_copy, large_shift)

        assert psi_small < psi_large  # Larger shift should have higher PSI
        assert psi_small < 0.25  # Small shift should be below alert threshold

    def test_calculate_different_distribution(self):
        """PSI should be high for different distributions."""
        baseline = pd.Series(np.random.normal(loc=5, scale=1, size=1000))
        different = pd.Series(np.random.normal(loc=8, scale=1, size=1000))

        psi = PSICalculator.calculate(baseline, different)
        assert psi > 0.25  # Should be above alert threshold

    def test_calculate_empty_series(self):
        """PSI should handle empty series."""
        baseline = pd.Series([1, 2, 3])
        empty = pd.Series([], dtype=float)

        psi = PSICalculator.calculate(baseline, empty)
        assert psi == 0.0

    def test_calculate_with_nulls(self):
        """PSI should handle null values."""
        baseline = pd.Series([1, 2, np.nan, 4, 5])
        current = pd.Series([1, 2, 3, np.nan, 5])

        psi = PSICalculator.calculate(baseline, current)
        assert psi >= 0  # Should not error

    def test_calculate_by_dimension(self):
        """Test PSI calculation for multiple columns."""
        baseline_df = pd.DataFrame({
            'score1': np.random.normal(5, 1.5, 100),
            'score2': np.random.normal(6, 2.0, 100),
        })

        current_df = pd.DataFrame({
            'score1': np.random.normal(5, 1.5, 100),
            'score2': np.random.normal(6.5, 2.0, 100),  # Shifted
        })

        psi_values = PSICalculator.calculate_by_dimension(
            baseline_df, current_df, ['score1', 'score2']
        )

        assert 'score1' in psi_values
        assert 'score2' in psi_values
        assert psi_values['score1'] < psi_values['score2']  # score2 shifted more

    def test_calculate_by_segment(self):
        """Test PSI calculation by segment."""
        baseline_df = pd.DataFrame({
            'score': np.random.normal(5, 1.5, 100),
            'specialty': ['Surgery'] * 50 + ['Medicine'] * 50,
        })

        current_df = pd.DataFrame({
            'score': np.random.normal(5.5, 1.5, 100),  # Shifted
            'specialty': ['Surgery'] * 50 + ['Medicine'] * 50,
        })

        psi_by_segment = PSICalculator.calculate_by_segment(
            baseline_df, current_df, 'score', 'specialty'
        )

        assert 'Surgery' in psi_by_segment
        assert 'Medicine' in psi_by_segment
        assert all(v > 0 for v in psi_by_segment.values())

    def test_interpret_psi(self):
        """Test PSI interpretation."""
        assert "No significant" in PSICalculator.interpret_psi(0.05)
        assert "Small change" in PSICalculator.interpret_psi(0.15)
        assert "Significant" in PSICalculator.interpret_psi(0.30)

    def test_alert_if_high(self):
        """Test alert thresholding."""
        should_alert, msg = PSICalculator.alert_if_high(0.30, threshold=0.25)
        assert should_alert is True
        assert "exceeds" in msg

        should_alert, msg = PSICalculator.alert_if_high(0.20, threshold=0.25)
        assert should_alert is False
        assert "acceptable" in msg

    def test_psi_bounds(self):
        """PSI should be non-negative and bounded."""
        baseline = pd.Series(np.random.uniform(0, 100, 1000))
        current = pd.Series(np.random.uniform(0, 100, 1000))

        psi = PSICalculator.calculate(baseline, current)
        assert psi >= 0
        assert psi < float('inf')
