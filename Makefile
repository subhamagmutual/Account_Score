.PHONY: help install install-dev test lint format clean

help:
	@echo "PAS Account Score - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install with development tools (testing, linting)"
	@echo "  test             Run unit tests with coverage"
	@echo "  lint             Run code quality checks (Black, isort, Flake8, mypy)"
	@echo "  format           Auto-format code (Black, isort)"
	@echo "  clean            Remove build artifacts and cache files"
	@echo "  help             Show this help message"

install:
	pip install -r requirements.txt
	@echo "✓ Production dependencies installed"

install-dev:
	pip install -r requirements-dev.txt
	@echo "✓ Development dependencies installed"

test:
	pytest tests/ -v --cov=src.account_score --cov-report=html --cov-report=term-missing
	@echo "✓ Tests complete. Coverage report in htmlcov/index.html"

lint:
	@echo "Running Black (format check)..."
	black --check src/ tests/ run_pipeline.py scripts/ || true
	@echo ""
	@echo "Running isort (import check)..."
	isort --check-only src/ tests/ run_pipeline.py scripts/ || true
	@echo ""
	@echo "Running Flake8 (linting)..."
	flake8 src/ tests/ run_pipeline.py --max-line-length=100 || true
	@echo ""
	@echo "Running mypy (type checking)..."
	mypy src/account_score/ --ignore-missing-imports || true
	@echo "✓ Lint checks complete"

format:
	@echo "Formatting code with Black..."
	black src/ tests/ run_pipeline.py scripts/
	@echo ""
	@echo "Sorting imports with isort..."
	isort src/ tests/ run_pipeline.py scripts/
	@echo "✓ Code formatting complete"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info account_score.egg-info
	rm -rf .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✓ Cleanup complete"
