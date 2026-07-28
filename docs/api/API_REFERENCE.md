# PAS API Reference

## Table of Contents

1. [Pipeline Functions](#pipeline-functions)
2. [Scoring Functions](#scoring-functions)
3. [Validation Functions](#validation-functions)
4. [Analysis Functions](#analysis-functions)
5. [Data Lineage](#data-lineage)

---

## Pipeline Functions

### `run_scoring_pipeline()`

Main entry point for the full batch scoring pipeline.

**Location:** `src/account_score/pipeline.py`

**Signature:**
```python
def run_scoring_pipeline(
    config_dir: Optional[str] = None,
    mode: str = "fit_and_score",
    input_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    sample_n: Optional[int] = None,
    dynamic: bool = False
) -> pd.DataFrame
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_dir` | `str` | `None` | Path to config directory. If None, uses default (../config) |
| `mode` | `str` | `"fit_and_score"` | Pipeline mode: `fit_and_score`, `fit_only`, or `score_only` |
| `input_path` | `str` | `None` | Override input data file path |
| `output_dir` | `str` | `None` | Override output directory |
| `sample_n` | `int` | `None` | If set, sample N records for testing |
| `dynamic` | `bool` | `False` | Use mean-anchored binning for all methods |

**Returns:** 
- `pd.DataFrame`: Scored data with all component and composite scores

**Modes:**

- `fit_and_score`: Fit binning thresholds from data, then score all records
- `fit_only`: Only fit thresholds (no scoring output)
- `score_only`: Score using previously fitted thresholds (requires existing binning_thresholds.json)

**Example:**

```python
from src.account_score.pipeline import run_scoring_pipeline

# Full pipeline with sampling for testing
df = run_scoring_pipeline(
    config_dir="./config",
    mode="fit_and_score",
    sample_n=10000,
    output_dir="./results"
)

# Score only using existing thresholds
df = run_scoring_pipeline(
    mode="score_only",
    input_path="/path/to/new_data.csv"
)
```

---

### `score_single_record()`

Score a single physician-year record (API mode).

**Location:** `src/account_score/pipeline.py`

**Signature:**
```python
def score_single_record(
    record: Dict[str, Any],
    config_dir: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `record` | `dict` | Dictionary with physician-year values |
| `config_dir` | `str` | Path to config directory |

**Returns:** 
- `Dict` with keys:
  - `adequacy_score`: 1-10
  - `capacity_score`: 1-10
  - `appetite_score`: 1-10
  - `environment_score`: 1-10
  - `composite_score`: 1-10
  - `credibility_z_factor`: 0-1

---

## Scoring Functions

### `ScoreCalculator` Class

Calculates component and composite scores from binned variables.

**Location:** `src/account_score/scorer.py`

**Methods:**
- `score_record(scores: Dict) -> Dict` - Score a single record
- `score_batch(df: DataFrame) -> DataFrame` - Score a batch of records
- `_calc_component() -> float` - Calculate component score
- `_calc_composite() -> int` - Calculate composite score

---

## Validation Functions

### `ConfigValidator` Class

Validates configuration files.

**Location:** `src/account_score/config_validator.py`

```python
validator = ConfigValidator(config_dict)
is_valid, errors, warnings = validator.validate_all()
```

### `InputValidator` Class

Validates input data quality.

**Location:** `src/account_score/input_validator.py`

```python
validator = InputValidator(config, verbose=True)
df, issues, stats = validator.validate_dataframe(df)
```

---

## Analysis Functions

### `DeploymentTables` Class

Generate summary statistics and deployment tables.

**Location:** `src/account_score/deployment_tables.py`

---

## Data Lineage

See `docs/data-governance/DATA_LINEAGE.md` for complete data flow documentation.

---

**Last Updated:** July 2026  
**Version:** 1.0
