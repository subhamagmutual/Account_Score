"""CLI entry point for the Physician MPL Account Scoring Pipeline.

Usage:
    python run_pipeline.py                          # Default: fit and score full dataset
    python run_pipeline.py --mode fit_only          # Only fit binning thresholds
    python run_pipeline.py --mode score_only        # Score using existing thresholds
    python run_pipeline.py --sample 1000            # Test with 1000 records
    python run_pipeline.py --config ./config        # Specify config directory
    python run_pipeline.py --output ./my_output     # Specify output directory
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.account_score.pipeline import run_scoring_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Physician MPL Account Scoring Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                             Run full pipeline (fit + score)
  python run_pipeline.py --mode fit_only             Fit bins only (no scoring)
  python run_pipeline.py --mode score_only           Score with existing bins
  python run_pipeline.py --sample 5000               Quick test with 5000 records
  python run_pipeline.py --input path/to/data.csv    Use a different input file
  python run_pipeline.py --dynamic                   Use mean-anchored portfolio-relative scoring
        """
    )

    parser.add_argument(
        "--mode",
        choices=["fit_and_score", "fit_only", "score_only"],
        default="fit_and_score",
        help="Pipeline mode (default: fit_and_score)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config directory (default: ./config)"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Override input data file path"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Override output directory"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample N records for testing (default: use full dataset)"
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        default=False,
        help="Use dynamic portfolio-relative scoring (mean-anchored binning)"
    )

    args = parser.parse_args()

    try:
        df = run_scoring_pipeline(
            config_dir=args.config,
            mode=args.mode,
            input_path=args.input,
            output_dir=args.output,
            sample_n=args.sample,
            dynamic=args.dynamic
        )
        print(f"\nSuccess! Final DataFrame shape: {df.shape}")
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
