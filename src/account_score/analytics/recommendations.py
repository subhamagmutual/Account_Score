"""Recommendation engine - suggest model improvements."""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np


class RecommendationEngine:
    """Generate recommendations for model improvement."""

    def __init__(self, config_path: str = "config/scoring_weights.json"):
        """Initialize engine."""
        self.config_path = config_path
        self.recommendations = []

    def suggest_weight_adjustments(
        self,
        component_correlations: Dict[str, float],
        baseline_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict]:
        """
        Suggest weight adjustments based on component performance.

        Args:
            component_correlations: Dict of component -> correlation coefficient
            baseline_weights: Current weights (default: 40/25/25/10)

        Returns:
            List of weight adjustment recommendations
        """
        if baseline_weights is None:
            baseline_weights = {
                'adequacy': 0.40,
                'capacity': 0.25,
                'appetite': 0.25,
                'environment': 0.10,
            }

        recommendations = []

        # Find strongest and weakest correlations
        sorted_corr = sorted(component_correlations.items(), key=lambda x: abs(x[1]), reverse=True)

        if len(sorted_corr) >= 2:
            strongest = sorted_corr[0]
            weakest = sorted_corr[-1]

            # If strongest component is underweighted, suggest increase
            if strongest[1] > 0.20 and baseline_weights.get(strongest[0], 0) < 0.35:
                recommendations.append({
                    'type': 'weight_increase',
                    'component': strongest[0],
                    'reason': f"Strong correlation ({strongest[1]:.3f}) to outcome",
                    'current_weight': baseline_weights.get(strongest[0], 0),
                    'suggested_weight': min(0.45, baseline_weights.get(strongest[0], 0) + 0.05),
                    'confidence': 'HIGH',
                })

            # If weakest component is overweighted, suggest decrease
            if abs(weakest[1]) < 0.10 and baseline_weights.get(weakest[0], 0) > 0.10:
                recommendations.append({
                    'type': 'weight_decrease',
                    'component': weakest[0],
                    'reason': f"Weak correlation ({abs(weakest[1]):.3f}) to outcome",
                    'current_weight': baseline_weights.get(weakest[0], 0),
                    'suggested_weight': max(0.05, baseline_weights.get(weakest[0], 0) - 0.05),
                    'confidence': 'MEDIUM',
                })

        self.recommendations = recommendations
        return recommendations

    def suggest_refitting_thresholds(
        self,
        df: pd.DataFrame,
        score_column: str,
        loss_column: str,
        current_gini: float,
    ) -> Optional[Dict]:
        """
        Suggest refitting binning thresholds if performance degrades.

        Args:
            df: Current scored data
            score_column: Score column
            loss_column: Loss column
            current_gini: Current Gini coefficient

        Returns:
            Recommendation to refit, or None
        """
        # Calculate Gini for current scores
        scores = df[score_column].dropna()
        losses = df[loss_column].dropna()

        # Spearman correlation as proxy for discrimination
        from scipy import stats
        if len(scores) > 2:
            corr, _ = stats.spearmanr(scores, losses)
            current_discrimination = abs(corr)

            # If discrimination < 0.15, recommend refitting
            if current_discrimination < 0.15:
                return {
                    'type': 'refit_thresholds',
                    'reason': f"Low discrimination (Gini {current_gini:.3f}, correlation {corr:.3f})",
                    'recommendation': 'Refit binning thresholds on new data',
                    'impact': 'HIGH',
                    'timeframe': 'URGENT',
                }

        return None

    def suggest_feature_engineering(
        self,
        feature_importances: Dict[str, float],
    ) -> List[Dict]:
        """
        Suggest new features based on analysis.

        Args:
            feature_importances: Dict of feature -> importance score

        Returns:
            List of feature engineering suggestions
        """
        suggestions = []

        # Find high-importance features
        high_importance = [
            (k, v) for k, v in feature_importances.items() if v > 0.10
        ]

        for feature, importance in high_importance:
            # Suggest interaction features
            suggestions.append({
                'type': 'interaction_feature',
                'description': f"Consider interactions with {feature}",
                'estimated_impact': 'MEDIUM',
                'effort': 'LOW',
            })

        return suggestions

    def suggest_population_expansion(
        self,
        population_stats: Dict[str, Dict],
        min_sample_size: int = 100,
    ) -> List[Dict]:
        """
        Suggest expanding to new populations.

        Args:
            population_stats: Stats by population
            min_sample_size: Minimum required size

        Returns:
            List of expansion recommendations
        """
        suggestions = []

        for pop_name, stats in population_stats.items():
            if stats.get('count', 0) >= min_sample_size:
                suggestions.append({
                    'type': 'population_expansion',
                    'population': pop_name,
                    'sample_size': stats.get('count'),
                    'recommendation': f"Sufficient data to score {pop_name} population",
                    'next_steps': [
                        'Validate score portability',
                        'Run diagnostics on sample',
                        'Compare to baseline distribution',
                    ],
                })

        return suggestions

    def generate_recommendations_report(self) -> str:
        """Generate text report of all recommendations."""
        if not self.recommendations:
            return "No recommendations at this time"

        report = "MODEL IMPROVEMENT RECOMMENDATIONS\n"
        report += "=" * 50 + "\n\n"

        for i, rec in enumerate(self.recommendations, 1):
            report += f"{i}. {rec.get('type', 'Unknown').upper()}\n"
            report += f"   Component: {rec.get('component', 'N/A')}\n"
            report += f"   Reason: {rec.get('reason', 'N/A')}\n"
            report += f"   Confidence: {rec.get('confidence', 'N/A')}\n"

            if 'current_weight' in rec:
                report += f"   Current: {rec['current_weight']:.3f}\n"
                report += f"   Suggested: {rec['suggested_weight']:.3f}\n"

            report += "\n"

        return report
