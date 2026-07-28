"""
Data quality validation for production scoring.

Provides pre and post-scoring validation:
- Pre-scoring: Check input data integrity
- Post-scoring: Validate output scores
"""

from typing import List, Dict, Tuple
import pandas as pd
import numpy as np


class DataQualityChecker:
    """Validate data quality before and after scoring."""

    # Sentinel values commonly used in data
    SENTINEL_VALUES = [-99, -9999, 999, 9999, np.nan, None]

    def __init__(self, strict: bool = False):
        """
        Initialize checker.

        Args:
            strict: If True, fail on warnings; if False, continue
        """
        self.strict = strict
        self.issues: List[Dict] = []

    def check_input_data(
        self,
        df: pd.DataFrame,
        required_columns: List[str],
        column_types: Dict[str, type],
    ) -> Tuple[bool, List[Dict]]:
        """
        Check input data quality before scoring.

        Args:
            df: Input dataframe
            required_columns: List of required column names
            column_types: Dict mapping column name to expected type

        Returns:
            (passes_all_checks, list_of_issues)
        """
        issues = []

        # Check required columns
        missing = set(required_columns) - set(df.columns)
        if missing:
            issues.append({
                'severity': 'BLOCKER',
                'check': 'required_columns',
                'message': f"Missing required columns: {missing}",
            })

        # Check column types
        for col, expected_type in column_types.items():
            if col in df.columns:
                if expected_type in (int, float):
                    # Numeric column
                    non_numeric = pd.to_numeric(df[col], errors='coerce').isna()
                    non_numeric_count = non_numeric.sum()
                    if non_numeric_count > 0:
                        issues.append({
                            'severity': 'WARNING',
                            'check': 'column_type',
                            'column': col,
                            'message': f"{col}: {non_numeric_count} non-numeric values",
                        })

        # Check for duplicates
        if 'NPI' in df.columns:
            duplicates = df[df.duplicated(subset=['NPI'], keep=False)]
            if len(duplicates) > 0:
                issues.append({
                    'severity': 'WARNING',
                    'check': 'duplicates',
                    'message': f"{len(duplicates)} duplicate NPI records",
                })

        # Check for missing values
        null_pcts = (df.isnull().sum() / len(df) * 100)
        for col, pct in null_pcts[null_pcts > 5].items():
            issues.append({
                'severity': 'WARNING',
                'check': 'missing_values',
                'column': col,
                'percentage': float(pct),
                'message': f"{col}: {pct:.1f}% null values",
            })

        has_blocker = any(i['severity'] == 'BLOCKER' for i in issues)
        passes = len(issues) == 0 or (not has_blocker and not self.strict)

        self.issues = issues
        return passes, issues

    def check_output_scores(
        self,
        df: pd.DataFrame,
        score_columns: List[str],
        valid_range: Tuple[float, float] = (1.0, 10.0),
    ) -> Tuple[bool, List[Dict]]:
        """
        Check output score quality after scoring.

        Args:
            df: Scored dataframe
            score_columns: List of score column names
            valid_range: Tuple of (min, max) valid values

        Returns:
            (passes_all_checks, list_of_issues)
        """
        issues = []

        for col in score_columns:
            if col not in df.columns:
                issues.append({
                    'severity': 'BLOCKER',
                    'check': 'missing_column',
                    'column': col,
                    'message': f"Expected score column {col} not found",
                })
                continue

            scores = df[col].dropna()

            # Check range
            out_of_range = (scores < valid_range[0]) | (scores > valid_range[1])
            if out_of_range.sum() > 0:
                issues.append({
                    'severity': 'BLOCKER',
                    'check': 'out_of_range',
                    'column': col,
                    'count': int(out_of_range.sum()),
                    'message': f"{col}: {out_of_range.sum()} scores outside [{valid_range[0]}, {valid_range[1]}]",
                })

            # Check for NaN
            nan_count = df[col].isna().sum()
            if nan_count > len(df) * 0.05:  # Alert if >5% NaN
                issues.append({
                    'severity': 'WARNING',
                    'check': 'null_scores',
                    'column': col,
                    'percentage': float(nan_count / len(df) * 100),
                    'message': f"{col}: {nan_count} null scores ({nan_count/len(df)*100:.1f}%)",
                })

            # Check for constant scores (all same value)
            if len(scores.unique()) == 1:
                issues.append({
                    'severity': 'WARNING',
                    'check': 'constant_scores',
                    'column': col,
                    'value': float(scores.iloc[0]),
                    'message': f"{col}: all scores are {scores.iloc[0]}",
                })

        has_blocker = any(i['severity'] == 'BLOCKER' for i in issues)
        passes = len(issues) == 0 or (not has_blocker and not self.strict)

        self.issues = issues
        return passes, issues

    def check_sentinel_values(
        self,
        df: pd.DataFrame,
        numeric_columns: List[str],
    ) -> List[Dict]:
        """
        Check for sentinel values that may indicate data quality issues.

        Args:
            df: Dataframe to check
            numeric_columns: List of numeric column names

        Returns:
            List of sentinel value findings
        """
        issues = []

        for col in numeric_columns:
            if col not in df.columns:
                continue

            col_values = df[col].dropna()

            for sentinel in self.SENTINEL_VALUES:
                if pd.isna(sentinel):
                    continue

                count = (col_values == sentinel).sum()
                if count > 0:
                    issues.append({
                        'severity': 'WARNING',
                        'check': 'sentinel_values',
                        'column': col,
                        'sentinel': sentinel,
                        'count': int(count),
                        'message': f"{col}: {count} sentinel values ({sentinel})",
                    })

        return issues

    def generate_report(self) -> Dict:
        """Generate quality report."""
        blocker_count = sum(1 for i in self.issues if i['severity'] == 'BLOCKER')
        warning_count = sum(1 for i in self.issues if i['severity'] == 'WARNING')

        return {
            'total_issues': len(self.issues),
            'blockers': blocker_count,
            'warnings': warning_count,
            'passes': blocker_count == 0,
            'issues': self.issues,
        }
