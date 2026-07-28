"""Configuration loader for the Account Scoring pipeline.

Supports two config sources:
1. JSON files (default): Loads from config/ directory (pipeline_params.json, scoring_weights.json, etc.)
2. Excel control file: Single PAS_control_file.xlsx with all config in sheets

When both are present, JSON takes precedence unless explicitly loading from Excel.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd


class ConfigLoader:
    """Loads and provides access to all pipeline configuration files."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        self.config_dir = Path(config_dir)
        self._configs: Dict[str, Any] = {}
        self.reload()

    def reload(self):
        """(Re)load all JSON config files from the config directory."""
        self._configs = {}
        for json_file in self.config_dir.glob("*.json"):
            key = json_file.stem
            with open(json_file, "r", encoding="utf-8") as f:
                self._configs[key] = json.load(f)

    @classmethod
    def from_excel(cls, excel_path: str) -> "ConfigLoader":
        """
        Load configuration from a PAS-style Excel control file.

        Converts Excel sheets into the same internal dict structure as JSON loading.

        Args:
            excel_path: Path to the Excel control file (PAS_control_file.xlsx)

        Returns:
            ConfigLoader instance with configs populated from Excel.
        """
        instance = cls.__new__(cls)
        instance.config_dir = Path(os.path.dirname(excel_path))
        instance._configs = {}

        # Read all sheets
        variables_df = pd.read_excel(excel_path, sheet_name="Variables")
        composite_df = pd.read_excel(excel_path, sheet_name="Composite_Weights")
        cred_df = pd.read_excel(excel_path, sheet_name="Credibility")
        filters_df = pd.read_excel(excel_path, sheet_name="Filters")
        identifiers_df = pd.read_excel(excel_path, sheet_name="Identifiers")
        data_paths_df = pd.read_excel(excel_path, sheet_name="Data_Paths")
        scoring_params_df = pd.read_excel(excel_path, sheet_name="Scoring_Params")

        # Store raw Excel data for direct access
        instance._configs["_variables_df"] = variables_df

        # Build scoring_weights structure
        scoring_weights = {"composite_weights": {}}
        for _, row in composite_df.iterrows():
            scoring_weights["composite_weights"][row["Component"].lower()] = float(row["Weight"])

        for component in ["Adequacy", "Capacity", "Appetite", "Environment"]:
            dim_key = f"{component.lower()}_sub_scores"
            scoring_weights[dim_key] = {}
            comp_vars = variables_df[variables_df["Component"] == component]
            for _, var_row in comp_vars.iterrows():
                var_config = {
                    "weight": float(var_row["Weight"]),
                    "type": var_row["Type"],
                    "invert_score": bool(var_row.get("Invert_Score", False)),
                }
                if var_row["Type"] == "Ratio":
                    var_config["numerator"] = var_row["Numerator"]
                    var_config["denominator"] = var_row["Denominator"]
                    var_config["numerator_multiplier"] = float(var_row.get("Multiplier", 1))
                    var_config["only_when_claims_exist"] = bool(var_row.get("Only_When_Claims", False))
                elif var_row["Type"] == "Direct":
                    var_config["source_column"] = var_row.get("Source_Column", "")
                elif var_row["Type"] == "Categorical":
                    var_config["source_column"] = var_row.get("Source_Column", "")
                    var_config["lookup_config"] = var_row.get("Lookup_Config", "")
                scoring_weights[dim_key][var_row["Variable"]] = var_config

        instance._configs["scoring_weights"] = scoring_weights

        # Build pipeline_params structure
        identifiers = {}
        for _, row in identifiers_df.iterrows():
            identifiers[row["Identifier"]] = row["Column"]

        filters = {}
        for _, row in filters_df.iterrows():
            param = row["Parameter"]
            val = row["Value"]
            try:
                filters[param] = int(val)
            except (ValueError, TypeError):
                filters[param] = val
            if "Column" in row.index:
                col_val = row["Column"]
                if pd.notna(col_val) and str(col_val).strip():
                    # Map filter params to their column names
                    if "col" in param:
                        filters[param] = col_val
                    else:
                        # Store as separate key (e.g., premium_col, bce_col)
                        col_key = f"{param}_col"
                        filters[col_key] = col_val

        data_paths = {}
        for _, row in data_paths_df.iterrows():
            data_paths[row["Parameter"]] = row["Value"]

        scoring = {}
        for _, row in scoring_params_df.iterrows():
            try:
                scoring[row["Parameter"]] = float(row["Value"])
            except (ValueError, TypeError):
                scoring[row["Parameter"]] = row["Value"]

        cred_params = {}
        for _, row in cred_df.iterrows():
            try:
                cred_params[row["Parameter"]] = float(row["Value"])
            except (ValueError, TypeError):
                cred_params[row["Parameter"]] = row["Value"]

        # Build credibility apply_to list from variables
        cred_vars = variables_df[variables_df["Apply_Credibility"] == True]["Variable"].tolist()
        cred_params["apply_to"] = cred_vars

        # Build binning params from variables
        methods_by_variable = {}
        for _, var_row in variables_df.iterrows():
            method = var_row.get("Binning_Method", "bin_All")
            # Map PAS method names to Account_Score method names
            method_map = {
                "bin_All": "mean_anchored",
                "bin_RA": "reciprocal",
                "categorical": "categorical"
            }
            methods_by_variable[var_row["Variable"]] = method_map.get(method, method)

        pipeline_params = {
            "data": data_paths,
            "filters": filters,
            "scoring": scoring,
            "credibility": cred_params,
            "binning": {
                "default_method": "mean_anchored",
                "n_bins": int(scoring.get("sub_score_max", 10)),
                "methods_by_variable": methods_by_variable
            },
            "identifiers": identifiers
        }
        instance._configs["pipeline_params"] = pipeline_params

        # Load tier JSON files if they exist in the same directory
        for tier_file in instance.config_dir.glob("*_tiers.json"):
            key = tier_file.stem
            with open(tier_file, "r", encoding="utf-8") as f:
                instance._configs[key] = json.load(f)

        return instance

    def get(self, config_name: str) -> Dict[str, Any]:
        """Get a config by name (filename without .json extension)."""
        if config_name not in self._configs:
            raise KeyError(f"Config '{config_name}' not found. Available: {list(self._configs.keys())}")
        return self._configs[config_name]

    @property
    def pipeline_params(self) -> Dict[str, Any]:
        return self.get("pipeline_params")

    @property
    def scoring_weights(self) -> Dict[str, Any]:
        return self.get("scoring_weights")

    @property
    def specialty_tiers(self) -> Dict[str, Any]:
        return self.get("specialty_tiers")

    @property
    def state_tiers(self) -> Dict[str, Any]:
        return self.get("state_tiers")

    @property
    def binning_thresholds(self) -> Optional[Dict[str, Any]]:
        """Returns binning thresholds from models/CURRENT/ or falls back to config/."""
        try:
            return self.get("binning_thresholds")
        except KeyError:
            # Try loading from versioned models directory
            project_root = self.config_dir.parent
            models_current = project_root / "models" / "CURRENT" / "thresholds.json"
            if models_current.exists():
                with open(models_current, "r", encoding="utf-8") as f:
                    thresholds = json.load(f)
                    self._configs["binning_thresholds"] = thresholds
                    return thresholds
            return None

    @property
    def variables_df(self) -> Optional[pd.DataFrame]:
        """Returns the variables DataFrame if loaded from Excel."""
        return self._configs.get("_variables_df")

    # --- Convenience accessors ---

    def get_data_params(self) -> Dict[str, Any]:
        return self.pipeline_params["data"]

    def get_filter_params(self) -> Dict[str, Any]:
        return self.pipeline_params["filters"]

    def get_scoring_params(self) -> Dict[str, Any]:
        return self.pipeline_params["scoring"]

    def get_credibility_params(self) -> Dict[str, Any]:
        return self.pipeline_params["credibility"]

    def get_binning_params(self) -> Dict[str, Any]:
        return self.pipeline_params["binning"]

    def get_composite_weights(self) -> Dict[str, float]:
        return self.scoring_weights["composite_weights"]

    def get_adequacy_config(self) -> Dict[str, Any]:
        return self.scoring_weights["adequacy_sub_scores"]

    def get_capacity_config(self) -> Dict[str, Any]:
        return self.scoring_weights["capacity_sub_scores"]

    def get_appetite_config(self) -> Dict[str, Any]:
        return self.scoring_weights["appetite_sub_scores"]

    def get_environment_config(self) -> Dict[str, Any]:
        return self.scoring_weights["environment_sub_scores"]

    def get_specialty_score(self, specialty: str) -> int:
        """Look up a specialty's risk score. Returns default if not found."""
        tiers = self.specialty_tiers["tiers"]
        return tiers.get(specialty, self.specialty_tiers["default_score"])

    def get_state_score(self, state: str) -> int:
        """Look up a state's venue risk score. Returns default if not found."""
        tiers = self.state_tiers["tiers"]
        return tiers.get(state, self.state_tiers["default_score"])

    def save_binning_thresholds(self, thresholds: Dict[str, Any]):
        """Save fitted binning thresholds to versioned models directory."""
        project_root = self.config_dir.parent
        models_dir = project_root / "models"

        # Create versioned directory with timestamp (e.g., binning_v20260728_143045)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_dir = models_dir / f"binning_v{timestamp}"
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save thresholds
        thresholds_path = version_dir / "thresholds.json"
        with open(thresholds_path, "w", encoding="utf-8") as f:
            json.dump(thresholds, f, indent=4)

        # Save metadata
        metadata = {
            "version": f"binning_v{timestamp}",
            "created_date": datetime.now().isoformat(),
            "description": "Fitted binning thresholds for all 23 variables"
        }
        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)

        # Update CURRENT symlink to point to new version
        current_link = models_dir / "CURRENT"
        if current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(version_dir.name)

        self._configs["binning_thresholds"] = thresholds
        print(f"  Saved binning thresholds to {thresholds_path}")
        print(f"  Updated models/CURRENT -> {version_dir.name}")
