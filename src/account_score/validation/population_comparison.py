"""
Population comparison - Compare distributions and statistics across populations.

Tests score portability:
- Do MagMutual scores work for DHC?
- Are thresholds optimal for new populations?
- Do variables have same signal strength?
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from scipy import stats


class PopulationComparator:
    """Compare two populations on scoring metrics."""

    def __init__(self):
        """Initialize comparator."""
        self.comparison_results = {}

    def compare_distributions(
        self,
        pop1_scores: pd.Series,
        pop2_scores: pd.Series,
        pop1_name: str = "Population 1",
        pop2_name: str = "Population 2",
    ) -> Dict:
        """
        Compare score distributions between populations.

        Args:
            pop1_scores: Scores from first population
            pop2_scores: Scores from second population
            pop1_name: Name of first population
            pop2_name: Name of second population

        Returns:
            Dictionary with comparison statistics
        """
        pop1 = pop1_scores.dropna()
        pop2 = pop2_scores.dropna()

        # Basic statistics
        comparison = {
            pop1_name: {
                'mean': float(pop1.mean()),
                'median': float(pop1.median()),
                'std': float(pop1.std()),
                'min': float(pop1.min()),
                'max': float(pop1.max()),
                'p25': float(pop1.quantile(0.25)),
                'p75': float(pop1.quantile(0.75)),
                'count': len(pop1),
            },
            pop2_name: {
                'mean': float(pop2.mean()),
                'median': float(pop2.median()),
                'std': float(pop2.std()),
                'min': float(pop2.min()),
                'max': float(pop2.max()),
                'p25': float(pop2.quantile(0.25)),
                'p75': float(pop2.quantile(0.75)),
                'count': len(pop2),
            },
        }

        # Statistical tests
        comparison['statistical_tests'] = {
            'kolmogorov_smirnov': {
                'statistic': float(stats.ks_2samp(pop1, pop2)[0]),
                'pvalue': float(stats.ks_2samp(pop1, pop2)[1]),
                'interpretation': 'Different distributions' if stats.ks_2samp(pop1, pop2)[1] < 0.05 else 'Similar distributions',
            },
            'mann_whitney_u': {
                'statistic': float(stats.mannwhitneyu(pop1, pop2)[0]),
                'pvalue': float(stats.mannwhitneyu(pop1, pop2)[1]),
                'interpretation': 'Different medians' if stats.mannwhitneyu(pop1, pop2)[1] < 0.05 else 'Similar medians',
            },
        }

        # Mean difference
        mean_diff = pop2.mean() - pop1.mean()
        comparison['mean_difference'] = float(mean_diff)
        comparison['mean_difference_pct'] = float((mean_diff / pop1.mean()) * 100)

        self.comparison_results['distribution_comparison'] = comparison
        return comparison

    def compare_by_bands(
        self,
        pop1_df: pd.DataFrame,
        pop2_df: pd.DataFrame,
        score_column: str,
        target_column: Optional[str] = None,
        n_bands: int = 10,
    ) -> Dict:
        """
        Compare populations by score band (decile analysis).

        Args:
            pop1_df: First population dataframe
            pop2_df: Second population dataframe
            score_column: Score column name
            target_column: Loss metric column (optional)
            n_bands: Number of bands

        Returns:
            Dictionary with band-level comparisons
        """
        pop1 = pop1_df[[score_column]].dropna()
        pop2 = pop2_df[[score_column]].dropna()

        # Create bands using population 1
        pop1_bands = pd.qcut(pop1[score_column], q=n_bands, duplicates='drop', labels=False)
        pop1_band_dist = pop1_bands.value_counts(normalize=True).sort_index()

        # Apply same band edges to population 2
        edges = pd.qcut(pop1[score_column], q=n_bands, duplicates='drop', retbins=True)[1]
        pop2_bands = pd.cut(pop2[score_column], bins=edges, labels=False, include_lowest=True)
        pop2_band_dist = pop2_bands.value_counts(normalize=True).sort_index()

        comparison = {
            'band_counts': {
                'population_1': pop1_band_dist.to_dict(),
                'population_2': pop2_band_dist.to_dict(),
            },
        }

        # If target provided, compare loss by band
        if target_column and target_column in pop1_df.columns and target_column in pop2_df.columns:
            pop1_target = pop1_df.copy()
            pop1_target['band'] = pop1_bands
            pop2_target = pop2_df.copy()
            pop2_target['band'] = pop2_bands

            comparison['loss_by_band'] = {
                'population_1': pop1_target.groupby('band')[target_column].agg(['mean', 'count']).to_dict(),
                'population_2': pop2_target.groupby('band')[target_column].agg(['mean', 'count']).to_dict(),
            }

        self.comparison_results['band_comparison'] = comparison
        return comparison

    def compare_variable_signal(
        self,
        pop1_df: pd.DataFrame,
        pop2_df: pd.DataFrame,
        variable_columns: List[str],
        target_column: str,
    ) -> Dict:
        """
        Compare variable predictiveness across populations.

        Args:
            pop1_df: First population dataframe
            pop2_df: Second population dataframe
            variable_columns: Variable column names
            target_column: Target (loss) column name

        Returns:
            Dictionary with correlation/signal by variable and population
        """
        comparison = {}

        for var in variable_columns:
            if var not in pop1_df.columns or var not in pop2_df.columns:
                continue
            if target_column not in pop1_df.columns or target_column not in pop2_df.columns:
                continue

            # Calculate Spearman correlation (rank-based, robust to outliers)
            pop1_corr = pop1_df[[var, target_column]].dropna()
            pop2_corr = pop2_df[[var, target_column]].dropna()

            if len(pop1_corr) > 2 and len(pop2_corr) > 2:
                pop1_rho, pop1_p = stats.spearmanr(pop1_corr[var], pop1_corr[target_column])
                pop2_rho, pop2_p = stats.spearmanr(pop2_corr[var], pop2_corr[target_column])

                comparison[var] = {
                    'population_1': {
                        'correlation': float(pop1_rho),
                        'pvalue': float(pop1_p),
                        'significant': pop1_p < 0.05,
                    },
                    'population_2': {
                        'correlation': float(pop2_rho),
                        'pvalue': float(pop2_p),
                        'significant': pop2_p < 0.05,
                    },
                    'correlation_diff': float(abs(pop2_rho - pop1_rho)),
                }

        self.comparison_results['variable_signal'] = comparison
        return comparison

    def compare_gini(
        self,
        pop1_scores: pd.Series,
        pop2_scores: pd.Series,
    ) -> Dict:
        """
        Compare Gini coefficients (discrimination power) across populations.

        Args:
            pop1_scores: Scores from population 1
            pop2_scores: Scores from population 2

        Returns:
            Dictionary with Gini comparison
        """
        pop1 = pop1_scores.dropna().values
        pop2 = pop2_scores.dropna().values

        gini1 = self._calculate_gini(pop1)
        gini2 = self._calculate_gini(pop2)

        comparison = {
            'population_1_gini': float(gini1),
            'population_2_gini': float(gini2),
            'gini_difference': float(abs(gini2 - gini1)),
            'gini_ratio': float(gini2 / gini1) if gini1 > 0 else 0,
            'interpretation': self._interpret_gini_difference(abs(gini2 - gini1)),
        }

        self.comparison_results['gini_comparison'] = comparison
        return comparison

    @staticmethod
    def _calculate_gini(values: np.ndarray) -> float:
        """Calculate Gini coefficient."""
        if len(values) < 2:
            return 0.0

        sorted_vals = np.sort(values)
        n = len(sorted_vals)
        cum_vals = np.cumsum(sorted_vals)

        gini = (2 * np.sum((n + 1 - np.arange(1, n + 1)) * sorted_vals)) / (n * np.sum(sorted_vals)) - 1
        return float(gini)

    @staticmethod
    def _interpret_gini_difference(diff: float) -> str:
        """Interpret Gini difference."""
        if diff < 0.05:
            return "Very similar discrimination"
        elif diff < 0.10:
            return "Moderately similar discrimination"
        elif diff < 0.20:
            return "Notable difference in discrimination"
        else:
            return "Significant difference in discrimination"

    def generate_report(self) -> Dict:
        """Generate comprehensive comparison report."""
        return self.comparison_results
