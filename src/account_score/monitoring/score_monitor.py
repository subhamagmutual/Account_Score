"""
Score distribution monitoring - track and compare score distributions over time.

Provides metrics for:
- Overall distribution (mean, std, percentiles)
- Component-specific metrics
- Gini coefficient (discrimination)
- Alerts for significant shifts
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import json
import pandas as pd
import numpy as np


@dataclass
class DistributionMetrics:
    """Distribution metrics for a set of scores."""

    mean: float
    median: float
    std: float
    min: float
    max: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    gini: float
    count: int
    null_count: int

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict):
        """Create from dictionary."""
        return cls(**d)


class ScoreMonitor:
    """Monitor score distributions and detect shifts."""

    def __init__(self, alert_threshold: float = 0.05):
        """
        Initialize monitor.

        Args:
            alert_threshold: Alert if metric changes by >this fraction (default 5%)
        """
        self.alert_threshold = alert_threshold
        self.baseline: Optional[Dict[str, DistributionMetrics]] = None
        self.history: List[Dict] = []

    def calculate_metrics(self, scores: pd.Series, name: str = "scores") -> DistributionMetrics:
        """
        Calculate distribution metrics for a series of scores.

        Args:
            scores: Series of score values
            name: Name of the score series

        Returns:
            DistributionMetrics object
        """
        scores_clean = scores.dropna()

        return DistributionMetrics(
            mean=float(scores_clean.mean()),
            median=float(scores_clean.median()),
            std=float(scores_clean.std()),
            min=float(scores_clean.min()),
            max=float(scores_clean.max()),
            p25=float(scores_clean.quantile(0.25)),
            p50=float(scores_clean.quantile(0.50)),
            p75=float(scores_clean.quantile(0.75)),
            p90=float(scores_clean.quantile(0.90)),
            p95=float(scores_clean.quantile(0.95)),
            gini=self._calculate_gini(scores_clean),
            count=len(scores_clean),
            null_count=scores.isna().sum(),
        )

    def analyze_dataframe(self, df: pd.DataFrame, score_columns: List[str]) -> Dict[str, DistributionMetrics]:
        """
        Analyze multiple score columns in a dataframe.

        Args:
            df: DataFrame with score columns
            score_columns: List of column names to analyze

        Returns:
            Dictionary of metrics by column
        """
        metrics = {}
        for col in score_columns:
            if col in df.columns:
                metrics[col] = self.calculate_metrics(df[col], col)
        return metrics

    def set_baseline(self, metrics: Dict[str, DistributionMetrics]):
        """Set baseline distribution metrics."""
        self.baseline = metrics

    def load_baseline(self, filepath: str):
        """Load baseline from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.baseline = {
            name: DistributionMetrics.from_dict(m)
            for name, m in data.items()
        }

    def save_baseline(self, filepath: str):
        """Save baseline to JSON file."""
        if self.baseline is None:
            raise ValueError("No baseline set")
        data = {name: m.to_dict() for name, m in self.baseline.items()}
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def compare_to_baseline(self, current: Dict[str, DistributionMetrics]) -> Dict:
        """
        Compare current metrics to baseline.

        Returns:
            Dictionary with alerts and percentage changes
        """
        if self.baseline is None:
            raise ValueError("No baseline set for comparison")

        alerts = []
        changes = {}

        for name, curr_metric in current.items():
            if name not in self.baseline:
                continue

            baseline_metric = self.baseline[name]

            # Compare each metric
            metric_changes = {
                'mean': self._pct_change(baseline_metric.mean, curr_metric.mean),
                'std': self._pct_change(baseline_metric.std, curr_metric.std),
                'p25': self._pct_change(baseline_metric.p25, curr_metric.p25),
                'p50': self._pct_change(baseline_metric.p50, curr_metric.p50),
                'p75': self._pct_change(baseline_metric.p75, curr_metric.p75),
                'gini': self._pct_change(baseline_metric.gini, curr_metric.gini),
            }

            changes[name] = metric_changes

            # Check for alerts
            for metric_name, pct_change in metric_changes.items():
                if abs(pct_change) > self.alert_threshold:
                    alerts.append({
                        'score': name,
                        'metric': metric_name,
                        'baseline': getattr(baseline_metric, metric_name),
                        'current': getattr(curr_metric, metric_name),
                        'pct_change': pct_change,
                        'severity': 'WARNING' if abs(pct_change) < 0.10 else 'CRITICAL',
                    })

        return {
            'alerts': alerts,
            'changes': changes,
            'total_alerts': len(alerts),
        }

    @staticmethod
    def _pct_change(baseline: float, current: float) -> float:
        """Calculate percentage change."""
        if baseline == 0:
            return 0.0
        return (current - baseline) / abs(baseline)

    @staticmethod
    def _calculate_gini(values: pd.Series) -> float:
        """
        Calculate Gini coefficient for score distribution.

        Gini measures inequality/discrimination:
        - 0.0: Perfect equality (all same value)
        - 1.0: Perfect inequality (one value, rest zero)
        - ~0.15+: Moderate discrimination (bands separate population)
        """
        if len(values) < 2:
            return 0.0

        # Sort and calculate cumulative sum
        sorted_vals = np.sort(values.values)
        n = len(sorted_vals)
        cum_vals = np.cumsum(sorted_vals)

        # Gini formula
        gini = (2 * np.sum((n + 1 - np.arange(1, n + 1)) * sorted_vals)) / (n * np.sum(sorted_vals)) - 1

        return float(gini)

    def add_to_history(self, timestamp: str, metrics: Dict[str, DistributionMetrics]):
        """Track metrics over time."""
        self.history.append({
            'timestamp': timestamp,
            'metrics': {name: m.to_dict() for name, m in metrics.items()},
        })

    def get_trend(self, metric_name: str, score_name: str = 'composite_score') -> List[float]:
        """Get historical trend for a metric."""
        if not self.history:
            return []

        trend = []
        for entry in self.history:
            if score_name in entry['metrics']:
                m = entry['metrics'][score_name]
                if metric_name in m:
                    trend.append(m[metric_name])

        return trend
