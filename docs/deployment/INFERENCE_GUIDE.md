# Account Score (PAS) Inference Guide

Complete guide to running inference, validation, and diagnostics on physician scores.

---

## Overview

The inference system validates and explains PAS scores through:
- **Diagnostic checks** - Validate data quality and model integrity
- **Reason codes** - Exact additive attribution for each score
- **HTML cards** - Visual score cards for underwriter review
- **Reports** - Comprehensive markdown/Excel reports

---

## Architecture

```
src/account_score/inference/        ← Core inference package
├── pas_diagnostics/                ← Main diagnostics module
│   ├── schema.py                   ← Data validation & column mapping
│   ├── metrics.py                  ← Statistical metrics (Gini, PSI, VIF)
│   ├── checks.py                   ← 10 diagnostic checks
│   ├── reasons.py                  ← Score attribution & reason codes
│   ├── card.py                     ← HTML card generation
│   ├── report.py                   ← Report writers (MD, CSV, Excel)
│   ├── cli.py                      ← Command-line interface
│   └── config.py                   ← Configuration

scripts/inference/                  ← Utility scripts
├── make_fixture.py                 ← Generate synthetic test data
├── build_dict.py                   ← Build data dictionary
├── test_edges.py                   ← Edge case testing
└── try_uw.py                       ← Interactive underwriter tool

notebooks/inference/                ← Analysis & exploration
├── 01_check_distribution.ipynb     ← Score distribution checks
├── 02_check_csv_columns.ipynb      ← Column validation
├── 03_run_diagnostics.ipynb        ← Full diagnostic run
├── 04_uw_tooling_reasons.ipynb     ← Reason codes exploration
└── 05_validation_harness.ipynb     ← Out-of-time validation
```

---

## Quick Start

### 1. Run Diagnostics (CLI)

```bash
# Basic check - just validate schema
python -m src.account_score.inference.pas_diagnostics \
    --input physician_scores_20260429.csv \
    --inspect

# Full diagnostics with reports
python -m src.account_score.inference.pas_diagnostics \
    --input physician_scores_20260429.csv \
    --outdir reports/2026-07 \
    --train-years 2017 2018 2019 2020 2021 \
    --test-years 2022 2023 2024 \
    --excel \
    --nrows 1000000
```

Exit code 3 = BLOCKER found (fails the pipeline)

### 2. Get Reason Codes (Python)

```python
import pandas as pd
from src.account_score.inference import reasons, schema

# Load data
df = pd.read_csv("physician_scores.csv")
cm = schema.ColumnMap()

# Get top 3 drivers for each physician
code_df = reasons.reason_codes(df, cm, top_n=3)

# See score reconciliation
reconciliation = reasons.reconciliation(df, cm)
print(f"Max residual: {reconciliation['max_residual']}")
print(f"% within 0.5: {reconciliation['pct_within_tolerance']}")
```

### 3. Generate Score Cards (HTML)

```python
from pathlib import Path
from src.account_score.inference import card, schema

df = pd.read_csv("physician_scores.csv")
cm = schema.ColumnMap()

# Render HTML cards (sample first 25)
card.render(df, cm, Path("cards.html"), limit=25)

# Open in browser
import webbrowser
webbrowser.open("cards.html")
```

### 4. Run Synthetic Tests

```bash
# Generate fixture with known pathologies
python scripts/inference/make_fixture.py \
    --rows 60000 \
    --output fixture_physician_scores.csv

# Run diagnostics on fixture
python -m src.account_score.inference.pas_diagnostics \
    --input fixture_physician_scores.csv \
    --outdir fixture_reports \
    --train-years 2017 2018 2019 2020 2021 \
    --test-years 2022 2023 2024
```

Expected: 9 blockers including circularity, adequacy_reality, sentinel_scored

---

## Diagnostic Checks

### Check: Schema
**Question:** Are the columns what the design workbook says?

