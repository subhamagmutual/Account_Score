"""Main Pipeline Orchestrator for Physician MPL Account Scoring.

Two entry points:
- run_scoring_pipeline(): Full batch pipeline (fit + score entire dataset)
- score_single_record(): Score a single physician-year record

Pipeline Steps:
1. Load configs
2. Load and filter data
3. Compute KPIs (derived target variables)
4. Fit or load binning thresholds
5. Apply categorical lookups (specialty, state)
6. Apply binning → sub-scores (1-30)
7. Apply credibility weighting to adequacy sub-scores
8. Calculate component scores and composite (1-10)
9. Generate deployment tables and export
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np

from .config_loader import ConfigLoader
from .data_loader import load_modeling_data
from .kpi_calculator import compute_kpis, compute_portfolio_averages
from .binner import BinFitter, BinApplier
from .credibility import apply_credibility_to_adequacy
from .scorer import ScoreCalculator
from .output_builder import build_output_dataframe, export_to_csv, export_to_excel
from .deployment_tables import create_all_deployment_tables


def run_scoring_pipeline(
    config_dir: Optional[str] = None,
    mode: str = "fit_and_score",
    input_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    sample_n: Optional[int] = None,
    dynamic: bool = False
) -> pd.DataFrame:
    """
    Run the full batch scoring pipeline.
    
    Args:
        config_dir: Path to config/ directory. If None, uses default (../config relative to src).
        mode: "fit_and_score" (fit bins from data, then score),
              "score_only" (use existing binning_thresholds.json),
              "fit_only" (fit bins and save, don't score)
        input_path: Override data file path.
        output_dir: Override output directory.
        sample_n: If set, sample N records for testing.
        dynamic: If True, use mean-anchored binning (portfolio-relative scoring).
    
    Returns:
        Scored DataFrame.
    """
    print("=" * 60)
    print("PHYSICIAN MPL ACCOUNT SCORING PIPELINE")
    print(f"Mode: {mode} | Dynamic: {dynamic} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Load configs
    print("\n[Step 1] Loading configuration...")
    config = ConfigLoader(config_dir)
    full_config = {
        "pipeline_params": config.pipeline_params,
        "scoring_weights": config.scoring_weights
    }

    if output_dir is None:
        output_dir = config.get_data_params().get("output_dir", "./output")
    os.makedirs(output_dir, exist_ok=True)

    # Step 2: Load and filter data
    print("\n[Step 2] Loading modeling data...")
    df = load_modeling_data(full_config, input_path=input_path, sample_n=sample_n)

    # Step 3: Compute KPIs
    print("\n[Step 3] Computing KPIs...")
    df = compute_kpis(df, config.scoring_weights)

    # Step 4: Apply categorical lookups (specialty, state)
    print("\n[Step 4] Applying categorical lookups...")
    df = _apply_categorical_scores(df, config)

    # Step 5: Fit or load binning thresholds
    print("\n[Step 5] Binning thresholds...")
    portfolio_means = compute_portfolio_averages(df, config.scoring_weights)

    if dynamic:
        # Override binning methods to use mean_anchored/reciprocal
        binning_params = config.get_binning_params().copy()
        methods = binning_params.get("methods_by_variable", {}).copy()
        scoring_weights = config.scoring_weights
        for dim_key in ["adequacy_sub_scores", "capacity_sub_scores",
                        "appetite_sub_scores", "environment_sub_scores"]:
            for var_name, var_config in scoring_weights.get(dim_key, {}).items():
                if methods.get(var_name) == "categorical":
                    continue
                if var_config.get("invert_score", False):
                    methods[var_name] = "reciprocal"
                else:
                    methods[var_name] = "mean_anchored"
        binning_params["methods_by_variable"] = methods
    else:
        binning_params = config.get_binning_params()

    if mode in ("fit_and_score", "fit_only"):
        all_var_configs = _merge_variable_configs(config.scoring_weights)
        fitter = BinFitter(
            n_bins=binning_params.get("n_bins", 30),
        )
        thresholds = fitter.fit_all(
            df, all_var_configs, binning_params, portfolio_means=portfolio_means
        )
        config.save_binning_thresholds(thresholds)
    else:
        thresholds = config.binning_thresholds
        if thresholds is None:
            raise FileNotFoundError(
                "No binning_thresholds.json found. Run with mode='fit_and_score' first."
            )
        print(f"  Loaded existing binning thresholds ({len(thresholds)} variables)")

    if mode == "fit_only":
        print("\n[Done] Fit-only mode complete. Binning thresholds saved.")
        return df

    # Step 6: Apply binning → sub-scores
    print("\n[Step 6] Applying binning to compute sub-scores...")
    all_var_configs = _merge_variable_configs(config.scoring_weights)
    applier = BinApplier(thresholds, score_range=(1, config.get_scoring_params()["sub_score_max"]))
    df = applier.apply_all(df, all_var_configs)

    # Step 7: Apply credibility weighting
    print("\n[Step 7] Applying credibility weighting...")
    portfolio_score_averages = _compute_portfolio_score_averages(df, config)
    df = apply_credibility_to_adequacy(
        df, config.get_credibility_params(), config.scoring_weights, portfolio_score_averages
    )

    # Step 8: Calculate component + composite scores
    print("\n[Step 8] Calculating component and composite scores...")
    scorer = ScoreCalculator(config)
    df = scorer.score_batch(df)

    # Step 9: Generate deployment tables and export
    print("\n[Step 9] Generating deployment tables and exporting...")
    deployment_tables = create_all_deployment_tables(
        df,
        scoring_weights=config.scoring_weights,
        thresholds=thresholds,
        portfolio_means=portfolio_means,
        binning_params=binning_params,
        sub_score_max=config.get_scoring_params()["sub_score_max"]
    )
    print(f"  Generated {len(deployment_tables)} deployment tables")

    output_df = build_output_dataframe(df, full_config)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"physician_scores_{timestamp}.csv")
    xlsx_path = os.path.join(output_dir, f"physician_scores_{timestamp}.xlsx")

    export_to_csv(output_df, csv_path)
    export_to_excel(output_df, xlsx_path, full_config, deployment_tables=deployment_tables)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Records scored: {len(output_df):,}")
    print(f"  Output CSV: {csv_path}")
    print(f"  Output Excel: {xlsx_path}")
    if "composite_score" in df.columns:
        valid = df["composite_score"].notna()
        print(f"  Score distribution:")
        dist = df.loc[valid, "composite_score"].value_counts().sort_index()
        for score, count in dist.items():
            print(f"    Score {int(score)}: {count:,} ({count/valid.sum()*100:.1f}%)")
    print("=" * 60)

    return df


def score_single_record(
    record: Dict[str, Any],
    config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Score a single physician-year record.
    
    Args:
        record: Dict with column values for one physician-year
        config_dir: Path to config/ directory.
    
    Returns:
        Dict with sub-scores, component scores, and composite.
    """
    config = ConfigLoader(config_dir)
    thresholds = config.binning_thresholds
    if thresholds is None:
        raise FileNotFoundError(
            "No binning_thresholds.json found. Run the batch pipeline first to fit thresholds."
        )

    scoring_weights = config.scoring_weights
    score_params = config.get_scoring_params()

    # Compute KPIs for this record
    sub_scores = {}
    adequacy = scoring_weights.get("adequacy_sub_scores", {})
    for var_name, var_config in adequacy.items():
        value = _compute_single_kpi(record, var_config)
        if value is not None and not pd.isna(value):
            applier = BinApplier(thresholds, score_range=(1, score_params["sub_score_max"]))
            sub_scores[var_name] = applier.apply_single(value, var_name)
        else:
            sub_scores[var_name] = -1

    # Categorical lookups
    specialty = record.get(config.pipeline_params["identifiers"].get("specialty", ""))
    state = record.get(config.pipeline_params["identifiers"].get("state", ""))

    if specialty:
        sub_scores["specialty_risk_tier"] = _scale_categorical_to_sub(
            config.get_specialty_score(specialty), score_params["sub_score_max"]
        )
    if state:
        sub_scores["state_venue_risk"] = _scale_categorical_to_sub(
            config.get_state_score(state), score_params["sub_score_max"]
        )

    # Capacity and other appetite sub-scores
    for dimension_key in ["capacity_sub_scores", "appetite_sub_scores", "environment_sub_scores"]:
        for var_name, var_config in scoring_weights.get(dimension_key, {}).items():
            if var_name in sub_scores:
                continue
            source_col = var_config.get("source_column")
            if source_col and source_col in record:
                value = record[source_col]
                if value is not None and not pd.isna(value):
                    applier = BinApplier(thresholds, score_range=(1, score_params["sub_score_max"]))
                    sub_scores[var_name] = applier.apply_single(float(value), var_name)
                else:
                    sub_scores[var_name] = -1

    # Apply credibility
    cred_params = config.get_credibility_params()
    premium = record.get("WRTN_PREM_AMT_ITD_BURNED", 0)
    from .credibility import compute_credibility_weight
    z = compute_credibility_weight(premium, cred_params["full_credibility_premium"])

    complement = cred_params["complement_score"]
    for var_name in cred_params.get("apply_to", []):
        if var_name in sub_scores and sub_scores[var_name] > 0:
            sub_scores[var_name] = z * sub_scores[var_name] + (1 - z) * complement

    # Calculate composite
    scorer = ScoreCalculator(config)
    result = scorer.score_record(sub_scores)
    result["sub_scores"] = sub_scores
    result["credibility_z"] = round(z, 4)

    return result


# ---- Private helper functions ----

def _apply_categorical_scores(df: pd.DataFrame, config: ConfigLoader) -> pd.DataFrame:
    """Apply specialty and state tier lookups, saving as score columns."""
    df = df.copy()
    score_max = config.get_scoring_params()["sub_score_max"]

    # Specialty
    spec_col = config.pipeline_params.get("identifiers", {}).get("specialty", "OL_RISK_SPECIALTY_DESC")
    if spec_col in df.columns:
        tier_scores = df[spec_col].map(lambda x: config.get_specialty_score(x) if pd.notna(x) else -1)
        df["score_specialty_risk_tier"] = tier_scores.apply(
            lambda x: _scale_categorical_to_sub(x, score_max) if x > 0 else -1
        )
        valid = (df["score_specialty_risk_tier"] > 0).sum()
        print(f"  Scored specialty_risk_tier: {valid:,} valid scores")

    # State
    state_col = config.pipeline_params.get("identifiers", {}).get("state", "ST")
    if state_col in df.columns:
        tier_scores = df[state_col].map(lambda x: config.get_state_score(x) if pd.notna(x) else -1)
        df["score_state_venue_risk"] = tier_scores.apply(
            lambda x: _scale_categorical_to_sub(x, score_max) if x > 0 else -1
        )
        valid = (df["score_state_venue_risk"] > 0).sum()
        print(f"  Scored state_venue_risk: {valid:,} valid scores")

    return df


def _scale_categorical_to_sub(tier_score: int, sub_score_max: int = 30) -> int:
    """Scale a 1-10 categorical tier score to the 1-30 sub-score scale."""
    if tier_score < 1:
        return -1
    # Linear scale: tier 1 → sub 1, tier 10 → sub 30
    return int(round(1 + (tier_score - 1) * (sub_score_max - 1) / 9))


def _merge_variable_configs(scoring_weights: Dict[str, Any]) -> Dict[str, Any]:
    """Merge all sub-score configs from all dimensions into one dict."""
    merged = {}
    for dim_key in ["adequacy_sub_scores", "capacity_sub_scores",
                    "appetite_sub_scores", "environment_sub_scores"]:
        merged.update(scoring_weights.get(dim_key, {}))
    return merged


def _compute_single_kpi(record: Dict[str, Any], var_config: Dict[str, Any]) -> Optional[float]:
    """Compute a single KPI value from a record dict."""
    if "numerator" in var_config:
        num_col = var_config["numerator"]
        den_col = var_config.get("denominator")
        multiplier = var_config.get("numerator_multiplier", 1)

        num = record.get(num_col)
        if num is None or pd.isna(num):
            return None

        num = float(num) * multiplier

        if den_col:
            den = record.get(den_col)
            if den is None or pd.isna(den) or float(den) == 0:
                return None
            if var_config.get("only_when_claims_exist") and float(den) <= 0:
                return None
            return num / float(den)
        return num

    elif "source_column" in var_config:
        val = record.get(var_config["source_column"])
        if val is None or pd.isna(val):
            return None
        return float(val)

    return None


def _compute_portfolio_score_averages(df: pd.DataFrame, config: ConfigLoader) -> Dict[str, float]:
    """Compute the portfolio average SCORE for credibility complement."""
    complement = config.get_credibility_params().get("complement_score", 15)
    averages = {}

    adequacy = config.scoring_weights.get("adequacy_sub_scores", {})
    for var_name in adequacy.keys():
        score_col = f"score_{var_name}"
        if score_col in df.columns:
            valid_scores = df[score_col][df[score_col] > 0]
            if len(valid_scores) > 0:
                averages[var_name] = valid_scores.median()
            else:
                averages[var_name] = complement
        else:
            averages[var_name] = complement

    return averages
