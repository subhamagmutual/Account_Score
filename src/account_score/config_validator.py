"""Configuration validation: Ensure all required parameters are present and valid.

Validates:
- Composite weights sum to 1.0
- All dimensions have sub-scores
- Data paths exist
- Credibility parameters reasonable
- Binning parameters consistent
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path


class ConfigValidator:
    """Validates PAS configuration for completeness and consistency."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Dict containing all loaded configs (pipeline_params, scoring_weights, etc.)
        """
        self.config = config
        self.errors = []
        self.warnings = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validation checks.
        
        Returns:
            (is_valid, list_of_errors, list_of_warnings)
        """
        self._validate_scoring_weights()
        self._validate_pipeline_params()
        self._validate_tier_mappings()
        self._validate_binning_params()
        self._validate_credibility_params()
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_scoring_weights(self):
        """Ensure weights sum to 1.0 and all sub-scores are defined."""
        weights = self.config.get("scoring_weights", {})
        
        if not weights:
            self.errors.append("❌ Missing scoring_weights configuration")
            return
        
        # Check composite weights sum to 1.0
        comp_weights = weights.get("composite_weights", {})
        
        if not comp_weights:
            self.errors.append("❌ scoring_weights missing composite_weights")
            return
        
        weight_sum = sum(comp_weights.values())
        if not (0.98 < weight_sum < 1.02):  # Allow small floating point error
            self.errors.append(
                f"❌ Composite weights sum to {weight_sum:.4f}, expected 1.0. "
                f"Check: {comp_weights}"
            )
        
        # Check all dimensions exist and have sub-scores
        required_dims = [
            "adequacy_sub_scores",
            "capacity_sub_scores",
            "appetite_sub_scores",
            "environment_sub_scores"
        ]
        
        for dim in required_dims:
            if dim not in weights or not weights[dim]:
                self.errors.append(f"❌ Missing or empty {dim}")
            else:
                # Check sub-score weights within each dimension
                sub_weights = {k: v.get("weight", 0) for k, v in weights[dim].items()}
                sub_sum = sum(sub_weights.values())
                
                # Within each dimension, weights should sum to 1.0
                if not (0.98 < sub_sum < 1.02):
                    self.warnings.append(
                        f"⚠️  {dim} weights sum to {sub_sum:.4f}. "
                        f"Consider normalizing: {sub_weights}"
                    )
                
                # Check each sub-score has required fields
                for var_name, var_config in weights[dim].items():
                    if "weight" not in var_config:
                        self.errors.append(f"❌ {dim}.{var_name} missing weight")
                    
                    var_type = var_config.get("type")
                    if not var_type:
                        self.warnings.append(f"⚠️  {dim}.{var_name} missing type")
    
    def _validate_pipeline_params(self):
        """Check required pipeline parameters."""
        params = self.config.get("pipeline_params", {})
        
        if not params:
            self.errors.append("❌ Missing pipeline_params configuration")
            return
        
        # Verify required sections exist
        required_sections = ["data", "filters", "scoring", "credibility", "binning", "identifiers"]
        for section in required_sections:
            if section not in params:
                self.errors.append(f"❌ Missing pipeline_params.{section}")
        
        # Verify data paths
        data_config = params.get("data", {})
        input_path = data_config.get("input_file")
        
        if input_path:
            if not Path(input_path).exists():
                self.warnings.append(
                    f"⚠️  Input file not found at: {input_path}\n"
                    f"    (This is OK if running in different environment)"
                )
        else:
            self.warnings.append("⚠️  input_file not specified in data config")
        
        # Check identifiers
        identifiers = params.get("identifiers", {})
        required_ids = ["npi", "specialty", "state"]
        
        for id_type in required_ids:
            if id_type not in identifiers:
                self.warnings.append(f"⚠️  Missing identifier mapping for: {id_type}")
    
    def _validate_tier_mappings(self):
        """Check specialty and state tier completeness."""
        spec_tiers = self.config.get("specialty_tiers", {})
        state_tiers = self.config.get("state_tiers", {})
        
        # Ensure they have basic structure
        if "default_score" not in spec_tiers:
            self.errors.append("❌ specialty_tiers missing default_score")
        
        if "default_score" not in state_tiers:
            self.errors.append("❌ state_tiers missing default_score")
        
        # Check tier ranges are valid (1-10)
        if "tiers" in spec_tiers:
            for specialty, score in spec_tiers["tiers"].items():
                if not (1 <= score <= 10):
                    self.errors.append(
                        f"❌ specialty_tiers[{specialty}] = {score}, expected 1-10"
                    )
        
        if "tiers" in state_tiers:
            for state, score in state_tiers["tiers"].items():
                if not (1 <= score <= 10):
                    self.errors.append(
                        f"❌ state_tiers[{state}] = {score}, expected 1-10"
                    )
    
    def _validate_binning_params(self):
        """Verify binning method configuration."""
        params = self.config.get("pipeline_params", {})
        binning = params.get("binning", {})
        
        if not binning:
            self.errors.append("❌ Missing binning parameters")
            return
        
        # Check valid methods
        valid_methods = [
            "quantile", "equal_width", "log_scale", "u_shaped",
            "mean_anchored", "reciprocal", "categorical"
        ]
        
        methods_by_var = binning.get("methods_by_variable", {})
        for var_name, method in methods_by_var.items():
            if method not in valid_methods:
                self.errors.append(
                    f"❌ Unknown binning method '{method}' for {var_name}. "
                    f"Valid: {valid_methods}"
                )
        
        # Check default method
        default_method = binning.get("default_method")
        if default_method and default_method not in valid_methods:
            self.errors.append(
                f"❌ Invalid default_method: {default_method}. "
                f"Valid: {valid_methods}"
            )
        
        # Check n_bins is reasonable
        n_bins = binning.get("n_bins")
        if n_bins and (n_bins < 5 or n_bins > 100):
            self.warnings.append(
                f"⚠️  n_bins = {n_bins}. Typical range: 10-50"
            )
    
    def _validate_credibility_params(self):
        """Verify credibility weighting parameters."""
        params = self.config.get("pipeline_params", {})
        cred = params.get("credibility", {})
        
        if not cred:
            self.warnings.append("⚠️  Missing credibility parameters")
            return
        
        # Check full_credibility_premium is positive
        full_cred = cred.get("full_credibility_premium", 0)
        if full_cred <= 0:
            self.errors.append(
                f"❌ full_credibility_premium must be positive, got {full_cred}"
            )
        
        # Check complement_score is in valid range
        complement = cred.get("complement_score", 0)
        if not (1 <= complement <= 30):
            self.errors.append(
                f"❌ complement_score must be 1-30, got {complement}"
            )
        
        # Check apply_to list
        apply_to = cred.get("apply_to", [])
        if not apply_to:
            self.warnings.append("⚠️  Credibility apply_to list is empty")


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate configuration and return validation results.
    
    Args:
        config: Dict with all configuration loaded
    
    Returns:
        (is_valid, errors, warnings)
    """
    validator = ConfigValidator(config)
    return validator.validate_all()


__all__ = ['ConfigValidator', 'validate_config']
