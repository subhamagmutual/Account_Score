"""Credibility weighting for loss-based adequacy sub-scores.

Formula: Z = MIN(SQRT(premium / full_credibility_premium), 1)
Blended Score = Z * Individual_Score + (1-Z) * Portfolio_Average_Score

Only applied to loss-based sub-scores where individual experience may be unreliable
for low-premium physicians.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


def compute_credibility_weight(premium: float, full_credibility_premium: float) -> float:
    """
    Compute the credibility weight Z for a single record.
    
    Z = MIN(SQRT(premium / full_credibility_premium), 1)
    
    Args:
        premium: Written premium for this physician-year
        full_credibility_premium: Threshold at which Z=1 (full credibility)
    
    Returns:
        Z value between 0 and 1.
    """
    if pd.isna(premium) or premium <= 0 or full_credibility_premium <= 0:
        return 0.0
    return min(np.sqrt(premium / full_credibility_premium), 1.0)


def compute_credibility_weights_series(
    premium_series: pd.Series,
    full_credibility_premium: float
) -> pd.Series:
    """Vectorized credibility weight computation for a full column."""
    z = np.sqrt(premium_series.clip(lower=0) / full_credibility_premium)
    return z.clip(upper=1.0).fillna(0.0)


def apply_credibility_blending(
    individual_scores: pd.Series,
    portfolio_avg_score: float,
    z_weights: pd.Series
) -> pd.Series:
    """
    Blend individual scores with portfolio average using credibility weights.
    
    Blended = Z * Individual + (1 - Z) * Portfolio_Average
    
    Args:
        individual_scores: Raw sub-scores (1-30 scale, -1 = missing)
        portfolio_avg_score: Portfolio average score (complement)
        z_weights: Credibility weights (0 to 1) per record
    
    Returns:
        Blended scores (same scale). Missing scores remain -1.
    """
    result = individual_scores.copy().astype(float)
    valid = individual_scores > 0

    blended = z_weights * individual_scores + (1 - z_weights) * portfolio_avg_score
    result[valid] = blended[valid]
    result[~valid] = -1

    return result


def apply_credibility_to_adequacy(
    df: pd.DataFrame,
    credibility_params: Dict[str, Any],
    scoring_weights: Dict[str, Any],
    portfolio_averages: Dict[str, float]
) -> pd.DataFrame:
    """
    Apply credibility weighting to all eligible adequacy sub-scores.
    
    Args:
        df: DataFrame with score_* columns and premium column
        credibility_params: From pipeline_params.json credibility section
        scoring_weights: Full scoring_weights config
        portfolio_averages: Dict of {var_name: portfolio_avg_score_value}
    
    Returns:
        DataFrame with credibility-adjusted score columns.
    """
    df = df.copy()

    full_cred_prem = credibility_params["full_credibility_premium"]
    complement_score = credibility_params["complement_score"]
    apply_to = credibility_params.get("apply_to", [])

    # Compute Z weights
    prem_col = "WRTN_PREM_AMT_ITD_BURNED"
    if prem_col in df.columns:
        df["credibility_z"] = compute_credibility_weights_series(df[prem_col], full_cred_prem)
    else:
        df["credibility_z"] = 1.0  # Default to full credibility if no premium data

    # Apply blending to eligible sub-scores
    adequacy = scoring_weights.get("adequacy_sub_scores", {})
    for var_name, var_config in adequacy.items():
        if not var_config.get("apply_credibility", False):
            continue
        if var_name not in apply_to:
            continue

        score_col = f"score_{var_name}"
        if score_col not in df.columns:
            continue

        # Use portfolio average for this variable, or global complement
        port_avg = portfolio_averages.get(var_name, complement_score)

        df[score_col] = apply_credibility_blending(
            df[score_col], port_avg, df["credibility_z"]
        )
        print(f"  Applied credibility to {score_col} (complement={port_avg:.1f})")

    return df
