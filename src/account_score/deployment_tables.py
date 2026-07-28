"""Deployment Tables: Score band summary tables for business interpretation.

Generates per-variable deployment tables showing:
- Score band (1-10 after rescaling)
- Bin boundaries (from fitted thresholds or mean-anchored)
- Policy count per band
- Premium sum per band
- Weighted average KPI per band

Also generates composite-level summary tables.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional


def create_deployment_table(
    df: pd.DataFrame,
    var_name: str,
    thresholds: Optional[Dict[str, Any]] = None,
    portfolio_mean: Optional[float] = None,
    binning_method: str = "quantile",
    sub_score_max: int = 30,
    premium_col: str = "WRTN_PREM_AMT_ITD_BURNED"
) -> pd.DataFrame:
    """
    Create a deployment table for a single variable.

    Supports two modes:
    - Threshold-based (Account_Score default): uses fitted bin boundaries from JSON
    - Mean-anchored (dynamic mode): computes boundaries from portfolio mean

    Args:
        df: Scored DataFrame with score_* and kpi_* columns
        var_name: Variable name
        thresholds: Fitted bin thresholds dict (from binning_thresholds.json)
        portfolio_mean: Portfolio mean (for mean-anchored mode)
        binning_method: Binning method used
        sub_score_max: Max sub-score (30 for threshold-based, 10 for dynamic)
        premium_col: Premium column for summary stats

    Returns:
        DataFrame with Score, Lower_Bound, Upper_Bound, Policy_Count, Premium_Sum, Avg_KPI
    """
    score_col = f"score_{var_name}"
    kpi_col = f"kpi_{var_name}"

    if score_col not in df.columns:
        return pd.DataFrame()

    # Rescale to 1-10 bands for display
    n_display_bands = 10

    if binning_method in ("mean_anchored", "reciprocal") and portfolio_mean:
        # Mean-anchored: boundaries computed from portfolio mean
        boundaries = _get_mean_anchored_boundaries(portfolio_mean, binning_method, n_display_bands)
    elif thresholds and var_name in thresholds:
        # Threshold-based: summarize fitted bins into 10 display bands
        boundaries = _get_threshold_boundaries(thresholds[var_name], sub_score_max, n_display_bands)
    else:
        # Fallback: just group by rescaled score
        boundaries = [{"score": i, "lower_bound": None, "upper_bound": None}
                      for i in range(1, n_display_bands + 1)]

    # Map sub-scores (1-30) to display bands (1-10)
    score_series = df[score_col].copy()
    if sub_score_max > 10:
        display_scores = _rescale_to_bands(score_series, sub_score_max, n_display_bands)
    else:
        display_scores = score_series

    rows = []
    for band_info in boundaries:
        score = band_info["score"]
        band_df = df[display_scores == score]

        policy_count = len(band_df)
        premium_sum = band_df[premium_col].sum() if premium_col in band_df.columns else 0
        avg_kpi = band_df[kpi_col].mean() if kpi_col in band_df.columns and len(band_df) > 0 else np.nan

        rows.append({
            "Score": score,
            "Lower_Bound": band_info["lower_bound"],
            "Upper_Bound": band_info["upper_bound"],
            "Policy_Count": policy_count,
            "Premium_Sum": round(premium_sum, 2),
            "Avg_KPI": round(avg_kpi, 6) if pd.notna(avg_kpi) else None
        })

    return pd.DataFrame(rows)


def create_all_deployment_tables(
    df: pd.DataFrame,
    scoring_weights: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
    portfolio_means: Optional[Dict[str, float]] = None,
    binning_params: Optional[Dict[str, Any]] = None,
    sub_score_max: int = 30,
    premium_col: str = "WRTN_PREM_AMT_ITD_BURNED"
) -> Dict[str, pd.DataFrame]:
    """
    Create deployment tables for all scored variables.

    Args:
        df: Scored DataFrame
        scoring_weights: Scoring weights config (all dimensions)
        thresholds: Fitted bin thresholds (for threshold-based mode)
        portfolio_means: Dict of portfolio means (for dynamic mode)
        binning_params: Binning parameters with methods_by_variable
        sub_score_max: Max sub-score scale
        premium_col: Premium column name

    Returns:
        Dict of {variable_name: deployment_table_DataFrame}
    """
    tables = {}
    methods = binning_params.get("methods_by_variable", {}) if binning_params else {}

    for dim_key in ["adequacy_sub_scores", "capacity_sub_scores",
                    "appetite_sub_scores", "environment_sub_scores"]:
        for var_name, var_config in scoring_weights.get(dim_key, {}).items():
            method = methods.get(var_name, "quantile")

            if method == "categorical":
                tables[var_name] = _create_categorical_deployment_table(
                    df, var_name, premium_col
                )
                continue

            mean = portfolio_means.get(var_name, 0) if portfolio_means else 0

            table = create_deployment_table(
                df, var_name,
                thresholds=thresholds,
                portfolio_mean=mean if mean > 0 else None,
                binning_method=method,
                sub_score_max=sub_score_max,
                premium_col=premium_col
            )

            if not table.empty:
                tables[var_name] = table

    return tables


def create_composite_deployment_table(
    df: pd.DataFrame,
    premium_col: str = "WRTN_PREM_AMT_ITD_BURNED"
) -> pd.DataFrame:
    """Create summary table for the composite score distribution."""
    if "composite_score" not in df.columns:
        return pd.DataFrame()

    rows = []
    for score in range(1, 11):
        band_df = df[df["composite_score"] == score]
        policy_count = len(band_df)
        premium_sum = band_df[premium_col].sum() if premium_col in band_df.columns else 0
        pct_of_total = (policy_count / len(df) * 100) if len(df) > 0 else 0

        adequacy = band_df["adequacy_score"].mean() if "adequacy_score" in band_df.columns else None
        capacity = band_df["capacity_score"].mean() if "capacity_score" in band_df.columns else None
        appetite = band_df["appetite_score"].mean() if "appetite_score" in band_df.columns else None
        environment = band_df["environment_score"].mean() if "environment_score" in band_df.columns else None

        rows.append({
            "Composite_Score": score,
            "Policy_Count": policy_count,
            "Pct_of_Total": round(pct_of_total, 1),
            "Premium_Sum": round(premium_sum, 2),
            "Avg_Adequacy": round(adequacy, 2) if pd.notna(adequacy) else None,
            "Avg_Capacity": round(capacity, 2) if pd.notna(capacity) else None,
            "Avg_Appetite": round(appetite, 2) if pd.notna(appetite) else None,
            "Avg_Environment": round(environment, 2) if pd.notna(environment) else None,
        })

    return pd.DataFrame(rows)


# ---- Private helpers ----

def _rescale_to_bands(scores: pd.Series, sub_score_max: int, n_bands: int) -> pd.Series:
    """Rescale sub-scores (1-30) to display bands (1-10)."""
    valid = scores >= 1
    result = pd.Series(0, index=scores.index, dtype=int)
    result[valid] = np.clip(
        np.ceil(scores[valid] / sub_score_max * n_bands).astype(int),
        1, n_bands
    )
    return result


def _get_threshold_boundaries(
    bin_entries: List[Dict], sub_score_max: int, n_display_bands: int
) -> List[Dict[str, Any]]:
    """Summarize fitted bin thresholds into n_display_bands display bands."""
    # Group bin entries by display band
    boundaries = []
    bins_per_band = sub_score_max / n_display_bands

    for band in range(1, n_display_bands + 1):
        score_low = int((band - 1) * bins_per_band) + 1
        score_high = int(band * bins_per_band)

        # Find boundaries for this band range
        band_entries = [e for e in bin_entries
                       if "score" in e and score_low <= e.get("score", 0) <= score_high]

        if band_entries:
            lower = min(e.get("lower_bound", 0) for e in band_entries
                       if "lower_bound" in e)
            upper = max(e.get("upper_bound", 0) for e in band_entries
                       if "upper_bound" in e)
        else:
            lower = None
            upper = None

        boundaries.append({
            "score": band,
            "lower_bound": round(lower, 4) if lower is not None else None,
            "upper_bound": round(upper, 4) if upper is not None else None
        })

    return boundaries


def _get_mean_anchored_boundaries(
    portfolio_mean: float, method: str, n_bands: int, anchor_band: float = 4.5
) -> List[Dict[str, Any]]:
    """Compute mean-anchored bin boundaries for deployment table display."""
    boundaries = []

    if method == "reciprocal":
        lower_5 = (anchor_band / 5.0) * portfolio_mean
        reciprocal_base = (1.0 / lower_5) / 5.0

        thresholds = []
        for i in range(1, n_bands + 1):
            denom = reciprocal_base * i
            thresholds.append(1.0 / denom if denom > 0 else np.inf)

        for i in range(n_bands):
            score = i + 1
            upper = thresholds[i] if i < len(thresholds) else np.inf
            lower = thresholds[i + 1] if i + 1 < len(thresholds) else 0
            boundaries.append({
                "score": score,
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4) if upper != np.inf else 999999
            })
    else:  # mean_anchored (bin_All style)
        band_width = portfolio_mean / anchor_band
        for i in range(n_bands):
            lower = round(i * band_width, 4)
            upper = round((i + 1) * band_width, 4) if i < n_bands - 1 else 999999
            boundaries.append({
                "score": i + 1,
                "lower_bound": lower,
                "upper_bound": upper
            })

    return boundaries


def _create_categorical_deployment_table(
    df: pd.DataFrame, var_name: str, premium_col: str
) -> pd.DataFrame:
    """Create deployment table for categorical (tier-based) variables."""
    score_col = f"score_{var_name}"
    if score_col not in df.columns:
        return pd.DataFrame()

    # Rescale from 1-30 to 1-10 for display
    rows = []
    for score in range(1, 11):
        # Map display band back to sub-score range
        score_low = (score - 1) * 3 + 1
        score_high = score * 3
        band_df = df[(df[score_col] >= score_low) & (df[score_col] <= score_high)]

        policy_count = len(band_df)
        premium_sum = band_df[premium_col].sum() if premium_col in band_df.columns else 0

        rows.append({
            "Score": score,
            "Lower_Bound": "Tier lookup",
            "Upper_Bound": "Tier lookup",
            "Policy_Count": policy_count,
            "Premium_Sum": round(premium_sum, 2),
            "Avg_KPI": None
        })

    return pd.DataFrame(rows)
