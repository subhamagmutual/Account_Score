"""Unit tests for binning module (BinFitter and BinApplier).

Tests cover:
- Quantile binning
- Mean-anchored binning
- Reciprocal binning
- Empty/sparse data handling
- Vectorized application
"""

import pytest
import pandas as pd
import numpy as np
from src.account_score.binner import BinFitter, BinApplier


class TestBinFitter:
    """Test BinFitter class for threshold computation."""
    
    def test_quantile_binning_basic(self):
        """Test quantile-based binning produces expected structure."""
        data = pd.Series(np.linspace(0, 100, 1000))
        fitter = BinFitter(n_bins=10)
        
        bins = fitter._fit_quantile(data, higher_is_worse=True, name="test")
        
        # Should have 10 bins + 1 default
        assert len(bins) == 11
        assert bins[-1]["lower_operator"] == "default"
        assert bins[0]["score"] == 1
        assert bins[-2]["score"] == 10
    
    def test_quantile_binning_inverted(self):
        """Test inverted (higher is better) binning."""
        data = pd.Series(np.linspace(0, 100, 1000))
        fitter = BinFitter(n_bins=10)
        
        bins = fitter._fit_quantile(data, higher_is_worse=False, name="test")
        
        # With inversion, boundaries should be flipped
        assert len(bins) >= 2
        # First boundary should be higher when inverted
        if len(bins) > 2:
            first_bounds = bins[0]
            second_bounds = bins[1]
            # In inverted mode, lower values get higher scores (worse)
            assert first_bounds.get("score", 0) > second_bounds.get("score", 0)
    
    def test_empty_data_handling(self):
        """Test handling of empty/all-NA data."""
        data = pd.Series([np.nan, np.nan, np.nan])
        fitter = BinFitter()
        
        bins = fitter.fit_variable(data, method="quantile", name="empty")
        
        # Should return default bin for empty data
        assert len(bins) >= 1
        assert bins[0]["lower_operator"] == "default"
        assert bins[0]["score"] == -1
    
    def test_constant_data(self):
        """Test handling of constant (all same value) data."""
        data = pd.Series([42.0] * 100)
        fitter = BinFitter()
        
        bins = fitter._fit_quantile(data, higher_is_worse=True, name="constant")
        
        # Should handle constant data gracefully
        assert len(bins) >= 2
        assert bins[-1]["lower_operator"] == "default"
    
    def test_mean_anchored_binning(self):
        """Test mean-anchored binning places portfolio mean correctly."""
        data = pd.Series(np.linspace(0, 100, 1000))
        portfolio_mean = 50
        
        fitter = BinFitter(n_bins=30, portfolio_avg_score=15)
        bins = fitter._fit_mean_anchored(data, portfolio_mean, "test")
        
        # Check structure
        assert len(bins) == 31  # 30 bins + 1 default
        assert bins[-1]["lower_operator"] == "default"
        
        # Verify bin scores go from 1 to 30
        scores = [b.get("score") for b in bins[:-1]]
        assert scores == list(range(1, 31))
    
    def test_mean_anchored_no_mean(self):
        """Test mean-anchored fallback when mean is None."""
        data = pd.Series(np.linspace(0, 100, 1000))
        
        fitter = BinFitter(n_bins=30)
        bins = fitter._fit_mean_anchored(data, portfolio_mean=None, name="test")
        
        # Should fall back gracefully
        assert len(bins) >= 2
        assert bins[-1]["lower_operator"] == "default"
    
    def test_reciprocal_binning(self):
        """Test reciprocal-spacing binning (for inverted metrics)."""
        data = pd.Series(np.linspace(1, 50, 500))  # Positive values for reciprocal
        portfolio_mean = 25
        
        fitter = BinFitter(n_bins=10)
        bins = fitter._fit_reciprocal(data, portfolio_mean, "test")
        
        # Check structure
        assert len(bins) >= 2
        assert bins[-1]["lower_operator"] == "default"
    
    def test_log_scale_binning(self):
        """Test log-scale binning for skewed distributions."""
        # Create right-skewed data
        data = pd.Series(np.random.exponential(scale=2, size=1000))
        
        fitter = BinFitter(n_bins=10)
        bins = fitter._fit_log_scale(data, higher_is_worse=True, name="test")
        
        # Should produce valid bins
        assert len(bins) >= 2
        assert bins[-1]["lower_operator"] == "default"
    
    def test_u_shaped_binning(self):
        """Test U-shaped binning (extremes are worse)."""
        # Create data with optimal middle values
        data = pd.Series(list(range(20, 50)) + list(range(50, 80)) + [1, 100, 105])
        
        fitter = BinFitter(n_bins=10)
        bins = fitter._fit_u_shaped(data, name="test")
        
        # Should produce valid bins
        assert len(bins) >= 2
        assert bins[-1]["lower_operator"] == "default"


