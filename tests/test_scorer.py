"""Unit tests for score calculation module.

Tests cover:
- Single record scoring
- Batch scoring
- Component calculation
- Composite calculation
- Score rescaling and capping
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
from src.account_score.scorer import ScoreCalculator
from src.account_score.utils import rescale_score, cap_score


class TestScoreCalculator:
    """Test ScoreCalculator for component and composite scoring."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        config = MagicMock()
        config.scoring_weights = {
            "composite_weights": {
                "adequacy": 0.40,
                "capacity": 0.25,
                "appetite": 0.25,
                "environment": 0.10
            },
            "adequacy_sub_scores": {
                "loss_cost": {"weight": 0.5},
                "frequency": {"weight": 0.5}
            },
            "capacity_sub_scores": {
                "limit_a": {"weight": 1.0}
            },
            "appetite_sub_scores": {
                "appetite_a": {"weight": 1.0}
            },
            "environment_sub_scores": {
                "env_a": {"weight": 1.0}
            }
        }
        config.get_composite_weights = lambda: config.scoring_weights["composite_weights"]
        config.get_scoring_params = lambda: {
            "sub_score_max": 30,
            "composite_max": 10,
            "composite_min": 1
        }
        return config
    
    def test_score_record_basic(self, mock_config):
        """Test single record scoring."""
        calculator = ScoreCalculator(mock_config)
        
        # Create sub-scores on 1-30 scale
        scores = {
            "loss_cost": 15,       # Middle score (1-30)
            "frequency": 12,
            "limit_a": 18,
            "appetite_a": 20,
            "env_a": 25
        }
        
        result = calculator.score_record(scores)
        
        # Check all component scores are present
        assert "adequacy_score" in result
        assert "capacity_score" in result
        assert "appetite_score" in result
        assert "environment_score" in result
        assert "composite_score" in result
        
        # Check all scores are in valid range (1-10)
        for key in ["adequacy_score", "capacity_score", "appetite_score", "environment_score"]:
            if result[key] is not None:
                assert 1 <= result[key] <= 10
        
        # Composite score should be integer 1-10
        assert isinstance(result["composite_score"], (int, np.integer))
        assert 1 <= result["composite_score"] <= 10
    
    def test_score_record_with_missing_scores(self, mock_config):
        """Test handling of missing sub-scores."""
        calculator = ScoreCalculator(mock_config)
        
        scores = {
            "loss_cost": 15,
            # frequency missing
            "limit_a": 18,
            "appetite_a": 20,
            "env_a": 25
        }
        
        result = calculator.score_record(scores)
        
        # Should still produce valid scores
        assert result["adequacy_score"] is not None
        assert 1 <= result["adequacy_score"] <= 10
        
        assert result["composite_score"] is not None
        assert 1 <= result["composite_score"] <= 10
    
    def test_score_record_all_missing(self, mock_config):
        """Test when all sub-scores are missing."""
        calculator = ScoreCalculator(mock_config)
        
        scores = {}
        result = calculator.score_record(scores)
        
        # Should return None for all scores
        assert result["adequacy_score"] is None
        assert result["composite_score"] is None
    
    def test_score_record_extreme_values(self, mock_config):
        """Test scoring with extreme sub-score values."""
        calculator = ScoreCalculator(mock_config)
        
        # Worst case scenario
        scores = {
            "loss_cost": 30,
            "frequency": 30,
            "limit_a": 30,
            "appetite_a": 30,
            "env_a": 30
        }
        
        result = calculator.score_record(scores)
        
        # Should still produce valid composite score
        assert result["composite_score"] is not None
        assert result["composite_score"] == 10  # Capped at max
    
    def test_score_record_best_case(self, mock_config):
        """Test scoring with best-case sub-scores."""
        calculator = ScoreCalculator(mock_config)
        
        # Best case
        scores = {
            "loss_cost": 1,
            "frequency": 1,
            "limit_a": 1,
            "appetite_a": 1,
            "env_a": 1
        }
        
        result = calculator.score_record(scores)
        
        assert result["composite_score"] == 1  # Best score
    
    def test_score_batch_basic(self, mock_config):
        """Test batch DataFrame scoring."""
        calculator = ScoreCalculator(mock_config)
        
        # Create test DataFrame with score columns
        df = pd.DataFrame({
            'score_loss_cost': [15, 10, 20],
            'score_frequency': [12, 14, 18],
            'score_limit_a': [18, 16, 22],
            'score_appetite_a': [20, 19, 21],
            'score_env_a': [25, 24, 26]
        })
        
        result = calculator.score_batch(df)
        
        # Check output columns added
        assert 'adequacy_score' in result.columns
        assert 'composite_score' in result.columns
        
        # Check all scores valid
        valid_composite = result['composite_score'].dropna()
        assert all((valid_composite >= 1) & (valid_composite <= 10))
        
        # Should have valid scores for all 3 records
        assert valid_composite.shape[0] == 3
    
    def test_score_batch_with_invalid_scores(self, mock_config):
        """Test batch scoring with -1 (invalid) scores."""
        calculator = ScoreCalculator(mock_config)
        
        df = pd.DataFrame({
            'score_loss_cost': [15, -1, 20],  # -1 is invalid
            'score_frequency': [12, -1, 18],
            'score_limit_a': [18, -1, 22],
            'score_appetite_a': [20, -1, 21],
            'score_env_a': [25, -1, 26]
        })
        
        result = calculator.score_batch(df)
        
        # First and third records should have valid composite scores
        assert result['composite_score'].iloc[0] > 0
        assert result['composite_score'].iloc[2] > 0
    
    def test_score_batch_empty_dataframe(self, mock_config):
        """Test batch scoring with empty DataFrame."""
        calculator = ScoreCalculator(mock_config)
        
        df = pd.DataFrame({
            'score_var': []
        })
        
        result = calculator.score_batch(df)
        
        # Should handle gracefully
        assert len(result) == 0
        assert 'composite_score' in result.columns
    
    def test_component_calculation(self, mock_config):
        """Test individual component score calculation."""
        calculator = ScoreCalculator(mock_config)
        
        # Simulate rescaled scores (1-10 range)
        rescaled = {
            "loss_cost": 5,
            "frequency": 5,
            "limit_a": 5,
            "appetite_a": 5,
            "env_a": 5
        }
        
        adequacy = calculator._calc_component(rescaled, "adequacy_sub_scores")
        capacity = calculator._calc_component(rescaled, "capacity_sub_scores")
        appetite = calculator._calc_component(rescaled, "appetite_sub_scores")
        environment = calculator._calc_component(rescaled, "environment_sub_scores")
        
        # All should be close to 5 (given middle-range inputs)
        assert 4 < adequacy < 6 if not pd.isna(adequacy) else True
        assert 4 < capacity < 6 if not pd.isna(capacity) else True
        assert 4 < appetite < 6 if not pd.isna(appetite) else True
        assert 4 < environment < 6 if not pd.isna(environment) else True
    
    def test_composite_calculation(self, mock_config):
        """Test composite score from components."""
        calculator = ScoreCalculator(mock_config)
        
        # Equal component scores
        composite = calculator._calc_composite(5, 5, 5, 5)
        
        # Should be 5 (with weights 0.4, 0.25, 0.25, 0.1)
        assert composite is not None
        assert 4.9 < composite < 5.1


