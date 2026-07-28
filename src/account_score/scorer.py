"""Score Calculator: Computes component scores and composite from sub-scores.

Follows the reference model pattern:
- Weighted average: sum(score_i * weight_i) / sum(active_weights)
- Missing scores (< 1 or NaN) excluded by setting weight to 0
- Composite score capped between 1 and 10

Supports both single-record (dict) and batch (DataFrame) modes.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

from .utils import weighted_average, weighted_average_df, rescale_score, cap_score
from .config_loader import ConfigLoader


class ScoreCalculator:
    """Calculates component scores (Adequacy, Capacity, Appetite, Environment) and Composite."""

    def __init__(self, config: ConfigLoader):
        self.config = config
        self.scoring = config.scoring_weights
        self.composite_weights = config.get_composite_weights()
        self.score_params = config.get_scoring_params()
        self.sub_score_max = self.score_params.get("sub_score_max", 30)
        self.composite_max = self.score_params.get("composite_max", 10)
        self.composite_min = self.score_params.get("composite_min", 1)

    # ---- Single-record scoring (API mode) ----

    def score_record(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """
        Score a single record from a dict of sub-scores.
        
        Args:
            scores: Dict of {variable_name: score_value} (on 1-30 scale)
        
        Returns:
            Dict with component scores (1-10) and composite.
        """
        # Rescale sub-scores from 1-30 to 1-10
        rescaled = {}
        for k, v in scores.items():
            if v is not None and v >= 1:
                rescaled[k] = rescale_score(v, 1, self.sub_score_max, 1, self.composite_max)
            else:
                rescaled[k] = np.nan

        adequacy = self._calc_component(rescaled, "adequacy_sub_scores")
        capacity = self._calc_component(rescaled, "capacity_sub_scores")
        appetite = self._calc_component(rescaled, "appetite_sub_scores")
        environment = self._calc_component(rescaled, "environment_sub_scores")

        composite = self._calc_composite(adequacy, capacity, appetite, environment)

        return {
            "adequacy_score": round(adequacy, 2) if not pd.isna(adequacy) else None,
            "capacity_score": round(capacity, 2) if not pd.isna(capacity) else None,
            "appetite_score": round(appetite, 2) if not pd.isna(appetite) else None,
            "environment_score": round(environment, 2) if not pd.isna(environment) else None,
            "composite_score_raw": round(composite, 4) if not pd.isna(composite) else None,
            "composite_score": int(cap_score(round(composite), self.composite_min, self.composite_max)) if not pd.isna(composite) else None
        }

    def _calc_component(self, scores: Dict[str, float], dimension_key: str) -> float:
        """Calculate a single component score as weighted average of its sub-scores."""
        dimension_config = self.scoring.get(dimension_key, {})
        weights = {name: cfg["weight"] for name, cfg in dimension_config.items()}
        return weighted_average(scores, weights)

    def _calc_composite(self, adequacy: float, capacity: float, appetite: float, environment: float) -> float:
        """Calculate composite as weighted average of component scores."""
        components = {
            "adequacy": adequacy,
            "capacity": capacity,
            "appetite": appetite,
            "environment": environment
        }
        return weighted_average(components, self.composite_weights)

    # ---- Batch scoring (DataFrame mode) ----

    def score_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score all records in a DataFrame.
        
        Expects columns named 'score_{variable_name}' with values on 1-30 scale.
        Adds component score and composite score columns.
        
        Args:
            df: DataFrame with score_* columns
        
        Returns:
            DataFrame with added component and composite score columns.
        """
        df = df.copy()

        # Rescale all sub-scores from 1-30 to 1-10
        score_cols = [c for c in df.columns if c.startswith("score_")]
        rescaled_df = pd.DataFrame(index=df.index)

        for col in score_cols:
            var_name = col.replace("score_", "")
            values = df[col].astype(float)
            # Invalid scores (-1) become NaN for weighted averaging
            values[values < 1] = np.nan
            rescaled_df[var_name] = rescale_score(values, 1, self.sub_score_max, 1, self.composite_max)

        # Compute component scores
        df["adequacy_score"] = self._calc_component_batch(rescaled_df, "adequacy_sub_scores")
        df["capacity_score"] = self._calc_component_batch(rescaled_df, "capacity_sub_scores")
        df["appetite_score"] = self._calc_component_batch(rescaled_df, "appetite_sub_scores")
        df["environment_score"] = self._calc_component_batch(rescaled_df, "environment_sub_scores")

        # Compute composite
        composite_df = df[["adequacy_score", "capacity_score", "appetite_score", "environment_score"]].copy()
        composite_df.columns = ["adequacy", "capacity", "appetite", "environment"]
        df["composite_score_raw"] = weighted_average_df(composite_df, self.composite_weights)

        # Cap and round
        df["composite_score"] = df["composite_score_raw"].apply(
            lambda x: int(cap_score(round(x), self.composite_min, self.composite_max)) if pd.notna(x) else np.nan
        )

        # Summary
        valid = df["composite_score"].notna().sum()
        print(f"  Scored {valid:,} records with composite scores")
        if valid > 0:
            print(f"  Composite distribution: mean={df['composite_score'].mean():.2f}, "
                  f"median={df['composite_score'].median():.1f}")

        return df

    def _calc_component_batch(self, rescaled_df: pd.DataFrame, dimension_key: str) -> pd.Series:
        """Calculate component score for all records (vectorized)."""
        dimension_config = self.scoring.get(dimension_key, {})
        weights = {name: cfg["weight"] for name, cfg in dimension_config.items()}
        return weighted_average_df(rescaled_df, weights)