Validates that input CSV has all required columns with correct types and distributions match the design specification.

**Severity:** BLOCKER if required columns missing

### Check: Data Quality
**Question:** Missing, zero, out-of-range, or sentinels that received a score?

Identifies:
- Missing values in required columns
- Zero values where they shouldn't be
- Out-of-range values
- **Sentinel values that were scored** (data quality bug)

**Severity:** BLOCKER if >1% sentinel values scored

### Check: Adequacy Reality
**Question:** Is Adequacy measuring loss experience, or a burn factor?

Adequacy should order loss, not just loss ratio (which can be high from low premium). Tests whether Adequacy sub-scores correlate with actual loss amounts.

**Severity:** BLOCKER if poor correlation

### Check: Circularity
**Question:** Were bands cut on the outcome?

If band thresholds were defined by looking at the outcome variable, they'll always predict it. Tests whether variables still separate the portfolio when outcome is randomized.

**Severity:** BLOCKER if detected

### Check: Variable Signal
**Question:** Does each variable order loss? (Permutation-guarded)

For each variable, tests whether its bands separate loss experience. Uses permutation test to guard against multiple-comparisons error.

**Severity:** WARNING if p > 0.05

### Check: Discrimination
**Question:** Can the bands separate the book, or is everyone tied?

Tests whether the composite score separates the portfolio by loss. Calculates Gini and Spearman rank correlation by band.

**Severity:** WARNING if Gini < 0.10

### Check: Effective Weights
**Question:** Nominal vs realized weight after weight-zeroing?

Some sub-scores may have weight = 0 for some physicians (credibility blending). Calculates what the portfolio actually experienced vs what was designed.

**Severity:** INFO (diagnostic only)

### Check: Redundancy
**Question:** VIF and pairwise rank correlation among scores?

Tests for multicollinearity that might indicate variable overlap or design flaw.

**Severity:** WARNING if VIF > 5

### Check: Composite Lift
**Question:** Gini in-sample and out-of-time?

Measures discriminatory power in training window and out-of-time validation window. Large divergence suggests overfitting.

**Severity:** WARNING if out-of-time Gini < 0.5 × in-sample Gini

### Check: Stability
**Question:** PSI year over year?

Population Stability Index measures whether the population shifted. High PSI suggests changing underwriting, claims experience, or data quality.

**Severity:** WARNING if PSI > 0.25

---

## Score Attribution & Reason Codes

### Exact Additive Decomposition

Each variable's contribution sums to the score:

```
composite - 4.5 = Σ [ effective_weight_i × (score_i - 4.5) ]
```

Each term is:
- The **actual realized weight** (after credibility blending, weight-zeroing, etc.)
- Multiplied by the **deviation from portfolio average** (4.5)
- Equals **score points** the variable contributed

### Running Attribution

```python
from src.account_score.inference import reasons

# Exact reconciliation
recon = reasons.reconciliation(df, cm)

# Reason codes (long format, one row per driver)
codes = reasons.reason_codes(df, cm, top_n=3)
# Columns: NPI, rank (1-3), variable, raw_value, score, points_contributed

# Dispersion analysis - which variables have most spread?
disp = reasons.dispersion(df, cm)

# Triage - top 250 physicians by loss, with reason codes
triage = reasons.triage(df, cm, cm.exposure_premium, top_n=250)
```

### Credibility Note

⚠️ **Credibility blending breaks anchoring**: If Adequacy sub-scores are blended toward 5 before aggregation, then raw sub-scores won't reconcile against blended composites.

Fix: Use pre-blended sub-scores in output, persist `CREDIBILITY_Z` per record, ensure complement equals anchor (both 4.5, not 5).

---

## Common Workflows

