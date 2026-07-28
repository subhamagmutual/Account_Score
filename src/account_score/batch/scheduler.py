"""Batch job scheduler for production scoring."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd

from ..pipeline import run_scoring_pipeline
from ..monitoring import ScoreMonitor
from ..monitoring.psi import PSICalculator
from ..deployment.gates import DeploymentGates

logger = logging.getLogger(__name__)


class BatchScheduler:
    """Orchestrate scheduled batch scoring jobs."""

    def __init__(self, config_path: str = "config/batch_schedule.yaml"):
        """
        Initialize scheduler.

        Args:
            config_path: Path to batch schedule configuration
        """
        self.config_path = config_path
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        self.last_run = {}

    def add_daily_job(
        self,
        input_file: str,
        output_dir: str,
        hour: int = 2,
        minute: int = 0,
    ):
        """
        Add daily scoring job.

        Args:
            input_file: Path to input CSV
            output_dir: Output directory for results
            hour: Hour to run (24-hour format)
            minute: Minute to run
        """
        job_id = f"daily_{Path(input_file).stem}"

        self.scheduler.add_job(
            self._run_batch_job,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            args=[input_file, output_dir],
        )

        logger.info(f"Added daily job {job_id} at {hour:02d}:{minute:02d}")

    def add_weekly_job(
        self,
        input_file: str,
        output_dir: str,
        day_of_week: str = "monday",
        hour: int = 3,
    ):
        """
        Add weekly scoring job.

        Args:
            input_file: Path to input CSV
            output_dir: Output directory for results
            day_of_week: Day to run (monday-sunday)
            hour: Hour to run
        """
        job_id = f"weekly_{Path(input_file).stem}"

        self.scheduler.add_job(
            self._run_batch_job,
            'cron',
            day_of_week=day_of_week,
            hour=hour,
            id=job_id,
            args=[input_file, output_dir],
        )

        logger.info(f"Added weekly job {job_id} on {day_of_week} at {hour:02d}:00")

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Batch scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Batch scheduler stopped")

    def get_jobs(self) -> Dict[str, Any]:
        """Get list of scheduled jobs."""
        return {
            job.id: {
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'func': job.func_ref,
            }
            for job in self.scheduler.get_jobs()
        }

    def _run_batch_job(
        self,
        input_file: str,
        output_dir: str,
    ):
        """
        Execute batch scoring job.

        Args:
            input_file: Path to input CSV
            output_dir: Output directory
        """
        job_id = f"{Path(input_file).stem}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting batch job {job_id}")

        try:
            # Record start time
            start_time = datetime.utcnow()

            # 1. Load input data
            logger.info(f"Loading {input_file}...")
            df = pd.read_csv(input_file, low_memory=False)
            logger.info(f"Loaded {len(df):,} records")

            # 2. Run pre-scoring checks
            logger.info("Running pre-scoring validation...")
            gates = DeploymentGates()
            passes_input = gates.check_input_data(df)
            if not passes_input:
                logger.error("Input validation failed")
                return

            # 3. Run scoring pipeline
            logger.info("Running scoring pipeline...")
            scored_df = run_scoring_pipeline(
                df,
                mode='batch',
                config_path='config/scoring_weights.json',
            )

            # 4. Run post-scoring validation
            logger.info("Running post-scoring validation...")
            passes_output = gates.check_output_scores(scored_df)
            if not passes_output:
                logger.error("Output validation failed")
                return

            # 5. Run monitoring/diagnostics
            logger.info("Running diagnostics...")
            monitor = ScoreMonitor()
            current_metrics = monitor.analyze_dataframe(
                scored_df,
                ['composite_score', 'adequacy_score', 'capacity_score', 'appetite_score', 'environment_score'],
            )

            # Load baseline and check for drift
            try:
                monitor.load_baseline('config/monitoring_baseline.json')
                comparison = monitor.compare_to_baseline(current_metrics)
                if comparison['total_alerts'] > 0:
                    logger.warning(f"Distribution alerts: {comparison['total_alerts']}")
            except FileNotFoundError:
                logger.warning("Baseline not found, skipping drift detection")

            # 6. Save output
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_file = Path(output_dir) / f"physician_scores_{job_id}.csv"
            scored_df.to_csv(output_file, index=False)
            logger.info(f"Saved scores to {output_file}")

            # 7. Generate report
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            report = {
                'job_id': job_id,
                'status': 'success',
                'input_file': input_file,
                'output_file': str(output_file),
                'records_scored': len(scored_df),
                'elapsed_seconds': elapsed,
                'metrics': {
                    name: m.to_dict() for name, m in current_metrics.items()
                },
                'timestamp': datetime.utcnow().isoformat(),
            }

            report_file = Path(output_dir) / f"report_{job_id}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Batch job {job_id} completed in {elapsed:.1f}s")
            self.last_run[job_id] = report

        except Exception as e:
            logger.error(f"Batch job {job_id} failed: {e}", exc_info=True)
            # TODO: Send alert


if __name__ == "__main__":
    # Example usage
    scheduler = BatchScheduler()

    # Add jobs
    scheduler.add_daily_job(
        input_file="data/input/magmutual_physicians.csv",
        output_dir="data/output/batch/",
        hour=2,
        minute=0,
    )

    scheduler.add_weekly_job(
        input_file="data/input/dhc_physicians.csv",
        output_dir="data/output/batch/dhc/",
        day_of_week="sunday",
        hour=3,
    )

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.stop()
