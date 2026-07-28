"""Unit tests for config and input validators."""

import pytest
import pandas as pd
import numpy as np
from src.account_score.config_validator import ConfigValidator
from src.account_score.input_validator import InputValidator


class TestConfigValidator:
    """Test ConfigValidator for configuration validation."""
    
    @pytest.fixture
    def valid_config(self):
        """Create a minimal valid configuration."""
        return {
            "scoring_weights": {
                "composite_weights": {
                    "adequacy": 0.40,
                    "capacity": 0.25,
                    "appetite": 0.25,
                    "environment": 0.10
                },
                "adequacy_sub_scores": {
                    "var_a": {"weight": 1.0, "type": "ratio"}
                },
                "capacity_sub_scores": {
                    "var_b": {"weight": 1.0, "type": "direct"}
                },
                "appetite_sub_scores": {
                    "var_c": {"weight": 1.0, "type": "direct"}
                },
                "environment_sub_scores": {
                    "var_d": {"weight": 1.0, "type": "categorical"}
                }
            },
            "pipeline_params": {
                "data": {"input_file": "/path/to/data.csv"},
                "filters": {"min_premium": 10000},
                "scoring": {"sub_score_max": 30, "composite_max": 10},
                "credibility": {
                    "full_credibility_premium": 50000,
                    "complement_score": 15,
                    "apply_to": ["var_a"]
                },
                "binning": {
                    "default_method": "quantile",
                    "n_bins": 30,
                    "methods_by_variable": {}
                },
                "identifiers": {
                    "npi": "NPI",
                    "specialty": "SPECIALTY",
                    "state": "STATE"
                }
            },
            "specialty_tiers": {
                "default_score": 5,
                "tiers": {"Surgery": 3, "Internal Medicine": 6}
            },
            "state_tiers": {
                "default_score": 5,
                "tiers": {"CA": 4, "TX": 6}
            }
        }
    
    def test_valid_config_passes(self, valid_config):
        """Test that valid configuration passes all checks."""
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_missing_scoring_weights(self, valid_config):
        """Test detection of missing scoring_weights."""
        del valid_config["scoring_weights"]
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("scoring_weights" in e for e in errors)
    
    def test_weights_dont_sum_to_one(self, valid_config):
        """Test detection of weights not summing to 1.0."""
        valid_config["scoring_weights"]["composite_weights"] = {
            "adequacy": 0.40,
            "capacity": 0.25,
            "appetite": 0.25,
            "environment": 0.05  # Sum is 0.95
        }
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("sum" in e.lower() for e in errors)
    
    def test_missing_dimension(self, valid_config):
        """Test detection of missing dimension."""
        del valid_config["scoring_weights"]["adequacy_sub_scores"]
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("adequacy_sub_scores" in e for e in errors)
    
    def test_missing_pipeline_params(self, valid_config):
        """Test detection of missing pipeline_params."""
        del valid_config["pipeline_params"]
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("pipeline_params" in e for e in errors)
    
    def test_invalid_credibility_premium(self, valid_config):
        """Test detection of invalid credibility premium."""
        valid_config["pipeline_params"]["credibility"]["full_credibility_premium"] = -100
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("premium" in e.lower() and "positive" in e.lower() for e in errors)
    
    def test_invalid_binning_method(self, valid_config):
        """Test detection of invalid binning method."""
        valid_config["pipeline_params"]["binning"]["methods_by_variable"] = {
            "var_a": "invalid_method"
        }
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("Unknown binning method" in e for e in errors)
    
    def test_invalid_tier_score(self, valid_config):
        """Test detection of invalid tier scores."""
        valid_config["specialty_tiers"]["tiers"]["Surgery"] = 15  # Should be 1-10
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("1-10" in e for e in errors)
    
    def test_missing_tier_default(self, valid_config):
        """Test detection of missing tier default score."""
        del valid_config["specialty_tiers"]["default_score"]
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        assert not is_valid
        assert any("default_score" in e and "specialty" in e for e in errors)
    
    def test_warnings_for_minor_issues(self, valid_config):
        """Test that minor issues are warnings, not errors."""
        # Remove input file
        valid_config["pipeline_params"]["data"]["input_file"] = "/nonexistent/path.csv"
        
        validator = ConfigValidator(valid_config)
        is_valid, errors, warnings = validator.validate_all()
        
        # Should be valid but with warning
        assert is_valid is True
        assert any("Input file" in w for w in warnings)


