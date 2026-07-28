# Inference Scripts & Utilities

Operational utilities for running diagnostics, feature analysis, and model validation.

## Scripts

### `build_dict.py`
Build and validate data dictionary from design specifications.

```bash
python build_dict.py --input design.xlsx --output data_dictionary.json
```

### `build_guide.py`
Generate diagnostic guide and best practices documentation.

```bash
python build_guide.py --output guide.md
```

### `build_notebook.py`
Auto-generate diagnostic notebooks from templates.

```bash
python build_notebook.py --template template.ipynb --output diagnostic.ipynb
```

### `make_fixture.py`
Create synthetic test data with known pathologies for validation.

```bash
python make_fixture.py --rows 60000 --output fixture_scores.csv
```

### `test_edges.py`
Test edge cases and boundary conditions in scoring logic.

```bash
python test_edges.py --input physician_scores.csv --output edge_test_report.html
```

### `try_uw.py`
Interactive underwriter tooling - explore reasons, cards, and attributions.

```bash
python try_uw.py --input physician_scores.csv
```

## Feature Analysis

See `feature_importance_analysis/` for feature importance and sensitivity analysis.

```bash
python feature_importance_analysis/feature_importance_analysis.py \
    --input physician_scores.csv \
    --output importance_report.xlsx
```

## Usage with Inference Module

All scripts integrate with the core `src.account_score.inference` module:

```python
from src.account_score.inference import reasons, card, schema
```

See [Inference README](../../src/account_score/inference/README.md) for API details.
