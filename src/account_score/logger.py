"""Structured logging for the PAS pipeline.

Provides:
- Console logging with color coding
- File logging for audit trails
- Context-aware logging (step tracking)
- Performance metrics logging
"""

import logging
import sys
import os
from typing import Optional
from datetime import datetime
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Formatter with color coding for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if sys.stdout.isatty():  # Only use colors in terminal
            log_color = self.COLORS.get(record.levelname, self.RESET)
            record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "./logs"
) -> logging.Logger:
    """
    Configure logger with console and optional file handlers.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: If provided, also log to this file path
        log_dir: Directory for log files (created if doesn't exist)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        '[%(asctime)s] %(levelname)-8s [%(name)s:%(funcName)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_path = os.path.join(log_dir, log_file)
        
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # File gets all messages
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


class PipelineLogger:
    """Context-aware logging for pipeline steps."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.step_count = 0
        self.step_stack = []
    
    def start_step(self, step_name: str, details: str = ""):
        """Mark the start of a pipeline step."""
        self.step_count += 1
        self.step_stack.append(step_name)
        
        msg = f"[Step {self.step_count}] {step_name}"
        if details:
            msg += f" | {details}"
        
        self.logger.info("=" * 70)
        self.logger.info(msg)
        self.logger.info("=" * 70)
    
    def end_step(self, success: bool = True, summary: str = ""):
        """Mark the end of a pipeline step."""
        if self.step_stack:
            step_name = self.step_stack.pop()
            status = "✓ COMPLETED" if success else "✗ FAILED"
            msg = f"{step_name}: {status}"
            if summary:
                msg += f" | {summary}"
            self.logger.info(msg)
    
    def log_metric(self, metric_name: str, value, unit: str = ""):
        """Log a metric (records, time, memory, etc)."""
        formatted_value = self._format_value(value)
        msg = f"  {metric_name}: {formatted_value}"
        if unit:
            msg += f" {unit}"
        self.logger.info(msg)
    
    def log_data_shape(self, df_name: str, shape_tuple):
        """Log DataFrame dimensions."""
        rows, cols = shape_tuple
        self.logger.info(f"  {df_name} shape: {rows:,} rows × {cols} columns")
    
    def log_null_summary(self, df, threshold_pct: float = 50):
        """Log null value summary for DataFrame."""
        null_pcts = (df.isnull().sum() / len(df) * 100).sort_values(ascending=False)
        high_null = null_pcts[null_pcts > threshold_pct]
        
        if len(high_null) > 0:
            self.logger.warning(f"  {len(high_null)} columns with >{threshold_pct}% nulls:")
            for col, pct in high_null.items():
                self.logger.warning(f"    - {col}: {pct:.1f}% missing")
        else:
            self.logger.info(f"  No columns with >{threshold_pct}% nulls")
    
    @staticmethod
    def _format_value(value):
        """Format numeric values nicely."""
        if isinstance(value, int):
            return f"{value:,}"
        elif isinstance(value, float):
            if value > 1000:
                return f"{value:,.2f}"
            else:
                return f"{value:.4f}"
        return str(value)


# Module-level logger
logger = setup_logger(__name__)

__all__ = ['setup_logger', 'PipelineLogger', 'ColoredFormatter', 'logger']
