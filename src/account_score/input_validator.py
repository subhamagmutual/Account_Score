"""Input data validation: Ensure incoming data meets quality requirements.

Checks:
- Required columns present
- Data types correct
- No excessive nulls
- No negative values in cost metrics
- No extreme outliers
- No duplicate records
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from .logger import logger


class InputValidator:
    """Validates physician-level input data quality."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = True):
        """
        Args:
            config: Configuration dict with identifiers and filters
            verbose: Whether to log detailed messages
        """
        self.config = config
        self.verbose = verbose
        self.issues = []
        self.stats = {}
    
    def validate_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], Dict]:
        """
        Validate and report on input DataFrame.
        
        Args:
            df: Input DataFrame to validate
        
        Returns:
            (df, list_of_issues, stats_dict)
        """
        self.issues = []
        self.stats = {}
        
        if df is None or len(df) == 0:
            self.issues.append("❌ Input DataFrame is empty")
            return df, self.issues, self.stats
        
        self._check_identifiers(df)
        self._check_required_columns(df)
        self._check_duplicates(df)
        self._check_nulls(df)
        self._check_numeric_validity(df)
        self._check_outliers(df)
        self._generate_stats(df)
        
        return df, self.issues, self.stats
    
    def _check_identifiers(self, df: pd.DataFrame):
        """Verify required identifier columns exist."""
        identifiers = self.config.get("pipeline_params", {}).get("identifiers", {})
        
        if not identifiers:
            self.issues.append("⚠️  No identifiers configured")
            return
        
        missing_ids = []
        for id_type, col_name in identifiers.items():
            if col_name not in df.columns:
                missing_ids.append(f"{id_type} ({col_name})")
        
        if missing_ids:
            self.issues.append(f"❌ Missing identifier columns: {', '.join(missing_ids)}")
        elif self.verbose:
            logger.info(f"  ✓ All identifier columns present: {list(identifiers.keys())}")
    
    def _check_required_columns(self, df: pd.DataFrame):
        """Check for required KPI source columns."""
        required_cols = self._get_required_source_columns()
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            self.issues.append(
                f"⚠️  Missing {len(missing_cols)} source columns: "
                f"{', '.join(missing_cols[:5])}"
                f"{'...' if len(missing_cols) > 5 else ''}"
            )
        else:
            if self.verbose:
                logger.info(f"  ✓ All {len(required_cols)} required source columns present")
    
    def _check_duplicates(self, df: pd.DataFrame):
        """Flag duplicate physician-years."""
        identifiers = self.config.get("pipeline_params", {}).get("identifiers", {})
        
        id_cols = [
            identifiers.get("npi", "NPI"),
            identifiers.get("year", "COVEFF_DATE")
        ]
        id_cols = [c for c in id_cols if c in df.columns]
        
        if not id_cols:
            return
        
        dupes = df.duplicated(subset=id_cols, keep=False)
        if dupes.any():
            dupe_count = dupes.sum()
            self.issues.append(
                f"⚠️  Found {dupe_count} duplicate physician-year combinations"
            )
            self.stats["duplicate_records"] = int(dupe_count)
        else:
            if self.verbose:
                logger.info(f"  ✓ No duplicate physician-year combinations")
    
    def _check_nulls(self, df: pd.DataFrame):
        """Report on missing values by column."""
        null_pcts = (df.isnull().sum() / len(df) * 100).sort_values(ascending=False)
        
        # Check columns with >50% missing
        high_null_cols = null_pcts[null_pcts > 50]
        if len(high_null_cols) > 0:
            for col, pct in high_null_cols.head(10).items():
                self.issues.append(
                    f"⚠️  Column '{col}': {pct:.1f}% missing values"
                )
        
        # Summary stats
        cols_with_nulls = null_pcts[null_pcts > 0]
        self.stats["columns_with_nulls"] = len(cols_with_nulls)
        self.stats["max_null_pct"] = float(null_pcts.max())
        self.stats["avg_null_pct"] = float(null_pcts.mean())
        
        if self.verbose:
            logger.info(f"  ✓ Null summary: {len(cols_with_nulls)} columns have nulls")
            logger.info(f"    Max: {null_pcts.max():.1f}% | Avg: {null_pcts.mean():.1f}%")
    
    def _check_numeric_validity(self, df: pd.DataFrame):
        """Check for invalid numeric values."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        invalid_count = 0
        for col in numeric_cols:
            # Check for negative values in cost/loss metrics
            if any(x in col.lower() for x in ["loss", "cost", "premium"]):
                negatives = (df[col] < 0).sum()
                if negatives > 0:
                    self.issues.append(
                        f"⚠️  Column '{col}': {negatives} negative values found"
                    )
                    invalid_count += negatives
            
            # Check for inf values
            infs = np.isinf(df[col]).sum()
            if infs > 0:
                self.issues.append(f"⚠️  Column '{col}': {infs} infinite values found")
                invalid_count += infs
        
        self.stats["invalid_numeric_values"] = invalid_count
        
        if self.verbose and invalid_count == 0:
            logger.info(f"  ✓ No invalid numeric values detected")
    
    def _check_outliers(self, df: pd.DataFrame):
        """Flag extreme outliers that may need investigation."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outlier_count = 0
        outlier_cols = []
        
        for col in numeric_cols:
            # Skip if mostly null
            if df[col].isnull().mean() > 0.9:
                continue
            
            # Calculate outlier bounds
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            if IQR == 0:
                continue
            
            # 3x IQR for extreme outliers
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR
            
            outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_pct = outliers.sum() / df[col].notna().sum() * 100
            
            # Flag if >5% outliers
            if outlier_pct > 5:
                self.issues.append(
                    f"⚠️  Column '{col}': {outliers.sum()} extreme outliers "
                    f"({outlier_pct:.1f}% of valid values)"
                )
                outlier_cols.append(col)
                outlier_count += outliers.sum()
        
        self.stats["outlier_records"] = outlier_count
        self.stats["outlier_columns"] = len(outlier_cols)
        
        if self.verbose and outlier_count == 0:
            logger.info(f"  ✓ No extreme outliers detected")
    
    def _generate_stats(self, df: pd.DataFrame):
        """Generate summary statistics."""
        self.stats["total_records"] = len(df)
        self.stats["total_columns"] = len(df.columns)
        self.stats["memory_mb"] = df.memory_usage(deep=True).sum() / 1024**2
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            self.stats["numeric_columns"] = len(numeric_cols)
    
    def _get_required_source_columns(self) -> List[str]:
        """Collect all source columns referenced in config."""
        cols = set()
        weights = self.config.get("scoring_weights", {})
        
        for dim_key in [
            "adequacy_sub_scores",
            "capacity_sub_scores",
            "appetite_sub_scores",
            "environment_sub_scores"
        ]:
            for var_name, var_config in weights.get(dim_key, {}).items():
                if "source_column" in var_config:
                    cols.add(var_config["source_column"])
                if "numerator" in var_config:
                    cols.add(var_config["numerator"])
                if "denominator" in var_config:
                    cols.add(var_config["denominator"])
        
        return list(cols)
    
    def print_report(self):
        """Print validation report to logger."""
        logger.info("\n" + "=" * 70)
        logger.info("DATA VALIDATION REPORT")
        logger.info("=" * 70)
        
        # Summary stats
        if self.stats:
            logger.info("\nSummary Statistics:")
            logger.info(f"  Total records: {self.stats.get('total_records', 'N/A'):,}")
            logger.info(f"  Total columns: {self.stats.get('total_columns', 'N/A')}")
            logger.info(f"  Memory usage: {self.stats.get('memory_mb', 0):.1f} MB")
        
        # Issues
        if self.issues:
            logger.warning(f"\nValidation Issues ({len(self.issues)}):")
            for issue in self.issues:
                logger.warning(f"  {issue}")
        else:
            logger.info("\n✓ No validation issues detected")
        
        logger.info("=" * 70 + "\n")


def validate_input_data(
    df: pd.DataFrame,
    config: Dict[str, Any],
    verbose: bool = True
) -> Tuple[pd.DataFrame, List[str], Dict]:
    """
    Validate input data and return results.
    
    Args:
        df: Input DataFrame
        config: Configuration dict
        verbose: Whether to log details
    
    Returns:
        (df, issues, stats)
    """
    validator = InputValidator(config, verbose=verbose)
    df, issues, stats = validator.validate_dataframe(df)
    
    if verbose:
        validator.print_report()
    
    return df, issues, stats


__all__ = ['InputValidator', 'validate_input_data']
