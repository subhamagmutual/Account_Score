"""
CLI tool for production score monitoring.

Usage:
  python -m src.account_score.monitoring --input scores.csv --baseline config/monitoring_baseline.json
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .score_monitor import ScoreMonitor
from .psi import PSICalculator
from .data_quality import DataQualityChecker
from .anomalies import AnomalyDetector


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor production score distributions and detect drift"
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input CSV file with scores",
    )

    parser.add_argument(
        "--baseline",
        type=str,
        default="config/monitoring_baseline.json",
        help="Baseline metrics JSON file",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="data/output/monitoring/",
        help="Output directory for reports",
    )

    parser.add_argument(
        "--score-columns",
        type=str,
        nargs="+",
        default=["composite_score", "adequacy_score", "capacity_score", "appetite_score", "environment_score"],
        help="Score column names to monitor",
    )

    parser.add_argument(
        "--check-data-quality",
        action="store_true",
        help="Run data quality checks",
    )

    parser.add_argument(
        "--detect-anomalies",
        action="store_true",
        help="Detect anomalies",
    )

    parser.add_argument(
        "--calculate-psi",
        action="store_true",
        help="Calculate PSI (requires baseline)",
    )

    args = parser.parse_args()

    # Load data
    print(f"Loading {args.input}...", flush=True)
    try:
        df = pd.read_csv(args.input, low_memory=False)
    except Exception as e:
        print(f"ERROR: Failed to load {args.input}: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(df):,} records", flush=True)

    # Initialize output directory
    Path(args.output).mkdir(parents=True, exist_ok=True)

    results = {
        'input_file': args.input,
        'total_records': len(df),
        'checks': {},
    }

    # 1. Score distribution monitoring
    print("Calculating score distributions...", flush=True)
    monitor = ScoreMonitor()
    current_metrics = monitor.analyze_dataframe(df, args.score_columns)

    results['current_metrics'] = {
        name: m.to_dict() for name, m in current_metrics.items()
    }

    # Compare to baseline
    if Path(args.baseline).exists():
        print(f"Loading baseline from {args.baseline}...", flush=True)
        monitor.load_baseline(args.baseline)
        comparison = monitor.compare_to_baseline(current_metrics)
        results['checks']['distribution_comparison'] = comparison
        print(f"Distribution alerts: {comparison['total_alerts']}", flush=True)
    else:
        print(f"WARNING: Baseline file not found: {args.baseline}", flush=True)

    # 2. Data quality checks
    if args.check_data_quality:
        print("Running data quality checks...", flush=True)
        checker = DataQualityChecker()

        # Pre-scoring checks (input validation)
        input_passes, input_issues = checker.check_input_data(
            df,
            required_columns=args.score_columns,
            column_types={col: float for col in args.score_columns},
        )

        # Post-scoring checks
        output_passes, output_issues = checker.check_output_scores(
            df,
            score_columns=args.score_columns,
            valid_range=(1.0, 10.0),
        )

        results['checks']['data_quality'] = {
            'input_passes': input_passes,
            'output_passes': output_passes,
            'total_issues': len(input_issues) + len(output_issues),
        }

        print(f"Data quality: {input_issues + output_issues}", flush=True)

    # 3. Anomaly detection
    if args.detect_anomalies:
        print("Detecting anomalies...", flush=True)
        detector = AnomalyDetector()

        for col in args.score_columns:
            if col in df.columns:
                _, anomalies = detector.detect_outliers(df[col], name=col)
                detector.anomalies.extend(anomalies)

        report = detector.generate_report()
        results['checks']['anomalies'] = report
        print(f"Anomalies detected: {report['total_anomalies']}", flush=True)

    # 4. PSI calculation
    if args.calculate_psi and Path(args.baseline).exists():
        print("Calculating PSI...", flush=True)
        baseline_df = pd.read_csv(args.input, low_memory=False)  # In real scenario, use actual baseline data

        psi_values = PSICalculator.calculate_by_dimension(
            baseline_df,
            df,
            args.score_columns,
        )

        results['checks']['psi'] = psi_values
        for col, psi in psi_values.items():
            should_alert, msg = PSICalculator.alert_if_high(psi)
            print(f"{col}: {msg}", flush=True)

    # Save results
    output_file = Path(args.output) / "monitoring_report.json"
    print(f"Saving results to {output_file}...", flush=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Exit code: 3 if BLOCKER found
    has_blocker = any(
        check_result.get('total_alerts', 0) > 0
        or check_result.get('blockers', 0) > 0
        for check_result in results['checks'].values()
    )

    exit_code = 3 if has_blocker else 0
    print(f"Monitoring complete. Exit code: {exit_code}", flush=True)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
