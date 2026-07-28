"""Variable Binning: Fit bins from data and apply bin thresholds to score variables.

Two main classes:
- BinFitter: Analyzes data distribution and auto-computes bin thresholds (1-30 scale)
- BinApplier: Takes JSON thresholds and applies them to data (returns scores)

The fit process generates a JSON config that can be manually tweaked before applying.
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple


class BinFitter:
    """Fits binning thresholds from data distributions."""

    def __init__(self, n_bins: int = 30, portfolio_avg_score: int = 15):
        """
        Args:
            n_bins: Number of score levels (default 30, i.e., scores 1 to 30)
            portfolio_avg_score: Which score level should align with portfolio average
        """
        self.n_bins = n_bins
        self.portfolio_avg_score = portfolio_avg_score

    def fit_variable(
        self,
        series: pd.Series,
        method: str = "quantile",
        higher_is_worse: bool = True,
        name: str = "",
        portfolio_mean: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Compute bin thresholds for a single variable.
        
        Args:
            series: Data series (NaN excluded)
            method: "quantile", "equal_width", "log_scale", "u_shaped", "mean_anchored", "reciprocal"
            higher_is_worse: If True, higher values get higher (worse) scores
            name: Variable name for logging
            portfolio_mean: Portfolio weighted mean (required for mean_anchored/reciprocal)
        
        Returns:
            List of bin entries (JSON-serializable), ordered by score 1 to n_bins.
        """
        clean = series.dropna()
        if len(clean) == 0:
            return self._empty_bins(name)

        if method == "quantile":
            return self._fit_quantile(clean, higher_is_worse, name)
        elif method == "equal_width":
            return self._fit_equal_width(clean, higher_is_worse, name)
        elif method == "log_scale":
            return self._fit_log_scale(clean, higher_is_worse, name)
        elif method == "u_shaped":
            return self._fit_u_shaped(clean, name)
        elif method == "mean_anchored":
            return self._fit_mean_anchored(clean, portfolio_mean, name)
        elif method == "reciprocal":
            return self._fit_reciprocal(clean, portfolio_mean, name)
        else:
            return self._fit_quantile(clean, higher_is_worse, name)

    def _fit_quantile(self, data: pd.Series, higher_is_worse: bool, name: str) -> List[Dict]:
        """Quantile-based binning: equal number of records per bin."""
        percentiles = np.linspace(0, 100, self.n_bins + 1)
        boundaries = np.percentile(data, percentiles)
        boundaries = np.unique(boundaries)

        # If not enough unique values, create simple min/max range
        if len(boundaries) < 3:
            data_min = data.min()
            data_max = data.max()
            if data_min == data_max:
                # Truly degenerate: all same value, assign score based on value
                return [
                    {"score": self.portfolio_avg_score, "lower_bound": float(data_min),
                     "lower_operator": ">=", "upper_bound": float(data_max), "upper_operator": "<="},
                    {"score": -1, "lower_operator": "default"}
                ]
            # Just two boundaries: split into two halves
            mid = (data_min + data_max) / 2
            boundaries = np.array([data_min, mid, data_max])

        return self._boundaries_to_bins(boundaries, higher_is_worse, name)

    def _fit_equal_width(self, data: pd.Series, higher_is_worse: bool, name: str) -> List[Dict]:
        """Equal-width binning centered on median (portfolio average)."""
        median = data.median()
        p5 = data.quantile(0.05)
        p95 = data.quantile(0.95)

        # Compute bin width from the interquartile range
        range_span = p95 - p5
        if range_span == 0:
            # Degenerate case: all values clustered, use full data range
            data_min = data.min()
            data_max = data.max()
            if data_min == data_max:
                return [
                    {"score": self.portfolio_avg_score, "lower_bound": float(data_min),
                     "lower_operator": ">=", "upper_bound": float(data_max), "upper_operator": "<="},
                    {"score": -1, "lower_operator": "default"}
                ]
            # Use full range instead
            range_span = data_max - data_min

        bin_width = range_span / (self.n_bins - 2)  # leave room for tails

        # Center on median: score portfolio_avg_score corresponds to median
        boundaries = []
        for i in range(self.n_bins + 1):
            offset = i - self.portfolio_avg_score
            boundaries.append(median + offset * bin_width)

        boundaries = sorted(boundaries)
        # Ensure boundaries span the actual data range
        data_min = data.min()
        data_max = data.max()
        if boundaries[0] > data_min:
            boundaries[0] = data_min
        if boundaries[-1] < data_max:
            boundaries[-1] = data_max

        return self._boundaries_to_bins(boundaries, higher_is_worse, name)

    def _fit_log_scale(self, data: pd.Series, higher_is_worse: bool, name: str) -> List[Dict]:
        """Log-scale binning for right-skewed distributions."""
        # Only use positive values for log
        positive = data[data > 0]
        if len(positive) == 0:
            return self._fit_equal_width(data, higher_is_worse, name)

        log_data = np.log1p(positive)
        percentiles = np.linspace(0, 100, self.n_bins + 1)
        log_boundaries = np.percentile(log_data, percentiles)
        boundaries = np.expm1(log_boundaries)
        boundaries = np.unique(np.round(boundaries, 4))

        if len(boundaries) < 4:
            return self._fit_quantile(data, higher_is_worse, name)

        return self._boundaries_to_bins(boundaries, higher_is_worse, name)

    def _fit_u_shaped(self, data: pd.Series, name: str) -> List[Dict]:
        """
        U-shaped binning: mid-range values get best score, extremes get worst.
        Used for age, years-since-graduation where both very young and very old are riskier.
        """
        median = data.median()
        # Distance from optimal (median) determines score
        distance = (data - median).abs()
        # Use quantile-based on distance, then map back
        return self._fit_quantile(distance, higher_is_worse=True, name=name + "_distance")

    def _fit_mean_anchored(self, data: pd.Series, portfolio_mean: Optional[float], name: str) -> List[Dict]:
        """
        Mean-anchored equal-width binning (PAS bin_All concept).

        Creates equal-width bins where the portfolio mean falls at band ~4.5 (on 1-10 scale)
        or proportionally on the 1-30 scale. Higher values get higher (worse) scores.

        Formula: band_width = portfolio_mean / anchor_band
        """
        if portfolio_mean is None or portfolio_mean <= 0:
            # Fall back to equal_width if no mean available
            return self._fit_equal_width(data, higher_is_worse=True, name=name)

        # Anchor band on 1-n_bins scale (proportional to 4.5/10)
        anchor_band = self.n_bins * 4.5 / 10.0
        band_width = portfolio_mean / anchor_band

        # Create bin edges
        bin_edges = [round(i * band_width, 6) for i in range(self.n_bins)]
        bin_edges.append(float(max(data.max() * 1.1, self.n_bins * band_width)))

        bins = []
        for i in range(self.n_bins):
            entry = {
                "score": i + 1,
                "lower_bound": bin_edges[i],
                "lower_operator": ">=" if i == 0 else ">",
                "upper_bound": bin_edges[i + 1],
                "upper_operator": "<=" if i == self.n_bins - 1 else "<"
            }
            bins.append(entry)

        bins.append({"score": self.n_bins, "lower_operator": "default"})
        return bins

    def _fit_reciprocal(self, data: pd.Series, portfolio_mean: Optional[float], name: str) -> List[Dict]:
        """
        Reciprocal-spacing binning for inverse-relationship metrics (PAS bin_RA concept).

        For metrics where higher raw values are BETTER (loss_free_years, tenure, hospital_rating).
        Creates non-uniform bands with reciprocal spacing anchored at the portfolio mean.
        Higher raw values → lower score (better). Lower raw values → higher score (worse).
        """
        if portfolio_mean is None or portfolio_mean <= 0:
            return self._fit_quantile(data, higher_is_worse=False, name=name)

        anchor_band = self.n_bins * 4.5 / 10.0
        lower_anchor = (anchor_band / 5.0) * portfolio_mean

        if lower_anchor <= 0:
            return self._fit_quantile(data, higher_is_worse=False, name=name)

        reciprocal_base = (1.0 / lower_anchor) / 5.0

        # Generate thresholds (decreasing)
        thresholds = []
        for i in range(1, self.n_bins + 1):
            denom = reciprocal_base * i
            thresholds.append(1.0 / denom if denom > 0 else float('inf'))

        # Build bins: score 1 = best (highest values), score n_bins = worst (lowest values)
        bins = []
        for i in range(self.n_bins):
            score = i + 1
            upper = thresholds[i] if i < len(thresholds) else float('inf')
            lower = thresholds[i + 1] if i + 1 < len(thresholds) else 0

            entry = {
                "score": score,
                "lower_bound": round(lower, 6),
                "lower_operator": ">=" if i == self.n_bins - 1 else ">",
                "upper_bound": round(upper, 6),
                "upper_operator": "<=" if i == 0 else "<"
            }
            bins.append(entry)

        bins.append({"score": self.n_bins, "lower_operator": "default"})
        return bins

    def _boundaries_to_bins(
        self,
        boundaries: np.ndarray,
        higher_is_worse: bool,
        name: str
    ) -> List[Dict]:
        """Convert sorted boundaries array into scored bin entries."""
        bins = []
        n_actual = len(boundaries) - 1

        for i in range(n_actual):
            lower = float(boundaries[i])
            upper = float(boundaries[i + 1])

            if higher_is_worse:
                score = int(np.round(1 + (i / max(n_actual - 1, 1)) * (self.n_bins - 1)))
            else:
                score = int(np.round(self.n_bins - (i / max(n_actual - 1, 1)) * (self.n_bins - 1)))

            entry = {
                "score": score,
                "lower_bound": round(lower, 6),
                "lower_operator": ">=" if i == 0 else ">",
                "upper_bound": round(upper, 6),
                "upper_operator": "<=" if i == n_actual - 1 else "<"
            }
            bins.append(entry)

        # Add default entry for out-of-range values
        bins.append({"score": -1, "lower_operator": "default"})
        return bins

    def _empty_bins(self, name: str) -> List[Dict]:
        """Return a single default bin when no data is available."""
        return [{"score": -1, "lower_operator": "default", "note": f"No data for {name}"}]

    def fit_all(
        self,
        df: pd.DataFrame,
        variable_configs: Dict[str, Dict[str, Any]],
        binning_params: Dict[str, Any],
        portfolio_means: Optional[Dict[str, float]] = None
    ) -> Dict[str, List[Dict]]:
        """
        Fit bins for all configured variables.
        
        Args:
            df: Data DataFrame with KPI columns
            variable_configs: Dict from scoring_weights (all sub_scores merged)
            binning_params: Binning method settings from pipeline_params
            portfolio_means: Dict of portfolio means per variable (for mean_anchored/reciprocal)
        
        Returns:
            Dict of {variable_name: [bin_entries]} ready to save as JSON.
        """
        methods = binning_params.get("methods_by_variable", {})
        default_method = binning_params.get("default_method", "quantile")
        if portfolio_means is None:
            portfolio_means = {}

        all_bins = {}
        for var_name, var_config in variable_configs.items():
            # Determine source column
            kpi_col = f"kpi_{var_name}"
            source_col = var_config.get("source_column")

            if kpi_col in df.columns:
                series = df[kpi_col]
            elif source_col and source_col in df.columns:
                series = df[source_col]
            else:
                print(f"  SKIP fit for {var_name}: no data column found")
                continue

            method = methods.get(var_name, default_method)

            # Determine direction (for most metrics, higher = worse)
            higher_is_worse = True
            if var_config.get("invert_score", False):
                higher_is_worse = False

            # Pass portfolio mean for dynamic methods
            mean = portfolio_means.get(var_name)

            bins = self.fit_variable(
                series, method=method, higher_is_worse=higher_is_worse,
                name=var_name, portfolio_mean=mean
            )
            all_bins[var_name] = bins
            print(f"  Fitted {var_name}: {len(bins)-1} bins ({method})")

        return all_bins


