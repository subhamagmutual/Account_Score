"""
Anomaly detection for score data.

Detects:
- Outlier scores (unusual values)
- Unusual patterns in distributions
- Anomalies within segments (specialty, state, etc.)
"""

from typing import List, Dict, Tuple
import pandas as pd
import numpy as np


class AnomalyDetector:
    """Detect anomalies in score data."""

    def __init__(self, zscore_threshold: float = 3.0):
        """
        Initialize detector.

        Args:
            zscore_threshold: Z-score threshold for outliers (default 3.0 = 99.7%)
        """
        self.zscore_threshold = zscore_threshold
        self.anomalies: List[Dict] = []

    def detect_outliers(
        self,
        series: pd.Series,
        name: str = "values",
        method: str = "zscore",
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Detect outlier values using statistical methods.

        Args:
            series: Data series
            name: Name of series (for reporting)
            method: 'zscore' or 'iqr'

        Returns:
            (outlier_mask, list_of_anomalies)
        """
        clean_data = series.dropna()

        if method == "zscore":
            zscore = np.abs((clean_data - clean_data.mean()) / clean_data.std())
            outlier_mask = zscore > self.zscore_threshold

        elif method == "iqr":
            Q1 = clean_data.quantile(0.25)
            Q3 = clean_data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outlier_mask = (clean_data < lower_bound) | (clean_data > upper_bound)

        else:
            raise ValueError(f"Unknown method: {method}")

        outliers = clean_data[outlier_mask]
        anomalies = [
            {
                'type': 'outlier',
                'method': method,
                'series': name,
                'value': float(v),
                'zscore': float((v - clean_data.mean()) / clean_data.std()) if method == "zscore" else None,
                'severity': 'WARNING',
            }
            for v in outliers.values
        ]

        return outlier_mask, anomalies

    def detect_distribution_anomalies(
        self,
        df: pd.DataFrame,
        score_column: str,
    ) -> List[Dict]:
        """
        Detect unusual distribution characteristics.

        Args:
            df: Dataframe
            score_column: Name of score column

        Returns:
            List of anomalies
        """
        anomalies = []
        scores = df[score_column].dropna()

        if len(scores) == 0:
            return anomalies

        # Check for skewness
        skewness = scores.skew()
        if abs(skewness) > 2:
            anomalies.append({
                'type': 'skewed_distribution',
                'series': score_column,
                'skewness': float(skewness),
                'severity': 'WARNING',
                'message': f"Score distribution highly skewed ({skewness:.2f})",
            })

        # Check for bimodal distribution (two peaks)
        hist, _ = np.histogram(scores, bins=20)
        if (hist > 0).sum() >= 2:
            peaks = np.where((hist > np.roll(hist, 1)) & (hist > np.roll(hist, -1)))[0]
            if len(peaks) >= 2:
                anomalies.append({
                    'type': 'bimodal_distribution',
                    'series': score_column,
                    'peak_count': len(peaks),
                    'severity': 'INFO',
                    'message': f"Potential bimodal distribution ({len(peaks)} peaks detected)",
                })

        return anomalies

    def detect_segment_anomalies(
        self,
        df: pd.DataFrame,
        score_column: str,
        segment_column: str,
    ) -> List[Dict]:
        """
        Detect anomalies within segments (e.g., by specialty, state).

        Args:
            df: Dataframe
            score_column: Name of score column
            segment_column: Column to segment by

        Returns:
            List of anomalies
        """
        anomalies = []

        for segment_value in df[segment_column].unique():
            segment_scores = df[df[segment_column] == segment_value][score_column].dropna()

            if len(segment_scores) < 5:
                continue

            # Compare segment mean to overall mean
            overall_mean = df[score_column].dropna().mean()
            segment_mean = segment_scores.mean()
            zscore = abs((segment_mean - overall_mean) / df[score_column].dropna().std())

            if zscore > 2:
                anomalies.append({
                    'type': 'segment_anomaly',
                    'segment': segment_column,
                    'segment_value': str(segment_value),
                    'segment_mean': float(segment_mean),
                    'overall_mean': float(overall_mean),
                    'zscore': float(zscore),
                    'severity': 'WARNING',
                    'message': f"{segment_column}={segment_value}: mean {segment_mean:.2f} vs overall {overall_mean:.2f}",
                })

        return anomalies

    def detect_missing_segments(
        self,
        df: pd.DataFrame,
        segment_column: str,
        expected_segments: List,
    ) -> List[Dict]:
        """
        Detect if expected segments are missing.

        Args:
            df: Dataframe
            segment_column: Column to check
            expected_segments: Expected values

        Returns:
            List of missing segment anomalies
        """
        anomalies = []
        found_segments = set(df[segment_column].unique())
        expected_set = set(expected_segments)
        missing = expected_set - found_segments

        for segment in missing:
            anomalies.append({
                'type': 'missing_segment',
                'segment': segment_column,
                'segment_value': str(segment),
                'severity': 'WARNING',
                'message': f"Expected {segment_column}={segment} not found in data",
            })

        return anomalies

    def generate_report(self) -> Dict:
        """Generate anomaly report."""
        anomaly_count = len(self.anomalies)
        blocker_count = sum(1 for a in self.anomalies if a.get('severity') == 'BLOCKER')
        warning_count = sum(1 for a in self.anomalies if a.get('severity') == 'WARNING')

        return {
            'total_anomalies': anomaly_count,
            'blockers': blocker_count,
            'warnings': warning_count,
            'has_issues': anomaly_count > 0,
            'anomalies': self.anomalies,
        }