class TestBinApplier:
    """Test BinApplier class for bin assignment."""
    
    def test_apply_single_value_basic(self):
        """Test applying bins to a single value."""
        thresholds = {
            "test_var": [
                {"score": 1, "lower_bound": 0, "lower_operator": ">=", 
                 "upper_bound": 25, "upper_operator": "<"},
                {"score": 2, "lower_bound": 25, "lower_operator": ">=",
                 "upper_bound": 50, "upper_operator": "<"},
                {"score": 3, "lower_bound": 50, "lower_operator": ">=",
                 "upper_bound": 100, "upper_operator": "<="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        applier = BinApplier(thresholds)
        
        assert applier.apply_single(10, "test_var") == 1
        assert applier.apply_single(30, "test_var") == 2
        assert applier.apply_single(75, "test_var") == 3
    
    def test_apply_single_nan_handling(self):
        """Test NaN handling in single application."""
        thresholds = {
            "test_var": [
                {"score": 1, "lower_bound": 0, "lower_operator": ">="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        applier = BinApplier(thresholds)
        
        assert applier.apply_single(np.nan, "test_var") == -1
        assert applier.apply_single(None, "test_var") == -1
    
    def test_apply_single_missing_variable(self):
        """Test behavior when variable not in thresholds."""
        thresholds = {
            "var_a": [
                {"score": 1, "lower_bound": 0, "lower_operator": ">="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        applier = BinApplier(thresholds)
        
        # Unknown variable should return -1
        assert applier.apply_single(50, "var_b") == -1
    
    def test_apply_series_vectorized(self):
        """Test vectorized series application."""
        thresholds = {
            "test_var": [
                {"score": 1, "lower_bound": 0, "lower_operator": ">=", 
                 "upper_bound": 25, "upper_operator": "<"},
                {"score": 2, "lower_bound": 25, "lower_operator": ">=",
                 "upper_bound": 50, "upper_operator": "<"},
                {"score": 3, "lower_bound": 50, "lower_operator": ">=",
                 "upper_bound": 100, "upper_operator": "<="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        applier = BinApplier(thresholds)
        
        series = pd.Series([10, 30, 75, np.nan, 5, 99])
        result = applier.apply_series(series, "test_var")
        
        expected = pd.Series([1, 2, 3, -1, 1, 3])
        pd.testing.assert_series_equal(result, expected)
    
    def test_apply_series_respects_operators(self):
        """Test that different operators (<, <=, >, >=) are respected."""
        thresholds = {
            "test_var": [
                {"score": 1, "lower_bound": 10, "lower_operator": ">", 
                 "upper_bound": 20, "upper_operator": "<="},
                {"score": 2, "lower_bound": 20, "lower_operator": ">",
                 "upper_bound": 30, "upper_operator": "<="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        applier = BinApplier(thresholds)
        
        # 10 should NOT match (> 10, not >=)
        assert applier.apply_single(10, "test_var") == -1
        
        # 10.1 should match
        assert applier.apply_single(10.1, "test_var") == 1
        
        # 20 should match (upper is <=)
        assert applier.apply_single(20, "test_var") == 1
    
    def test_apply_all_dataframe(self):
        """Test applying bins to all variables in DataFrame."""
        df = pd.DataFrame({
            'var_a': [5, 15, 25, 35, 45],
            'var_b': [10, 20, 30, 40, 50]
        })
        
        thresholds = {
            'var_a': [
                {"score": 1, "lower_bound": 0, "lower_operator": ">=", 
                 "upper_bound": 20, "upper_operator": "<"},
                {"score": 2, "lower_bound": 20, "lower_operator": ">=",
                 "upper_bound": 100, "upper_operator": "<="},
                {"score": -1, "lower_operator": "default"}
            ],
            'var_b': [
                {"score": 1, "lower_bound": 0, "lower_operator": ">=", 
                 "upper_bound": 30, "upper_operator": "<"},
                {"score": 2, "lower_bound": 30, "lower_operator": ">=",
                 "upper_bound": 100, "upper_operator": "<="},
                {"score": -1, "lower_operator": "default"}
            ]
        }
        
        variable_configs = {
            'var_a': {'source_column': 'var_a'},
            'var_b': {'source_column': 'var_b'}
        }
        
        applier = BinApplier(thresholds)
        result_df = applier.apply_all(df, variable_configs)
        
        # Check new columns created
        assert 'score_var_a' in result_df.columns
        assert 'score_var_b' in result_df.columns
        
        # Check values
        assert result_df['score_var_a'].tolist() == [1, 1, 2, 2, 2]
        assert result_df['score_var_b'].tolist() == [1, 1, 1, 2, 2]
    
    def test_score_range_default(self):
        """Test default score range is 1-30."""
        applier = BinApplier({})
        assert applier.score_min == 1
        assert applier.score_max == 30
    
    def test_score_range_custom(self):
        """Test custom score range."""
        applier = BinApplier({}, score_range=(1, 10))
        assert applier.score_min == 1
        assert applier.score_max == 10


class TestBinFitterAndApplier:
    """Integration tests combining BinFitter and BinApplier."""
    
    def test_fit_and_apply_roundtrip(self):
        """Test that fitted thresholds can be applied successfully."""
        # Generate test data
        data = pd.Series(np.random.normal(loc=50, scale=15, size=1000))
        
        # Fit thresholds
        fitter = BinFitter(n_bins=10)
        bins = fitter.fit_variable(data, method="quantile", name="test")
        
        # Create applier with fitted bins
        thresholds = {"test_var": bins}
        applier = BinApplier(thresholds)
        
        # Apply to original data
        scores = applier.apply_series(data, "test_var")
        
        # Verify all scores are valid (1-10 or -1)
        valid_scores = set(range(1, 11)) | {-1}
        assert all(s in valid_scores for s in scores)
        
        # Verify some valid scores assigned
        assert (scores > 0).sum() > 0
    
    def test_fit_apply_with_missing_data(self):
        """Test fit and apply with missing values."""
        # Data with gaps
        data = pd.Series([1, 2, 3, np.nan, 5, 6, np.nan, 8, 9, 10])
        
        fitter = BinFitter(n_bins=5)
        bins = fitter.fit_variable(data, method="quantile", name="test")
        
        thresholds = {"test_var": bins}
        applier = BinApplier(thresholds)
        
        scores = applier.apply_series(data, "test_var")
        
        # NaN inputs should produce -1 scores
        assert scores[3] == -1
        assert scores[6] == -1
    
    def test_reproducibility(self):
        """Test that fitting is reproducible."""
        data = pd.Series(np.random.RandomState(42).normal(loc=50, scale=15, size=1000))
        
        fitter1 = BinFitter(n_bins=10)
        bins1 = fitter1.fit_variable(data, method="quantile", name="test")
        
        fitter2 = BinFitter(n_bins=10)
        bins2 = fitter2.fit_variable(data, method="quantile", name="test")
        
        # Should be identical
        assert len(bins1) == len(bins2)
        for b1, b2 in zip(bins1, bins2):
            assert b1 == b2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
