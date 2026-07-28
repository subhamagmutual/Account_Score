"""
Population Stability Index (PSI) calculation.

PSI measures population drift between two time periods:
- < 0.10: No significant change
- 0.10-0.25: Small change (investigate)
- > 0.25: Significant change (possible data quality issue or model re-fitting needed)

Formula: PSI = Σ (expected% - actual%) * ln(expected% / actual%)
"""

from typing import List, Tuple, Dict
import pandas as pd
import numpy as np


class PSICalculator:
    """Calculate Population Stability Index."""

    @staticmethod
    def calculate(
        baseline_values: pd.Series,
        current_values: pd.Series,
        n_bins: int = 10,
    ) -> float:
        """
        Calculate PSI between baseline and current populations.

        Args:
            baseline_values: Reference period scores (e.g., development data)
            current_values: Current period scores (e.g., production data)
            n_bins: Number of bins for discretization

        Returns:
            PSI value (higher = more drift)
        """
        # Clean values
        baseline = baseline_values.dropna().values
        current = current_values.dropna().values

        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        # Define bins using baseline
        min_val = min(baseline.min(), current.min())
        max_val = max(baseline.max(), current.max())
        bins = np.linspace(min_val, max_val, n_bins + 1)

        # Histogram baseline and current
        baseline_dist, _ = np.histogram(baseline, bins=bins)
        current_dist, _ = np.histogram(current, bins=bins)

        # Convert to percentages
        baseline_pct = baseline_dist / baseline_dist.sum()
        current_pct = current_dist / current_dist.sum()

        # Calculate PSI
        psi = 0.0
        for b, c in zip(baseline_pct, current_pct):
            # Avoid division by zero
            if b == 0 or c == 0:
                b = max(b, 0.0001)
                c = max(c, 0.0001)

            psi += (c - b) * np.log(c / b)

        return float(abs(psi))

    @staticmethod
    def calculate_by_dimension(
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame,
        score_columns: List[str],
        n_bins: int = 10,
    ) -> Dict[str, float]:
        """
        Calculate PSI for multiple score columns.

        Args:
            baseline_df: Baseline dataframe
            current_df: Current dataframe
            score_columns: List of score column names
            n_bins: Number of bins

        Returns:
            Dictionary of PSI values by column
        """
        psi_values = {}

        for col in score_columns:
            if col in baseline_df.columns and col in current_df.columns:
                psi = PSICalculator.calculate(
                    baseline_df[col],
                    current_df[col],
                    n_bins=n_bins,
                )
                psi_values[col] = psi

        return psi_values

    @staticmethod
    def calculate_by_segment(
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame,
        score_column: str,
        segment_column: str,
        n_bins: int = 10,
    ) -> Dict[str, float]:
        """
        Calculate PSI for each segment (e.g., by specialty, state).

        Args:
            baseline_df: Baseline dataframe
            current_df: Current dataframe
            score_column: Name of score column
            segment_column: Name of column to segment by
            n_bins: Number of bins

        Returns:
            Dictionary of PSI values by segment value
        """
        psi_by_segment = {}

        for segment_value in baseline_df[segment_column].unique():
            baseline_seg = baseline_df[
                baseline_df[segment_column] == segment_value
            ][score_column]

            current_seg = current_df[
                current_df[segment_column] == segment_value
            ][score_column]

            if len(baseline_seg) > 0 and len(current_seg) > 0:
                psi = PSICalculator.calculate(
                    baseline_seg,
                    current_seg,
                    n_bins=n_bins,
                )
                psi_by_segment[segment_value] = psi

        return psi_by_segment

    @staticmethod
    def interpret_psi(psi_value: float) -> str:
        """
        Interpret PSI value.

        Args:
            psi_value: PSI value

        Returns:
            Interpretation string
        """
        if psi_value < 0.10:
            return "No significant change"
        elif psi_value < 0.25:
            return "Small change (monitor)"
        else:
            return "Significant change (investigate)"

    @staticmethod
    def alert_if_high(psi_value: float, threshold: float = 0.25) -> Tuple[bool, str]:
        """
        Check if PSI exceeds threshold.

        Args:
            psi_value: PSI value
            threshold: Alert threshold (default 0.25)

        Returns:
            (should_alert, message)
        """
        if psi_value > threshold:
            return True, f"PSI {psi_value:.4f} exceeds threshold {threshold}"
        return False, f"PSI {psi_value:.4f} within acceptable range"
