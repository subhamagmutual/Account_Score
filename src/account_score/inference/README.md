# Inference & Diagnostics Module

Core tools for scoring physicians and validating model performance.

## Quick Start

### Python API

```python
from src.account_score.inference import pas_diagnostics, reasons, card
import pandas as pd

# Load scores
df = pd.read_csv("physician_scores.csv")

# Run diagnostics
diagnostics = pas_diagnostics.run_diagnostics(df, outdir="reports/")

# Get reason codes (attribution)
reason_codes = reasons.reason_codes(df, top_n=3)

# Render HTML cards
card.render(df, Path("cards.html"))
```

### Command Line

```bash
# Inspect schema
python -m src.account_score.inference.pas_diagnostics \
    --input physician_scores.csv \
    --inspect

# Full diagnostics report
python -m src.account_score.inference.pas_diagnostics \
    --input physician_scores.csv \
    --outdir reports/2026-07 \
    --train-years 2017 2018 2019 2020 2021 \
    --test-years 2022 2023 2024 \
    --excel
```

## Modules

- **schema.py** - Column mapping, data validation, distributions
- **metrics.py** - Gini, Lorenz, VIF, PSI, monotonicity tests
- **checks.py** - 10 diagnostic checks for model validation
- **reasons.py** - Exact additive score attribution & reason codes
- **card.py** - Standalone HTML cards for underwriter review
- **report.py** - Markdown, CSV, Excel report writers
- **cli.py** - Command-line interface
- **config.py** - Configuration & constants

## Checks

| Check | Purpose |
|-------|---------|
| schema | Validate columns match design |
| data_quality | Detect missing, zero, sentinel values |
| adequacy_reality | Ensure Adequacy measures loss, not burn |
| circularity | Detect if bands were cut on outcome |
| variable_signal | Test if each variable orders loss |
| discrimination | Check band separation |
| effective_weights | Compare nominal vs realized weights |
| redundancy | VIF and correlation analysis |
| composite_lift | Gini in-sample and out-of-time |
| stability | PSI year-over-year |

## Attribution & Reason Codes

Exact additive decomposition: each variable's contribution to the composite score sums to the actual score.

```python
composite - 4.5 == sum([weight_i * (score_i - 4.5)])
```

Each term is a real score point, auditable in Excel.

## See Also

- [Deployment Guide](../../docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Quick Reference](../../docs/deployment/PAS_QUICK_REFERENCE.md)
- [Implementation Roadmap](../../docs/deployment/IMPLEMENTATION_ROADMAP.md)
