"""Advanced validation - sensitivity analysis and what-if modeling."""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np


class AdvancedValidator:
    """Advanced validation and sensitivity analysis."""

    def __init__(self):
        """Initialize validator."""
        self.sensitivity_results = {}
        self.scenarios = []

    def sensitivity_analysis(
        self,
        df: pd.DataFrame,
        score_column: str,
        loss_column: str,
        weights: Dict[str, float],
        components: List[str],
    ) -> Dict:
        """
        Measure sensitivity of composite score to component weight changes.

        Args:
            df: Dataframe with scores
            score_column: Composite score column
            loss_column: Loss column
            weights: Current component weights
            components: List of component columns

        Returns:
            Sensitivity analysis results
        """
        baseline_corr = self._calculate_correlation(df, score_column, loss_column)
        sensitivity = {}

        for component in components:
            # Test 10% weight increase
            test_weights = weights.copy()
            test_weights[component] += 0.05

            # Normalize weights
            total = sum(test_weights.values())
            test_weights = {k: v / total for k, v in test_weights.items()}

            # Calculate new correlation
            test_corr = self._calculate_correlation(df, score_column, loss_column)

            sensitivity[component] = {
                'baseline_correlation': float(baseline_corr),
                'test_correlation': float(test_corr),
                'impact': float(test_corr - baseline_corr),
                'impact_pct': float((test_corr - baseline_corr) / baseline_corr * 100),
            }

        self.sensitivity_results = sensitivity
        return sensitivity

    def scenario_analysis(
        self,
        df: pd.DataFrame,
        score_column: str,
        scenarios: Dict[str, Dict],
    ) -> List[Dict]:
        """
        Run what-if scenarios (e.g., "if we weight X higher").

        Args:
            df: Dataframe
            score_column: Score column
            scenarios: Dict of scenario_name -> parameter changes

        Returns:
            Scenario results
        """
        results = []

        for scenario_name, params in scenarios.items():
            # Apply scenario
            test_df = df.copy()

            # Simulate score changes based on params
            for col, change in params.items():
                if col in test_df.columns:
                    test_df[col] = test_df[col] * (1 + change)

            # Evaluate scenario
            result = {
                'scenario': scenario_name,
                'parameters': params,
                'affected_rows': len(test_df),
                'avg_score_before': float(df[score_column].mean()),
                'avg_score_after': float(test_df[score_column].mean()),
                'score_change': float(
                    test_df[score_column].mean() - df[score_column].mean()
                ),
                'pct_change': float(
                    (test_df[score_column].mean() - df[score_column].mean())
                    / df[score_column].mean()
                    * 100
                ),
            }

            results.append(result)

        self.scenarios = results
        return results

    def stress_test(
        self,
        df: pd.DataFrame,
        score_column: str,
        stress_levels: Optional[List[float]] = None,
    ) -> Dict:
        """
        Stress test scores under extreme conditions.

        Args:
            df: Dataframe
            score_column: Score column
            stress_levels: List of stress multipliers (default: [0.5, 1.5, 2.0])

        Returns:
            Stress test results
        """
        if stress_levels is None:
            stress_levels = [0.5, 1.5, 2.0]

        results = {}
        baseline_scores = df[score_column].dropna()

        for stress_level in stress_levels:
            stressed_scores = baseline_scores * stress_level

            # Cap scores at valid range
            stressed_scores = stressed_scores.clip(1.0, 10.0)

            results[f"{stress_level}x"] = {
                'mean': float(stressed_scores.mean()),
                'median': float(stressed_scores.median()),
                'std': float(stressed_scores.std()),
                'min': float(stressed_scores.min()),
                'max': float(stressed_scores.max()),
                'out_of_range_pct': float(
                    ((baseline_scores * stress_level < 1.0) | (baseline_scores * stress_level > 10.0)).sum()
                    / len(baseline_scores)
                    * 100
                ),
            }

        return results

    def threshold_impact_analysis(
        self,
        df: pd.DataFrame,
        score_column: str,
        thresholds: Dict[str, float],
    ) -> Dict:
        """
        Analyze impact of different score thresholds.

        Args:
            df: Dataframe
            score_column: Score column
            thresholds: Dict of threshold_name -> value

        Returns:
            Threshold impact analysis
        """
        results = {}
        scores = df[score_column].dropna()

        for threshold_name, threshold_value in thresholds.items():
            above = (scores >= threshold_value).sum()
            pct_above = above / len(scores) * 100

            results[threshold_name] = {
                'threshold': threshold_value,
                'count_above': int(above),
                'count_below': int(len(scores) - above),
                'pct_above': float(pct_above),
                'pct_below': float(100 - pct_above),
            }

        return results

    @staticmethod
    def _calculate_correlation(
        df: pd.DataFrame,
        score_column: str,
        loss_column: str,
    ) -> float:
        """Calculate Spearman correlation between score and loss."""
        from scipy import stats

        data = df[[score_column, loss_column]].dropna()
        if len(data) < 2:
            return 0.0

        corr, _ = stats.spearmanr(data[score_column], data[loss_column])
        return corr

    def generate_validation_report(self) -> str:
        """Generate validation report."""
        report = "ADVANCED VALIDATION REPORT\n"
        report += "=" * 50 + "\n\n"

        if self.sensitivity_results:
            report += "SENSITIVITY ANALYSIS\n"
            report += "-" * 30 + "\n"
            for component, results in self.sensitivity_results.items():
                report += f"{component}:\n"
                report += f"  Impact: {results['impact_pct']:.2f}%\n"

            report += "\n"

        if self.scenarios:
            report += "SCENARIO ANALYSIS\n"
            report += "-" * 30 + "\n"
            for scenario in self.scenarios:
                report += f"{scenario['scenario']}:\n"
                report += f"  Score change: {scenario['pct_change']:.2f}%\n"

            report += "\n"

        return report