class TestInputValidator:
    """Test InputValidator for data quality checks."""
    
    @pytest.fixture
    def valid_config(self):
        """Create minimal config for testing."""
        return {
            "pipeline_params": {
                "identifiers": {
                    "npi": "NPI",
                    "year": "COVEFF_DATE"
                }
            },
            "scoring_weights": {
                "adequacy_sub_scores": {
                    "loss_cost": {"source_column": "TOTAL_LOSS", "numerator": "TOTAL_LOSS"},
                    "frequency": {"numerator": "CLAIM_COUNT", "denominator": "YEARS_EXP"}
                },
                "capacity_sub_scores": {},
                "appetite_sub_scores": {},
                "environment_sub_scores": {}
            }
        }
    
    def test_valid_data_passes(self, valid_config):
        """Test that valid data passes all checks."""
        df = pd.DataFrame({
            'NPI': [1, 2, 3],
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [100, 200, 300],
            'CLAIM_COUNT': [1, 2, 3],
            'YEARS_EXP': [5, 5, 5]
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert len(issues) == 0
        assert stats['total_records'] == 3
    
    def test_missing_identifier_columns(self, valid_config):
        """Test detection of missing identifier columns."""
        df = pd.DataFrame({
            'TOTAL_LOSS': [100, 200, 300]
            # NPI and COVEFF_DATE missing
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert any("Missing identifier" in issue for issue in issues)
    
    def test_duplicate_records_detected(self, valid_config):
        """Test detection of duplicate physician-years."""
        df = pd.DataFrame({
            'NPI': [1, 1, 2],  # First two are duplicates
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [100, 100, 300]
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert any("duplicate" in issue.lower() for issue in issues)
        assert stats.get('duplicate_records', 0) == 2
    
    def test_high_null_percentage_detected(self, valid_config):
        """Test detection of columns with high null percentages."""
        df = pd.DataFrame({
            'NPI': [1, 2, 3],
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [np.nan, np.nan, 300]  # 67% null
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert any("TOTAL_LOSS" in issue and "null" in issue.lower() for issue in issues)
    
    def test_negative_values_detected(self, valid_config):
        """Test detection of negative values in cost metrics."""
        df = pd.DataFrame({
            'NPI': [1, 2, 3],
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [-100, 200, 300],  # Negative loss
            'WRTN_PREM_AMT': [50000, 75000, 100000]
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert any("negative" in issue.lower() for issue in issues)
        assert stats.get('invalid_numeric_values', 0) > 0
    
    def test_outliers_detected(self, valid_config):
        """Test detection of extreme outliers."""
        df = pd.DataFrame({
            'NPI': list(range(100)),
            'COVEFF_DATE': ['2024-01-01'] * 100,
            'TOTAL_LOSS': [100] * 95 + [100000, 100000, 100000, 100000, 100000]  # 5 extreme outliers
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        # 5% outliers should trigger warning
        assert any("outlier" in issue.lower() for issue in issues)
    
    def test_empty_dataframe(self, valid_config):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert any("empty" in issue.lower() for issue in issues)
    
    def test_stats_generation(self, valid_config):
        """Test that statistics are properly generated."""
        df = pd.DataFrame({
            'NPI': [1, 2, 3],
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [100, 200, 300]
        })
        
        validator = InputValidator(valid_config, verbose=False)
        df, issues, stats = validator.validate_dataframe(df)
        
        assert stats['total_records'] == 3
        assert stats['total_columns'] == 3
        assert 'memory_mb' in stats
        assert 'numeric_columns' in stats
    
    def test_print_report(self, valid_config, capsys):
        """Test report printing functionality."""
        df = pd.DataFrame({
            'NPI': [1, 2, 3],
            'COVEFF_DATE': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'TOTAL_LOSS': [100, np.nan, 300]
        })
        
        validator = InputValidator(valid_config, verbose=True)
        df, issues, stats = validator.validate_dataframe(df)
        validator.print_report()
        
        # Just verify it doesn't crash
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
