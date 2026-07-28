"""Population analytics - segment analysis and risk profiles."""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy import stats


class PopulationAnalytics:
    """Analyze populations by segment and generate insights."""

    def __init__(self):
        """Initialize analytics."""
        self.segments = {}
        self.insights = []

    def analyze_by_segment(
        self,
        df: pd.DataFrame,
        score_column: str,
        segment_columns: List[str],
    ) -> Dict:
        """
        Analyze scores by segment (specialty, state, etc.).

        Args:
            df: Dataframe with scores
            score_column: Score column name
            segment_columns: Columns to segment by

        Returns:
            Dictionary with segment analysis
        """
        analysis = {}

        for seg_col in segment_columns:
            segment_stats = {}

            for segment_value in df[seg_col].unique():
                segment_df = df[df[seg_col] == segment_value]
                scores = segment_df[score_column].dropna()

                if len(scores) > 0:
                    segment_stats[str(segment_value)] = {
                        'count': len(scores),
                        'mean': float(scores.mean()),
                        'median': float(scores.median()),
                        'std': float(scores.std()),
                        'min': float(scores.min()),
                        'max': float(scores.max()),
                        'p25': float(scores.quantile(0.25)),
                        'p75': float(scores.quantile(0.75)),
                    }

            analysis[seg_col] = segment_stats

        self.segments = analysis
        return analysis

    def risk_profile_comparison(
        self,
        df: pd.DataFrame,
        score_column: str,
        risk_thresholds: Optional[Dict] = None,
    ) -> Dict:
        """
        Categorize physicians into risk profiles.

        Args:
            df: Dataframe with scores
            score_column: Score column name
            risk_thresholds: Custom thresholds (default: 1-3 low/med/high)

        Returns:
            Risk profile statistics
        """
        if risk_thresholds is None:
            risk_thresholds = {
                'low': (1.0, 4.0),
                'medium': (4.0, 7.0),
                'high': (7.0, 10.0),
            }

        profiles = {}
        scores = df[score_column].dropna()

        for risk_level, (lower, upper) in risk_thresholds.items():
            in_range = ((scores >= lower) & (scores < upper)).sum()
            pct = (in_range / len(scores) * 100) if len(scores) > 0 else 0

            profiles[risk_level] = {
                'count': int(in_range),
                'percentage': float(pct),
                'range': [lower, upper],
            }

        return {
            'risk_profiles': profiles,
            'total_physicians': len(scores),
        }

    def loss_correlation_by_segment(
        self,
        df: pd.DataFrame,
        score_column: str,
        loss_column: str,
        segment_column: str,
    ) -> Dict:
        """
        Correlate scores to loss experience by segment.

        Args:
            df: Dataframe with scores and loss
            score_column: Score column name
            loss_column: Loss amount column name
            segment_column: Segment column (specialty, state)

        Returns:
            Correlation analysis by segment
        """
        correlations = {}

        for segment_value in df[segment_column].unique():
            segment_df = df[df[segment_column] == segment_value][[score_column, loss_column]].dropna()

            if len(segment_df) > 2:
                corr, p_value = stats.spearmanr(
                    segment_df[score_column],
                    segment_df[loss_column],
                )
                correlations[str(segment_value)] = {
                    'correlation': float(corr),
                    'pvalue': float(p_value),
                    'significant': p_value < 0.05,
                    'count': len(segment_df),
                }

        return correlations

    def identify_outlier_segments(
        self,
        df: pd.DataFrame,
        score_column: str,
        segment_column: str,
        zscore_threshold: float = 2.0,
    ) -> List[Dict]:
        """
        Identify segments with unusual score distributions.

        Args:
            df: Dataframe with scores
            score_column: Score column
            segment_column: Segment column
            zscore_threshold: Z-score threshold for outliers

        Returns:
            List of outlier segments
        """
        outliers = []
        overall_mean = df[score_column].mean()
        overall_std = df[score_column].std()

        for segment_value in df[segment_column].unique():
            segment_scores = df[df[segment_column] == segment_value][score_column].dropna()

            if len(segment_scores) > 1:
                seg_mean = segment_scores.mean()
                zscore = abs((seg_mean - overall_mean) / overall_std)

                if zscore > zscore_threshold:
                    outliers.append({
                        'segment': segment_column,
                        'segment_value': str(segment_value),
                        'mean_score': float(seg_mean),
                        'overall_mean': float(overall_mean),
                        'zscore': float(zscore),
                        'count': len(segment_scores),
                        'severity': 'HIGH' if zscore > 3.0 else 'MEDIUM',
                    })

        return sorted(outliers, key=lambda x: x['zscore'], reverse=True)

    def generate_segment_report(self) -> str:
        """Generate text report of segment analysis."""
        if not self.segments:
            return "No segment analysis performed yet"

        report = "SEGMENT ANALYSIS REPORT\n"
        report += "=" * 50 + "\n\n"

        for seg_col, stats_dict in self.segments.items():
            report += f"{seg_col.upper()}\n"
            report += "-" * 30 + "\n"

            for seg_val, stats in stats_dict.items():
                report += f"\n  {seg_val}:\n"
                report += f"    Count: {stats['count']}\n"
                report += f"    Mean: {stats['mean']:.2f}\n"
                report += f"    Median: {stats['median']:.2f}\n"
                report += f"    Std Dev: {stats['std']:.2f}\n"
                report += f"    Range: [{stats['min']:.1f}, {stats['max']:.1f}]\n"

            report += "\n"

        return report
