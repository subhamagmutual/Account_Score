# Scoring Folder Reorganization Summary

**Date:** 2026-07-28  
**Status:** ✅ Complete

---

## What Was Done

The `Scoring/` folder containing inference, diagnostics, and deployment code has been reorganized into a proper production-ready structure following TIER 2 folder organization standards.

---

## Organization Map

### ✅ Source Code (Production Package)

**Before:**
```
Scoring/pas_diagnostics/     ← Mixed with other files
```

**After:**
```
src/account_score/inference/
├── __init__.py              ← New: Package initialization
├── README.md                ← New: Module documentation
├── pas_diagnostics/         ← Diagnostic checks, metrics, attribution
├── schema.py
├── metrics.py
├── checks.py
├── reasons.py
├── card.py
├── report.py
├── config.py
└── __main__.py
```

**Access:** `from src.account_score.inference import pas_diagnostics`

---

### ✅ Utility Scripts

**Before:**
```
Scoring/
├── build_dict.py
├── build_guide.py
├── build_notebook.py
├── make_fixture.py
├── test_edges.py
└── try_uw.py
```

**After:**
```
scripts/inference/
├── README.md                ← New: Usage guide
├── build_dict.py
├── build_guide.py
├── build_notebook.py
├── make_fixture.py
├── test_edges.py
└── try_uw.py
```

**Access:** `python scripts/inference/make_fixture.py ...`

---

### ✅ Analysis Notebooks

**Before:**
```
Scoring/
├── 01. check_distribution.ipynb
├── 02. check_csv_columns.ipynb
├── 03. run_diagnostics_CORRECTED.ipynb
├── 04. uw_tooling_reason_codes.ipynb
├── 05. validation_harness_70_30_split.ipynb
└── PAS_Pipeline.ipynb
```

**After:**
```
notebooks/inference/
├── 01. check_distribution.ipynb
├── 02. check_csv_columns.ipynb
├── 03. run_diagnostics_CORRECTED.ipynb
├── 04. uw_tooling_reason_codes.ipynb
├── 05. validation_harness_70_30_split.ipynb
└── PAS_Pipeline.ipynb
```

**Access:** Jupyter → `Open notebooks/inference/`

---

### ✅ Deployment Documentation

**Before:**
```
Scoring/production_deployment/
├── IMPLEMENTATION_ROADMAP.md
├── PAS_Quick_Reference.md
├── Production_Deployment_Guide.docx
└── Production_Deployment_Guide.md
```

**After:**
```
docs/deployment/
├── IMPLEMENTATION_ROADMAP.md
├── PAS_QUICK_REFERENCE.md
├── Production_Deployment_Guide.docx
├── Production_Deployment_Guide.md
├── INFERENCE_GUIDE.md         ← New: Comprehensive inference guide
└── PAS_HANDOFF.md
```

**Access:** `docs/deployment/INFERENCE_GUIDE.md`

---

### ✅ Data Dictionaries & Reference

**Before:**
```
Scoring/
├── PAS_Code_Guide.xlsx
└── PAS_Input_Data_Dictionary.xlsx
```

**After:**
```
docs/deployment/
├── PAS_Code_Guide.xlsx
├── PAS_Input_Data_Dictionary.xlsx
└── PAS_HANDOFF.md
```

---

### 📦 Archive (Reference Only)

**Preserved:**
```
._ARCHIVE_Scoring_Original/   ← Original folder (renamed, kept for reference)
```

All production code extracted, but original kept for any missing items.

---

## Benefits

| Aspect | Benefit |
|--------|---------|
| **Production Ready** | Core inference code in `src/` → importable, versionable, testable |
| **TIER 2 Compliant** | Follows folder structure standards created in TIER 2 |
| **Discoverable** | Developers know where to find inference tools |
| **Maintainable** | Clear separation: code vs scripts vs notebooks vs docs |
| **Deployable** | CI/CD can test/validate inference code automatically |
| **Documented** | Comprehensive INFERENCE_GUIDE.md explains everything |

---

## How to Use

### 1. Run Diagnostics (CLI)
```bash
python -m src.account_score.inference.pas_diagnostics \
    --input physician_scores.csv \
    --inspect
```

### 2. Get Reason Codes (Python)
```python
from src.account_score.inference import reasons
codes = reasons.reason_codes(df, column_map, top_n=3)
```

### 3. Generate Score Cards
```python
from src.account_score.inference import card
card.render(df, column_map, Path("cards.html"))
```

### 4. Create Test Fixtures
```bash
python scripts/inference/make_fixture.py --rows 60000
```

### 5. Explore in Notebooks
```bash
jupyter notebook notebooks/inference/03_run_diagnostics_CORRECTED.ipynb
```

---

## Integration Points

### With TIER 2 (CI/CD)
- Inference tests can run in GitHub Actions
- Diagnostic output can be artifact in CI/CD pipeline
- Exit codes gate deployment (code 3 = BLOCKER)

### With TIER 3 (Makefile)
- Could add `make diagnose` target
- Could add `make generate-cards` target
- Pre-commit hooks can validate inference outputs

### With TIER 4 (Monitoring)
- Health checks can run inference diagnostics
- Metrics from checks can feed monitoring dashboard
- Alerts can trigger on BLOCKER conditions

---

## Files Changed

✅ Created:
- `src/account_score/inference/__init__.py`
- `src/account_score/inference/README.md`
- `scripts/inference/README.md`
- `docs/deployment/INFERENCE_GUIDE.md`

📁 Moved:
- `Scoring/pas_diagnostics/` → `src/account_score/inference/pas_diagnostics/`
- `Scoring/*.py` → `scripts/inference/`
- `Scoring/*.ipynb` → `notebooks/inference/`
- `Scoring/production_deployment/*.md` → `docs/deployment/`
- `Scoring/PAS_*.xlsx` → `docs/deployment/`

🗂️ Archived:
- `Scoring/` → `._ARCHIVE_Scoring_Original/`

---

## Next Steps

1. **Test Imports** - Verify `from src.account_score.inference import pas_diagnostics` works
2. **Update TIER 2 Notebook** - Add inference tests to `notebooks/TIER2_TIER3_TEST.ipynb`
3. **Commit & Push** - Add to git, push to dev branch
4. **Plan TIER 4** - Monitoring/deployment enhancements for inference

---

## Questions?

See:
- `docs/deployment/INFERENCE_GUIDE.md` - Comprehensive guide
- `src/account_score/inference/README.md` - API documentation
- `scripts/inference/README.md` - Script usage

