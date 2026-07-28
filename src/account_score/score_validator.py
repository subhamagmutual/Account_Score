"""Score validation: Check computed scores for consistency and sanity.

Validates:
- Score distributions are reasonable
- Component scores in expected ranges
- No anomalies in scoring
- Credibility weighting applied correctly
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from .logger import logger


class ScoreValidator:
    """Validate computed scores for consistency."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.issues = []
        self.warnings = []
        self.stats = {}
    
    def validate_composite_distribution(
        self,
        df: pd.DataFrame,
        expected_mean: float = 5.5,
        expected_std: float = 2.0
    ) -> Tuple[bool, List[str], Dict]:
        """
        Check if composite score distribution looks reasonable.
        
        Args:
            df: DataFrame with 'composite_score' column
            expected_mean: Expected mean of distribution (default ~5-6)
            expected_std: Expected standard deviation
        
        Returns:
            (is_valid, issues, stats)
        """
        self.issues = []
        self.warnings = []
        self.stats = {}
        
        if "composite_score" not in df.columns:
            self.issues.append("❌ Column 'composite_score' not found")
            return False, self.issues, self.stats
        
        valid_scores = df[df["composite_score"].notna()]["composite_score"]
        
        if len(valid_scores) == 0:
            self.issues.append("❌ No valid composite scores generated!")
            return False, self.issues, self.stats
        
        # Basic statistics
        mean = valid_scores.mean()
        std = valid_scores.std()
        median = valid_scores.median()
        min_score = valid_scores.min()
        max_score = valid_scores.max()
        
        self.stats = {
            "valid_scores": len(valid_scores),
            "null_scores": df["composite_score"].isna().sum(),
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std": round(std, 2),
            "min": int(min_score),
            "max": int(max_score)
        }
        
        # Checks
        is_valid = True
        
        # Check score range
        if min_score < 1 or max_score > 10:
            self.issues.append(
                f"❌ Scores out of range: [{min_score}, {max_score}]. Expected [1, 10]"
            )
            is_valid = False
        
        # Check mean is reasonable (4-7 for most populations)
        if not (expected_mean - 2 < mean < expected_mean + 2):
            self.warnings.append(
                f"⚠️  Composite mean is {mean:.2f}, expected ~{expected_mean}. "
                f"Check score calibration or population risk profile."
            )
        
        # Check for clustering at extremes
        pct_1 = (valid_scores == 1).sum() / len(valid_scores) * 100
        pct_10 = (valid_scores == 10).sum() / len(valid_scores) * 100
        
        if pct_1 > 20:
            self.warnings.append(
                f"⚠️  {pct_1:.1f}% of physicians scored 1 (best risk). "
                f"Possible binning or calibration issue."
            )
        
        if pct_10 > 20:
            self.warnings.append(
                f"⚠️  {pct_10:.1f}% of physicians scored 10 (worst risk). "
                f"Possible binning or calibration issue."
            )
        
        # Check distribution spread
        if std < 0.5:
            self.warnings.append(
                f"⚠️  Very low standard deviation ({std:.2f}). "
                f"Scores may be too clustered."
            )
        
        if self.verbose:
            logger.info(f"  Score distribution: mean={mean:.2f}, std={std:.2f}, range=[{int(min_score)}, {int(max_score)}]")
        
        return is_valid, self.issues, self.stats
    
    def validate_component_distribution(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate component score distributions."""
        issues = []
        
        components = ["adequacy_score", "capacity_score", "appetite_score", "environment_score"]
        
        for component in components:
            if component not in df.columns:
                continue
            
            scores = df[component].dropna()
            
            if len(scores) == 0:
                issues.append(f"⚠️  {component}: No valid scores")
                continue
            
            min_score = scores.min()
            max_score = scores.max()
            
            # Check range
            if min_score < 1 or max_score > 10:
                issues.append(
                    f"❌ {component}: Out of range [{min_score:.1f}, {max_score:.1f}]. Expected [1, 10]"
                )
            
            # Check for all zeros or missing
            if (scores == 0).sum() > len(scores) * 0.5:
                issues.append(f"⚠️  {component}: >50% values are 0 or missing")
            
            if self.verbose:
                logger.info(f"  {component}: mean={scores.mean():.2f}, valid={len(scores):,}")
        
        return len([i for i in issues if i.startswith("❌")]) == 0, issues
    
    def validate_credibility_weighting(
        self,
        df: pd.DataFrame,
        credibility_col: str = "credibility_z"
    ) -> Tuple[bool, List[str]]:
        """
        Validate credibility weighting was applied correctly.
        
        Args:
            df: DataFrame with credibility scores
            credibility_col: Column name for credibility (Z-factor)
        
        Returns:
            (is_valid, issues)
        """
        issues = []
        
        if credibility_col not in df.columns:
            issues.append(f"⚠️  Credibility column '{credibility_col}' not found")
            return True, issues
        
        cred_scores = df[credibility_col].dropna()
        
        if len(cred_scores) == 0:
            issues.append(f"⚠️  No credibility scores present")
            return True, issues
        
        # Z-factor should be 0-1
        if (cred_scores < 0).any() or (cred_scores > 1).any():
            issues.append(
                f"❌ Credibility Z-factor out of range. "
                f"Found [{cred_scores.min():.3f}, {cred_scores.max():.3f}], expected [0, 1]"
            )
            return False, issues
        
        # Check distribution
        pct_zero = (cred_scores < 0.1).sum() / len(cred_scores) * 100
        pct_one = (cred_scores > 0.9).sum() / len(cred_scores) * 100
        
        if pct_zero > 50:
            issues.append(
                f"⚠️  {pct_zero:.1f}% have very low credibility (<0.1). "
                f"Many thin accounts in portfolio?"
            )
        
        if pct_one > 50:
            issues.append(
                f"⚠️  {pct_one:.1f}% have full credibility (>0.9). "
                f"Most accounts above minimum premium threshold?"
            )
        
        if self.verbose:
            logger.info(f"  Credibility: mean={cred_scores.mean():.3f}, valid={len(cred_scores):,}")
        
        return True, issues
    
    def validate_no_nulls_in_identifiers(self, df: pd.DataFrame, identifiers: List[str]) -> List[str]:
        """Check that identifier columns have no nulls."""
        issues = []
        
        for col in identifiers:
            if col not in df.columns:
                continue
            
            nulls = df[col].isna().sum()
            if nulls > 0:
                issues.append(
                    f"⚠️  Identifier '{col}': {nulls} null values"
                )
        
        return issues
    
    def validate_score_monotonicity(self, df: pd.DataFrame) -> List[str]:
        """
        Check that higher component scores correlate with higher composite score.
        (Higher scores = worse risk, so this should be true)
        """
        issues = []
        
        # Check a sample of records
        sample_df = df.dropna(subset=['composite_score']).head(100)
        
        if len(sample_df) == 0:
            return issues
        
        # For each record, max component should roughly align with composite
        for col in ["adequacy_score", "capacity_score", "appetite_score", "environment_score"]:
            if col not in sample_df.columns:
                continue
            
            sample_df['max_component'] = sample_df[[c for c in [
                "adequacy_score", "capacity_score", "appetite_score", "environment_score"
            ] if c in sample_df.columns]].max(axis=1)
            
            # Correlation check: max component should be similar to composite
            # (not enforced strictly as composite is weighted average)
            correlation = sample_df['max_component'].corr(sample_df['composite_score'])
            
            if correlation < 0.3:
                issues.append(
                    f"⚠️  Low correlation between max component ({correlation:.2f}) "
                    f"and composite score. Check weighting."
                )
                break
        
        return issues
    
    def generate_report(self) -> str:
        """Generate validation report."""
        report = []
        report.append("\n" + "=" * 80)
        report.append("SCORE VALIDATION REPORT")
        report.append("=" * 80)
        
        # Stats
        if self.stats:
            report.append("\nComposite Score Statistics:")
            for key, value in self.stats.items():
                report.append(f"  {key}: {value}")
        
        # Issues
        if self.issues:
            report.append(f"\nValidation Issues ({len(self.issues)}):")
            for issue in self.issues:
                report.append(f"  {issue}")
        
        # Warnings
        if self.warnings:
            report.append(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                report.append(f"  {warning}")
        
        if not self.issues and not self.warnings:
            report.append("\n✓ All validations passed!")
        
        report.append("=" * 80)
        
        return "\n".join(report)


def validate_scores(
    df: pd.DataFrame,
    expected_mean: float = 5.5,
    verbose: bool = True
) -> Tuple[bool, List[str], Dict]:
    """
    Comprehensive score validation.
    
    Args:
        df: DataFrame with scored results
        expected_mean: Expected mean of composite score
        verbose: Whether to log details
    
    Returns:
        (is_valid, issues, stats)
    """
    validator = ScoreValidator(verbose=verbose)
    is_valid, issues, stats = validator.validate_composite_distribution(df, expected_mean)
    
    if verbose:
        print(validator.generate_report())
    
    return is_valid, issues, stats


__all__ = ['ScoreValidator', 'validate_scores']
