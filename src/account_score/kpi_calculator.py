"""KPI Calculator: Computes derived target variables for scoring.

Each KPI uses the exact numerator/denominator from the Target_Weight_Dictionary.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .utils import safe_divide


def compute_kpis(df: pd.DataFrame, scoring_weights: Dict[str, Any]) -> pd.DataFrame:
    """
    Compute all derived KPIs (loss cost, frequency, severity, ratios).
    
    Adds new columns to the DataFrame for each computed KPI.
    Only computes KPIs where the source columns exist in the data.
    
    Args:
        df: Filtered modeling DataFrame
        scoring_weights: The scoring_weights config dict
    
    Returns:
        DataFrame with new KPI columns appended.
    """
    df = df.copy()

    for dimension in ["adequacy_sub_scores", "capacity_sub_scores",
                      "appetite_sub_scores", "environment_sub_scores"]:
        sub_scores = scoring_weights.get(dimension, {})

        for var_name, var_config in sub_scores.items():
            kpi_col_name = f"kpi_{var_name}"

            # Skip categorical variables (handled by tier lookups)
            if "lookup_config" in var_config:
                continue

            if "numerator" in var_config:
                num_col = var_config["numerator"]
                den_col = var_config.get("denominator")
                multiplier = var_config.get("numerator_multiplier", 1)

                if num_col not in df.columns:
                    print(f"  SKIP {var_name}: numerator '{num_col}' not in data")
                    continue
                if den_col and den_col not in df.columns:
                    print(f"  SKIP {var_name}: denominator '{den_col}' not in data")
                    continue

                numerator = df[num_col] * multiplier

                if den_col:
                    denominator = df[den_col]
                    if var_config.get("only_when_claims_exist", False):
                        kpi = safe_divide(numerator, denominator, default=np.nan)
                        kpi[denominator <= 0] = np.nan
                    else:
                        kpi = safe_divide(numerator, denominator, default=np.nan)
                else:
                    kpi = numerator

                df[kpi_col_name] = kpi
                non_null = kpi.notna().sum()
                print(f"  Computed {kpi_col_name}: {non_null:,} valid values")

            elif "source_column" in var_config:
                source_col = var_config["source_column"]
                if source_col in df.columns:
                    # For inverted metrics, clip negatives
                    if var_config.get("invert_score", False):
                        df[kpi_col_name] = df[source_col].clip(lower=0)
                    else:
                        df[kpi_col_name] = df[source_col]
                    non_null = df[kpi_col_name].notna().sum()
                    print(f"  Computed {kpi_col_name}: {non_null:,} valid values")

    return df


def compute_portfolio_averages(df: pd.DataFrame, scoring_weights: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute portfolio-level average for each KPI.
    Used as the credibility complement and for dynamic binning anchors.
    
    Returns:
        Dict of {variable_name: portfolio_weighted_average}
    """
    averages = {}

    for dimension in ["adequacy_sub_scores", "capacity_sub_scores",
                      "appetite_sub_scores", "environment_sub_scores"]:
        sub_scores = scoring_weights.get(dimension, {})
        for var_name, var_config in sub_scores.items():
            # Skip categorical variables
            if "lookup_config" in var_config:
                continue

            kpi_col = f"kpi_{var_name}"

            if kpi_col not in df.columns:
                # Try source_column directly for Direct-type variables
                source_col = var_config.get("source_column", "")
                if source_col and source_col in df.columns:
                    valid = df[source_col].dropna()
                    if len(valid) > 0:
                        # Premium-weighted mean for direct variables
                        prem_col = "WRTN_PREM_AMT_ITD_BURNED"
                        if prem_col in df.columns:
                            mask = df[source_col].notna() & df[prem_col].notna() & (df[prem_col] > 0)
                            if mask.sum() > 0:
                                averages[var_name] = (
                                    (df.loc[mask, source_col] * df.loc[mask, prem_col]).sum()
                                    / df.loc[mask, prem_col].sum()
                                )
                            else:
                                averages[var_name] = valid.median()
                        else:
                            averages[var_name] = valid.median()
                continue

            # For ratio KPIs, compute the portfolio-level ratio (sum(num)/sum(den))
            if "numerator" in var_config and "denominator" in var_config:
                num_col = var_config["numerator"]
                den_col = var_config["denominator"]
                multiplier = var_config.get("numerator_multiplier", 1)

                if num_col in df.columns and den_col in df.columns:
                    total_num = (df[num_col] * multiplier).sum()
                    total_den = df[den_col].sum()
                    if total_den > 0:
                        averages[var_name] = total_num / total_den
                    else:
                        averages[var_name] = 0.0
                else:
                    averages[var_name] = df[kpi_col].median()
            elif "source_column" in var_config:
                # Standalone: use premium-weighted mean
                prem_col = "WRTN_PREM_AMT_ITD_BURNED"
                if prem_col in df.columns:
                    mask = df[kpi_col].notna() & df[prem_col].notna() & (df[prem_col] > 0)
                    if mask.sum() > 0:
                        averages[var_name] = (
                            (df.loc[mask, kpi_col] * df.loc[mask, prem_col]).sum()
                            / df.loc[mask, prem_col].sum()
                        )
                    else:
                        averages[var_name] = df[kpi_col].median()
                else:
                    averages[var_name] = df[kpi_col].median()
            else:
                averages[var_name] = df[kpi_col].median()

    return averages