class BinApplier:
    """Applies saved bin thresholds to data, returning integer scores."""

    def __init__(self, thresholds: Dict[str, List[Dict]], score_range: Tuple[int, int] = (1, 30)):
        """
        Args:
            thresholds: Dict of {variable_name: [bin_entries]} from JSON config
            score_range: (min_score, max_score) for capping
        """
        self.thresholds = thresholds
        self.score_min, self.score_max = score_range

    def apply_single(self, value: float, variable: str) -> int:
        """
        Bin a single value for a given variable.
        Returns the integer score (1 to max), or -1 if no match/missing.
        """
        if pd.isna(value):
            return -1

        if variable not in self.thresholds:
            return -1

        bins = self.thresholds[variable]
        for entry in bins:
            if entry.get("lower_operator") == "default":
                return entry.get("score", -1)
            if self._matches(value, entry):
                return entry["score"]

        return -1

    def apply_series(self, series: pd.Series, variable: str) -> pd.Series:
        """
        Vectorized binning for an entire column.
        Returns a Series of integer scores.
        """
        if variable not in self.thresholds:
            return pd.Series(-1, index=series.index, dtype=int)

        bins = self.thresholds[variable]
        result = pd.Series(-1, index=series.index, dtype=int)

        for entry in bins:
            if entry.get("lower_operator") == "default":
                continue
            mask = self._build_mask(series, entry)
            # Only assign where not already assigned (first-match-wins)
            unassigned = result == -1
            result[unassigned & mask] = entry["score"]

        return result

    def apply_all(self, df: pd.DataFrame, variable_configs: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply binning to all configured variables in the DataFrame.
        
        Adds columns named 'score_{variable_name}' with integer scores.
        """
        df = df.copy()
        for var_name in variable_configs.keys():
            if var_name not in self.thresholds:
                continue

            # Determine source column
            kpi_col = f"kpi_{var_name}"
            source_col = variable_configs[var_name].get("source_column")

            if kpi_col in df.columns:
                series = df[kpi_col]
            elif source_col and source_col in df.columns:
                series = df[source_col]
            else:
                continue

            score_col = f"score_{var_name}"
            df[score_col] = self.apply_series(series, var_name)
            valid = (df[score_col] > 0).sum()
            print(f"  Scored {var_name}: {valid:,} valid scores")

        return df

    def _matches(self, value: float, entry: Dict) -> bool:
        """Check if a value matches a single bin entry."""
        # Check lower bound
        if "lower_bound" in entry:
            lb = entry["lower_bound"]
            op = entry.get("lower_operator", ">=")
            if op == ">=" and not (value >= lb):
                return False
            elif op == ">" and not (value > lb):
                return False
            elif op == "=" and not (value == lb):
                return False
        # Check upper bound
        if "upper_bound" in entry:
            ub = entry["upper_bound"]
            op = entry.get("upper_operator", "<=")
            if op == "<=" and not (value <= ub):
                return False
            elif op == "<" and not (value < ub):
                return False
        return True

    def _build_mask(self, series: pd.Series, entry: Dict) -> pd.Series:
        """Build a boolean mask for vectorized bin matching."""
        mask = pd.Series(True, index=series.index)

        if "lower_bound" in entry:
            lb = entry["lower_bound"]
            op = entry.get("lower_operator", ">=")
            if op == ">=":
                mask &= series >= lb
            elif op == ">":
                mask &= series > lb
            elif op == "=":
                mask &= series == lb

        if "upper_bound" in entry:
            ub = entry["upper_bound"]
            op = entry.get("upper_operator", "<=")
            if op == "<=":
                mask &= series <= ub
            elif op == "<":
                mask &= series < ub

        # Handle NaN: NaN should not match any bin
        mask &= series.notna()
        return mask
