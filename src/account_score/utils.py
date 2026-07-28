"""Shared utility functions for the Account Scoring pipeline."""

import numpy as np
import pandas as pd


def safe_divide(numerator, denominator, default=np.nan):
    """Divide numerator by denominator, returning default where denominator is 0 or NaN."""
    if isinstance(numerator, pd.Series):
        result = pd.Series(default, index=numerator.index, dtype=float)
        valid = (denominator != 0) & denominator.notna() & numerator.notna()
        result[valid] = numerator[valid] / denominator[valid]
        return result
    else:
        if denominator is None or denominator == 0 or pd.isna(denominator):
            return default
        if numerator is None or pd.isna(numerator):
            return default
        return numerator / denominator


def cap_score(score, min_val=1, max_val=10):
    """Cap a score between min and max values."""
    if isinstance(score, pd.Series):
        return score.clip(lower=min_val, upper=max_val)
    if pd.isna(score):
        return np.nan
    return max(min_val, min(max_val, score))


def rescale_score(score, from_min=1, from_max=30, to_min=1, to_max=10):
    """Linearly rescale a score from one range to another."""
    if isinstance(score, pd.Series):
        result = to_min + (score - from_min) * (to_max - to_min) / (from_max - from_min)
        return result.clip(lower=to_min, upper=to_max)
    if pd.isna(score) or score < from_min:
        return np.nan
    scaled = to_min + (score - from_min) * (to_max - to_min) / (from_max - from_min)
    return max(to_min, min(to_max, scaled))


def weighted_average(scores, weights):
    """
    Compute weighted average, excluding missing scores (NaN or < 1).
    
    Args:
        scores: dict of {name: score_value} or pd.DataFrame
        weights: dict of {name: weight_value}
    
    Returns:
        Weighted average (float), or NaN if no valid scores.
    """
    if isinstance(scores, dict):
        total_score = 0.0
        total_weight = 0.0
        for name, weight in weights.items():
            score = scores.get(name, np.nan)
            if pd.notna(score) and score >= 1:
                total_score += score * weight
                total_weight += weight
        if total_weight == 0:
            return np.nan
        return total_score / total_weight
    else:
        raise TypeError("Use weighted_average_df for DataFrame inputs")


def weighted_average_df(score_df, weights):
    """
    Vectorized weighted average across DataFrame columns.
    
    Args:
        score_df: DataFrame where each column is a sub-score
        weights: dict of {column_name: weight}
    
    Returns:
        Series of weighted averages per row.
    """
    valid_cols = [c for c in weights.keys() if c in score_df.columns]
    if not valid_cols:
        return pd.Series(np.nan, index=score_df.index)

    weight_arr = np.array([weights[c] for c in valid_cols])
    score_arr = score_df[valid_cols].values

    # Mask invalid scores (NaN or < 1)
    valid_mask = ~np.isnan(score_arr) & (score_arr >= 1)
    
    weighted_scores = np.where(valid_mask, score_arr * weight_arr, 0)
    active_weights = np.where(valid_mask, weight_arr, 0)
    
    total_weights = active_weights.sum(axis=1)
    total_scores = weighted_scores.sum(axis=1)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.where(total_weights > 0, total_scores / total_weights, np.nan)
    return pd.Series(result, index=score_df.index)


def is_missing(value):
    """Check if a value should be considered missing for scoring purposes."""
    if value is None:
        return True
    if isinstance(value, (int, float)):
        return pd.isna(value) or value < 0
    return pd.isna(value)