### Workflow 1: Validate New Scores
```bash
# 1. Check schema first (fails fast)
python -m src.account_score.inference.pas_diagnostics \
    --input new_scores.csv --inspect

# 2. If schema OK, run full suite
python -m src.account_score.inference.pas_diagnostics \
    --input new_scores.csv --outdir reports --excel

# 3. Check exit code
if ($LASTEXITCODE -eq 3) {
    Write-Host "BLOCKER found - do not deploy"
} else {
    Write-Host "OK to deploy"
}
```

### Workflow 2: Underwriter Investigation
```python
# "Why did this physician get a 7?"
df = pd.read_csv("scores.csv")
npi = 1234567890

codes = reasons.reason_codes(df[df.NPI == npi], cm, top_n=10)
print(codes)  # Top 10 drivers + contribution

# Render their card
card.render(df[df.NPI == npi], cm, Path(f"{npi}.html"))
```

### Workflow 3: Compare Models
```bash
# Run diagnostics on v1.0
python -m src.account_score.inference.pas_diagnostics \
    --input scores_v1_0.csv --outdir reports_v1_0 --excel

# Run diagnostics on v1.1
python -m src.account_score.inference.pas_diagnostics \
    --input scores_v1_1.csv --outdir reports_v1_1 --excel

# Compare Gini, Spearman, PSI in Excel outputs
```

### Workflow 4: Edge Case Testing
```bash
# Test edge cases
python scripts/inference/test_edges.py \
    --input physician_scores.csv \
    --output edge_report.html

# Examples tested:
# - Physicians with zero premium
# - Loss-free years sentinel (-99)
# - Out-of-range KPI values
# - Missing required columns
```

---

## Troubleshooting

### Issue: "Column not found" error

**Cause:** Input CSV columns don't match schema

**Fix:**
```bash
# Dump the column map
python -m src.account_score.inference.pas_diagnostics \
    --input your_scores.csv \
    --dump-column-map map.json

# Edit map.json to fix column names
# Then run with custom map
python -m src.account_score.inference.pas_diagnostics \
    --input your_scores.csv \
    --column-map map.json \
    --inspect
```

### Issue: "Reconciliation max_residual > 1.0"

**Cause:** Credibility blending not handled correctly (see note above)

**Fix:** Check pre/post blending, ensure CREDIBILITY_Z persisted, match complement to anchor (5 → 4.5)

### Issue: "Circularity detected"

**Cause:** Band thresholds were defined by looking at outcome

**Fix:** Re-fit bands on training data, evaluate on independent test data

### Issue: Out-of-time Gini much lower than in-sample

**Cause:** Likely overfitting to training period or population shift

**Fix:** Review variable selection, check for circularity, validate thresholds on broader time window

---

## Performance Tips

**For large files (>1GB):**

```bash
# Use --nrows to process in batches
python -m src.account_score.inference.pas_diagnostics \
    --input huge_scores.csv \
    --nrows 100000 \
    --inspect
```

**For production runs:**

```bash
# Use --excel to get all reports in one file
python -m src.account_score.inference.pas_diagnostics \
    --input scores.csv \
    --outdir reports \
    --excel  # Combines all outputs into one workbook
```

---

## Integration with Pipeline

Inference should run **after** scoring pipeline:

```
Pipeline: Data → KPI Calc → Binning → Scoring → Scores CSV
                                                       ↓
Inference:                                      Diagnostics
                                               Attribution
                                               Cards & Reports
```

Exit code from diagnostics should gate deployment:

```python
import subprocess
result = subprocess.run([
    'python', '-m', 'src.account_score.inference.pas_diagnostics',
    '--input', 'scores.csv',
    '--outdir', 'reports',
    '--excel'
])

if result.returncode == 3:
    print("BLOCKER - do not deploy")
    exit(1)
else:
    print("Diagnostics passed - safe to deploy")
```

---

## See Also

- [Production Deployment Guide](./PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Quick Reference](./PAS_QUICK_REFERENCE.md)
- [Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)
- [Inference Module README](../../src/account_score/inference/README.md)