class TestScoreRescaling:
    """Test score rescaling utility functions."""
    
    def test_rescale_score_basic(self):
        """Test basic score rescaling from 1-30 to 1-10."""
        result = rescale_score(1, 1, 30, 1, 10)
        assert result == 1.0
        
        result = rescale_score(30, 1, 30, 1, 10)
        assert result == 10.0
        
        result = rescale_score(15.5, 1, 30, 1, 10)
        assert 5.0 < result < 6.0
    
    def test_rescale_score_series(self):
        """Test rescaling a pandas Series."""
        series = pd.Series([1, 15, 30])
        result = rescale_score(series, 1, 30, 1, 10)
        
        expected = pd.Series([1.0, 5.5, 10.0])
        pd.testing.assert_series_equal(result, expected, atol=0.01)
    
    def test_rescale_score_with_nan(self):
        """Test rescaling with NaN values."""
        series = pd.Series([1, np.nan, 30])
        result = rescale_score(series, 1, 30, 1, 10)
        
        assert pd.isna(result[1])
        assert result[0] == 1.0
        assert result[2] == 10.0
    
    def test_cap_score_basic(self):
        """Test score capping."""
        assert cap_score(0.5, 1, 10) == 1
        assert cap_score(5, 1, 10) == 5
        assert cap_score(10.5, 1, 10) == 10
    
    def test_cap_score_series(self):
        """Test capping a Series."""
        series = pd.Series([0, 5, 10, 15])
        result = cap_score(series, 1, 10)
        
        expected = pd.Series([1, 5, 10, 10])
        pd.testing.assert_series_equal(result, expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
