"""Unit tests for analytics modules."""

import pytest
import pandas as pd
import numpy as np
import tempfile

from src.account_score.analytics import (
    PopulationAnalytics,
    RecommendationEngine,
    AdvancedValidator,
)
from src.account_score.analytics.dashboard import DashboardGenerator


class TestPopulationAnalytics:
    """Test population analytics."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return pd.DataFrame({
            'composite_score': np.random.uniform(1, 10, 100),
            'loss_amount': np.random.uniform(1000, 100000, 100),
            'specialty': ['Surgery'] * 50 + ['Medicine'] * 50,
            'state': ['CA'] * 50 + ['TX'] * 50,
        })

    def test_analyze_by_segment(self, sample_data):
        """Test segment analysis."""
        analytics = PopulationAnalytics()
        results = analytics.analyze_by_segment(
            sample_data,
            'composite_score',
            ['specialty', 'state']
        )

        assert 'specialty' in results
        assert 'state' in results
        assert 'Surgery' in results['specialty']
        assert 'CA' in results['state']
        assert results['specialty']['Surgery']['count'] == 50

    def test_risk_profile_comparison(self, sample_data):
        """Test risk profile analysis."""
        analytics = PopulationAnalytics()
        profiles = analytics.risk_profile_comparison(
            sample_data,
            'composite_score'
        )

        assert 'risk_profiles' in profiles
        assert 'low' in profiles['risk_profiles']
        assert 'medium' in profiles['risk_profiles']
        assert 'high' in profiles['risk_profiles']
        assert profiles['total_physicians'] == 100

    def test_identify_outlier_segments(self, sample_data):
        """Test outlier segment identification."""
        analytics = PopulationAnalytics()
        outliers = analytics.identify_outlier_segments(
            sample_data,
            'composite_score',
            'specialty',
            zscore_threshold=2.0
        )

        assert isinstance(outliers, list)
        # May or may not have outliers depending on data


class TestRecommendationEngine:
    """Test recommendation engine."""

    def test_suggest_weight_adjustments(self):
        """Test weight adjustment suggestions."""
        engine = RecommendationEngine()
        correlations = {
            'adequacy': 0.25,
            'capacity': 0.08,
            'appetite': 0.20,
            'environment': 0.05,
        }
        baseline_weights = {
            'adequacy': 0.40,
            'capacity': 0.25,
            'appetite': 0.25,
            'environment': 0.10,
        }

        recommendations = engine.suggest_weight_adjustments(
            correlations,
            baseline_weights
        )

        assert isinstance(recommendations, list)
        if recommendations:
            assert 'type' in recommendations[0]
            assert recommendations[0]['type'] in ['weight_increase', 'weight_decrease']

    def test_suggest_refitting_thresholds(self):
        """Test threshold refitting suggestions."""
        df = pd.DataFrame({
            'composite_score': np.random.uniform(1, 10, 100),
            'loss_amount': np.random.uniform(1000, 100000, 100),
        })

        engine = RecommendationEngine()
        recommendation = engine.suggest_refitting_thresholds(
            df,
            'composite_score',
            'loss_amount',
            current_gini=0.08
        )

        if recommendation:
            assert recommendation['type'] == 'refit_thresholds'


class TestAdvancedValidator:
    """Test advanced validation."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return pd.DataFrame({
            'composite_score': np.random.uniform(1, 10, 100),
            'component1': np.random.uniform(1, 10, 100),
            'component2': np.random.uniform(1, 10, 100),
            'loss_amount': np.random.uniform(1000, 100000, 100),
        })

    def test_stress_test(self, sample_data):
        """Test stress testing."""
        validator = AdvancedValidator()
        results = validator.stress_test(
            sample_data,
            'composite_score',
            stress_levels=[0.5, 1.5, 2.0]
        )

        assert '0.5x' in results
        assert '1.5x' in results
        assert '2.0x' in results
        assert 'mean' in results['1.5x']

    def test_threshold_impact_analysis(self, sample_data):
        """Test threshold impact analysis."""
        validator = AdvancedValidator()
        thresholds = {
            'low_risk': 4.0,
            'high_risk': 7.0,
        }

        results = validator.threshold_impact_analysis(
            sample_data,
            'composite_score',
            thresholds
        )

        assert 'low_risk' in results
        assert 'high_risk' in results
        assert 'pct_above' in results['low_risk']


class TestDashboardGenerator:
    """Test dashboard generation."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        return pd.DataFrame({
            'composite_score': np.random.uniform(1, 10, 100),
            'adequacy_score': np.random.uniform(1, 10, 100),
            'capacity_score': np.random.uniform(1, 10, 100),
            'loss_amount': np.random.uniform(1000, 100000, 100),
        })

    def test_generate_performance_dashboard(self, sample_data):
        """Test dashboard generation."""
        generator = DashboardGenerator()
        dashboard = generator.generate_performance_dashboard(
            sample_data,
            'composite_score',
            'loss_amount',
            ['adequacy_score', 'capacity_score']
        )

        assert 'generated_at' in dashboard
        assert 'score_distribution' in dashboard
        assert 'components' in dashboard
        assert dashboard['total_records'] == 100
        assert 'mean' in dashboard['score_distribution']

    def test_export_dashboard_json(self, sample_data):
        """Test JSON export."""
        generator = DashboardGenerator()
        dashboard = generator.generate_performance_dashboard(
            sample_data,
            'composite_score',
            'loss_amount',
            ['adequacy_score']
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = f"{tmpdir}/dashboard.json"
            generator.export_dashboard_json(dashboard, output_path)

            # Verify file was created
            import os
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

    def test_export_dashboard_html(self, sample_data):
        """Test HTML export."""
        generator = DashboardGenerator()
        dashboard = generator.generate_performance_dashboard(
            sample_data,
            'composite_score',
            'loss_amount',
            []
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = f"{tmpdir}/dashboard.html"
            generator.export_dashboard_html(dashboard, output_path)

            # Verify file was created
            import os
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                content = f.read()
                assert '<html>' in content
