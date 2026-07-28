"""Data loading and filtering for the Account Scoring pipeline."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


def get_required_columns(config: Dict[str, Any]) -> List[str]:
    """
    Determine all columns needed from the modeling data based on config.
    This avoids loading all 1701 columns.
    """
    cols = set()

    # Identifier columns
    identifiers = config.get("pipeline_params", {}).get("identifiers", {})
    cols.update(identifiers.values())

    # Filter columns
    filters = config.get("pipeline_params", {}).get("filters", {})
    cols.add(filters.get("premium_col", "WRTN_PREM_AMT_ITD_BURNED_CLASS_OL"))
    cols.add(filters.get("bce_col", "BCE_ST"))
    cols.add(filters.get("coverage_date_col", "COVEFF_DATE"))
    cols.add(filters.get("policy_date_col", "POLEFF_DATE"))

    # Scoring weight columns (numerators, denominators, source columns)
    weights = config.get("scoring_weights", {})
    for dimension in ["adequacy_sub_scores", "capacity_sub_scores",
                      "appetite_sub_scores", "environment_sub_scores"]:
        sub_scores = weights.get(dimension, {})
        for var_name, var_config in sub_scores.items():
            if "numerator" in var_config:
                cols.add(var_config["numerator"])
            if "denominator" in var_config:
                cols.add(var_config["denominator"])
            if "source_column" in var_config:
                cols.add(var_config["source_column"])

    # Credibility premium column (always needed for Z-factor)
    cols.add("WRTN_PREM_AMT_ITD_BURNED")

    # Remove any None values
    cols.discard(None)
    cols.discard("NaN")

    return sorted(cols)


def load_modeling_data(
    config: Dict[str, Any],
    input_path: Optional[str] = None,
    apply_filters: bool = True,
    sample_n: Optional[int] = None
) -> pd.DataFrame:
    """
    Load the modeling dataset with only required columns and apply filters.
    
    Uses chunked reading for large files when sample_n is None (full data mode).
    
    Args:
        config: Full config dict (pipeline_params + scoring_weights merged)
        input_path: Override for data file path. If None, uses config path.
        apply_filters: Whether to apply year/premium/bce filters.
        sample_n: If set, return a random sample of n rows (for testing).
    
    Returns:
        Filtered DataFrame ready for scoring.
    """
    data_params = config.get("pipeline_params", {}).get("data", {})
    if input_path is None:
        input_path = data_params["input_path"]

    # Get only needed columns
    required_cols = get_required_columns(config)

    # First read a small chunk to verify column availability
    header_sample = pd.read_csv(input_path, nrows=5)
    available_cols = [c for c in required_cols if c in header_sample.columns]
    missing_cols = [c for c in required_cols if c not in header_sample.columns]

    if missing_cols:
        print(f"WARNING: {len(missing_cols)} required columns not found in data: {missing_cols[:10]}")

    print(f"Loading {len(available_cols)} columns from modeling data...")

    if sample_n is not None:
        # Fast path: read limited rows for testing
        nrows_limit = sample_n * 5
        df = pd.read_csv(input_path, usecols=available_cols, low_memory=False, nrows=nrows_limit)
        print(f"  Raw records: {len(df):,}")

        if apply_filters:
            df = apply_data_filters(df, config)

        if sample_n < len(df):
            df = df.sample(n=sample_n, random_state=42)
            print(f"  Sampled to: {len(df):,} records")
    else:
        # Full data path: read in chunks to handle large files
        chunks = []
        total_raw = 0
        chunk_size = 50000
        for chunk in pd.read_csv(input_path, usecols=available_cols, low_memory=False, chunksize=chunk_size):
            total_raw += len(chunk)
            if apply_filters:
                chunk = apply_data_filters(chunk, config, silent=True)
            chunks.append(chunk)
            print(f"  Processed {total_raw:,} rows...", end='\r')

        df = pd.concat(chunks, ignore_index=True)
        print(f"  Raw records: {total_raw:,}                    ")
        print(f"  After filters: {len(df):,} records (removed {total_raw - len(df):,})")

    return df


def apply_data_filters(df: pd.DataFrame, config: Dict[str, Any], silent: bool = False) -> pd.DataFrame:
    """Apply standard data quality filters from config."""
    filters = config.get("pipeline_params", {}).get("filters", {})

    initial_count = len(df)

    # Premium filter
    prem_col = filters.get("premium_col", "WRTN_PREM_AMT_ITD_BURNED_CLASS_OL")
    if prem_col in df.columns:
        df = df[df[prem_col] > filters.get("min_written_premium", 0)]

    # BCE filter
    bce_col = filters.get("bce_col", "BCE_ST")
    if bce_col in df.columns:
        df = df[df[bce_col] > filters.get("min_bce", 0)]

    # Coverage year filter
    cov_col = filters.get("coverage_date_col", "COVEFF_DATE")
    if cov_col in df.columns:
        df[cov_col] = pd.to_datetime(df[cov_col], errors="coerce")
        year_min = filters.get("coverage_year_min", 2017)
        year_max = filters.get("coverage_year_max", 2023)
        df = df[
            (df[cov_col].dt.year >= year_min) &
            (df[cov_col].dt.year <= year_max)
        ]

    # Policy year filter
    pol_col = filters.get("policy_date_col", "POLEFF_DATE")
    if pol_col in df.columns:
        df[pol_col] = pd.to_datetime(df[pol_col], errors="coerce")
        pol_year_min = filters.get("policy_year_min", 2017)
        df = df[df[pol_col].dt.year >= pol_year_min]

    if not silent:
        print(f"  After filters: {len(df):,} records (removed {initial_count - len(df):,})")
    return df.reset_index(drop=True)
