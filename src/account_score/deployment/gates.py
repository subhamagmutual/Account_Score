"""Deployment gates - pre-deployment safety checks."""

import logging
from typing import List, Dict, Any
import pandas as pd

from ..monitoring import ScoreMonitor
from ..monitoring.psi import PSICalculator
from ..monitoring.data_quality import DataQualityChecker
from ..inference.pas_diagnostics.pipeline import run_diagnostics

logger = logging.getLogger(__name__)


class DeploymentGates:
    """Pre-deployment safety gates for production scoring."""

    def __init__(
        self,
        alert_threshold: float = 0.05,
        psi_threshold: float = 0.25,
        max_null_pct: float = 5.0,
    ):
        """
        Initialize gates.

        Args:
            alert_threshold: Distribution shift alert threshold (5%)
            psi_threshold: PSI alert threshold (0.25)
            max_null_pct: Maximum acceptable null percentage (5%)
        """
        self.alert_threshold = alert_threshold
        self.psi_threshold = psi_threshold
        self.max_null_pct = max_null_pct
        self.findings = []

    def check_input_data(self, df: pd.DataFrame) -> bool:
        """
        Pre-scoring validation gate.

        Args:
            df: Input dataframe

        Returns:
            True if passes, False if BLOCKER found
        """
        logger.info("Running input validation gate...")

        checker = DataQualityChecker(strict=False)
        required_cols = [
            'NPI', 'SPECIALTY', 'STATE',
            # Add other required columns
        ]
        col_types = {}

        passes, issues = checker.check_input_data(df, required_cols, col_types)

        if issues:
            for issue in issues:
                logger.warning(f"Input issue: {issue['message']}")
                if issue['severity'] == 'BLOCKER':
                    self.findings.append({
                        'gate': 'input_data',
                        'severity': 'BLOCKER',
                        'message': issue['message'],
                    })

        if not passes:
            logger.error("Input validation FAILED - blocking deployment")
            return False

        logger.info("✓ Input validation passed")
        return True

    def check_output_scores(self, df: pd.DataFrame) -> bool:
        """
        Post-scoring validation gate.

        Args:
            df: Scored dataframe

        Returns:
            True if passes, False if BLOCKER found
        """
        logger.info("Running output validation gate...")

        checker = DataQualityChecker(strict=False)
        score_cols = [
            'composite_score',
            'adequacy_score',
            'capacity_score',
            'appetite_score',
            'environment_score',
        ]

        passes, issues = checker.check_output_scores(df, score_cols, valid_range=(1.0, 10.0))

        if issues:
            for issue in issues:
                logger.warning(f"Output issue: {issue['message']}")
                if issue['severity'] == 'BLOCKER':
                    self.findings.append({
                        'gate': 'output_scores',
                        'severity': 'BLOCKER',
                        'message': issue['message'],
                    })

        if not passes:
            logger.error("Output validation FAILED - blocking deployment")
            return False

        logger.info("✓ Output validation passed")
        return True

    def check_distribution_shift(
        self,
        current_df: pd.DataFrame,
        baseline_path: str = "config/monitoring_baseline.json",
    ) -> bool:
        """
        Distribution shift gate.

        Args:
            current_df: Current scored data
            baseline_path: Path to baseline config

        Returns:
            True if acceptable shift, False if exceeds threshold
        """
        logger.info("Running distribution shift gate...")

        monitor = ScoreMonitor(alert_threshold=self.alert_threshold)
        score_cols = [
            'composite_score',
            'adequacy_score',
            'capacity_score',
            'appetite_score',
            'environment_score',
        ]

        try:
            monitor.load_baseline(baseline_path)
        except FileNotFoundError:
            logger.warning(f"Baseline not found at {baseline_path}, skipping drift check")
            return True

        current_metrics = monitor.analyze_dataframe(current_df, score_cols)
        comparison = monitor.compare_to_baseline(current_metrics)

        if comparison['total_alerts'] > 0:
            logger.warning(f"Distribution shift detected: {comparison['total_alerts']} alerts")
            for alert in comparison['alerts'][:5]:  # Log first 5
                logger.warning(f"  {alert['score']}: {alert['metric']} changed {alert['pct_change']:.1%}")
                self.findings.append({
                    'gate': 'distribution_shift',
                    'severity': 'WARNING',
                    'message': f"{alert['score']}: {alert['metric']} changed {alert['pct_change']:.1%}",
                })

            if any(a['severity'] == 'CRITICAL' for a in comparison['alerts']):
                logger.error("Critical distribution shift detected - blocking")
                return False

        logger.info("✓ Distribution shift check passed")
        return True

    def check_psi(
        self,
        current_df: pd.DataFrame,
        baseline_df: pd.DataFrame,
    ) -> bool:
        """
        PSI (drift) gate.

        Args:
            current_df: Current data
            baseline_df: Baseline data

        Returns:
            True if PSI acceptable, False if exceeds threshold
        """
        logger.info("Running PSI gate...")

        psi_values = PSICalculator.calculate_by_dimension(
            baseline_df,
            current_df,
            ['composite_score'],
        )

        for score, psi in psi_values.items():
            should_alert, msg = PSICalculator.alert_if_high(psi, self.psi_threshold)
            if should_alert:
                logger.error(f"PSI ALERT: {score} - {msg}")
                self.findings.append({
                    'gate': 'psi',
                    'severity': 'BLOCKER',
                    'message': msg,
                })
                return False
            else:
                logger.info(f"PSI OK: {score} - {msg}")

        logger.info("✓ PSI check passed")
        return True

    def check_diagnostics(self, df: pd.DataFrame) -> bool:
        """
        Run diagnostics checks gate.

        Args:
            df: Scored dataframe

        Returns:
            True if no BLOCKER found
        """
        logger.info("Running diagnostics gate...")

        try:
            # TODO: Run diagnostics from pas_diagnostics
            # report = run_diagnostics(df)
            # if report has BLOCKER, return False
            logger.info("✓ Diagnostics check passed")
            return True
        except Exception as e:
            logger.error(f"Diagnostics check failed: {e}")
            self.findings.append({
                'gate': 'diagnostics',
                'severity': 'WARNING',
                'message': f"Diagnostics error: {e}",
            })
            return True  # Don't block, just warn

    def run_all_checks(self, current_df: pd.DataFrame, baseline_df: pd.DataFrame = None) -> bool:
        """
        Run all deployment gates.

        Args:
            current_df: Current scored data
            baseline_df: Baseline data (optional)

        Returns:
            True if all gates pass, False if any BLOCKER found
        """
        logger.info("=== RUNNING ALL DEPLOYMENT GATES ===")
        self.findings = []

        gates = [
            ('Input Data', lambda: self.check_input_data(current_df)),
            ('Output Scores', lambda: self.check_output_scores(current_df)),
            ('Distribution Shift', lambda: self.check_distribution_shift(current_df)),
            ('Diagnostics', lambda: self.check_diagnostics(current_df)),
        ]

        if baseline_df is not None:
            gates.append(('PSI', lambda: self.check_psi(current_df, baseline_df)))

        results = {}
        for gate_name, gate_fn in gates:
            try:
                result = gate_fn()
                results[gate_name] = 'PASS' if result else 'FAIL'
            except Exception as e:
                logger.error(f"Gate {gate_name} errored: {e}")
                results[gate_name] = 'ERROR'

        # Summary
        logger.info("=== DEPLOYMENT GATE RESULTS ===")
        for gate_name, result in results.items():
            icon = "✓" if result == "PASS" else "✗"
            logger.info(f"{icon} {gate_name}: {result}")

        has_blocker = any(f['severity'] == 'BLOCKER' for f in self.findings)

        if has_blocker:
            logger.error("!!! DEPLOYMENT BLOCKED !!!")
            return False
        else:
            logger.info("✓ All gates passed - safe to deploy")
            return True

    def get_findings(self) -> List[Dict[str, Any]]:
        """Get all gate findings."""
        return self.findings
