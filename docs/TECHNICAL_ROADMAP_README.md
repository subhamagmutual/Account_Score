# Physician Account Score (PAS) - Technical Roadmap

**Complete Excel Documentation Created**: `TECHNICAL_ROADMAP.xlsx`

This document provides a comprehensive overview of the technical roadmap, all code modules, their inputs, and outputs.

---

## Excel Workbook Contents

### Sheet 1: Roadmap Overview
- **Purpose**: High-level summary of the 3-step technical approach
- **Contains**: Step 1, Step 2, Step 3 with key modules and outputs
- **Use Case**: Executive summary / quick reference

### Sheet 2: Step 1 - Development
**STEP 1: Score Development & Validation** (MagMutual + 3rd Party Data)

**10 Core Modules**:
1. **data_loader.py** (82 lines)
   - Loads MagMutual + 3rd party data
   - Input: CSV files, database connections
   - Output: Pandas DataFrame with raw data

2. **kpi_calculator.py** (84 lines)
   - Calculates 23 KPI variables
   - Input: Raw claims, procedures, diagnoses
   - Output: 23 engineered features

3. **credibility.py** (39 lines)
   - Data quality weighting
   - Input: Data completeness metrics
   - Output: Credibility z-scores

4. **binner.py** ⭐ (233 lines) **KEY MODULE**
   - Creates bin thresholds (THESE BINS ARE USED BY INFERENCE)
   - Input: 23 KPI features, number of bins
   - Output: Bin thresholds JSON → `models/binning_v{date}/`

5. **scorer.py** (59 lines)
   - Calculates sub-scores and composite score
   - Input: Binned features, weights (40/25/25/10)
   - Output: Composite (1-10) + 4 component scores

6. **config_loader.py** (178 lines)
   - Loads configurations
   - Input: JSON config files
   - Output: Config objects

7. **config_validator.py** (111 lines)
   - Validates all configs
   - Input: Configuration files
   - Output: Validation pass/fail

8. **input_validator.py** (151 lines)
   - Validates input data quality
   - Input: Raw data, rules
   - Output: Quality report

9. **score_validator.py** (135 lines)
   - Validates output scores
   - Input: Generated scores
   - Output: Validation report

10. **pipeline.py** (195 lines)
    - Orchestrates entire Step 1
    - Input: Data file, configs
    - Output: Scores, bins, reports

**OUTPUTS FROM STEP 1**:
- Composite scores (1-10 range) for MagMutual physicians
- **Bin thresholds** (stored in `models/binning_v{date}/`)
- Configuration files
- Validation reports

---

### Sheet 3: Step 2 - DHC
**STEP 2: Broader Dataset Application** (DHC - All US Physicians)

**5 Core Modules**:
1. **inference/pas_diagnostics/pipeline.py** (203 lines)
   - Applies scoring to DHC (millions of physicians)
   - Input: DHC raw data, Step 1 bins/configs
   - Output: Scores for all physicians

2. **inference/pas_diagnostics/checks.py** (296 lines)
   - Data quality diagnostics
   - Input: Raw data, validation rules
   - Output: Diagnostic report

3. **inference/pas_diagnostics/metrics.py** (155 lines)
   - Performance metrics
   - Input: Scored data, targets
   - Output: Metrics vs baseline

4. **inference/pas_diagnostics/card.py** (86 lines)
   - Diagnostic cards/reports
   - Input: Diagnostics, checks
   - Output: HTML/JSON diagnostic cards

5. **inference/pas_diagnostics/cli.py** (87 lines)
   - Command-line interface
   - Input: CLI arguments, data files
   - Output: Results, diagnostics

**KEY POINT**: Step 2 uses the **BINS FROM STEP 1** to score DHC data with the same binning strategy.

---

### Sheet 4: Step 3 - Monitoring
**STEP 3: Monitoring & Production** (Ensure Scores Still Work)

**13 Core Modules**:

**Monitoring Modules**:
1. **monitoring/score_monitor.py** (92 lines) - Track distributions
2. **monitoring/psi.py** ⭐ (54 lines) - **CRITICAL**: Population Stability Index
   - Detects drift when moving from MagMutual → DHC
   - If PSI > 0.25: bins need recalibration
3. **monitoring/data_quality.py** (67 lines) - Quality validation
4. **monitoring/anomalies.py** (62 lines) - Outlier detection
5. **validation/population_comparison.py** (77 lines) - Compare distributions

**Deployment & Versioning**:
6. **deployment/gates.py** ⭐ (113 lines) - 5 safety gates before production
7. **deployment/versioning.py** (41 lines) - Version management

**API & Batch**:
8. **api/server.py** (30 lines) - FastAPI app
9. **api/routes.py** (100 lines) - Scoring endpoints
10. **batch/scheduler.py** (91 lines) - Daily/weekly jobs

**Analytics & Alerts**:
11. **alerts/alerter.py** (18 lines) - Alert management
12. **analytics/population_analytics.py** (67 lines) - Segment analysis
13. **analytics/dashboard.py** (54 lines) - Performance dashboards

---

### Sheet 5: Data Flow
Complete end-to-end data flow for all 3 steps:

**STEP 1**: Load → Validate → Calculate KPIs → Create Bins → Score → Validate → Save
**STEP 2**: Load DHC → Calculate KPIs → Apply Step 1 Bins → Score DHC → Diagnose
**STEP 3**: Monitor → Check PSI → Gates → Deploy → Serve API → Track Distribution

---

### Sheet 6: Config and Bins
**Key Configuration Files**:

1. **config/scoring_weights.json**
   - Component weights: adequacy (0.40), capacity (0.25), appetite (0.25), environment (0.10)

2. **models/binning_v20260728/thresholds.json** ⭐
   - **THE BINS** created by Step 1
   - Quintile/quartile boundaries for all 23 KPI variables
   - **Used by Step 2 inference code**

3. **models/binning_v20260728/metadata.json**
   - Bin metadata (creation date, cohort, sample size)

4. **config/monitoring_baseline.json**
   - Baseline distributions from MagMutual
   - Used for comparison to DHC (PSI calculation)

5. **config/monitoring_config.json**
   - Alert thresholds (PSI: 0.25, shift: 5%, nulls: 5%)

6. **models/CURRENT.txt**
   - Active version for production (e.g., v1.0.0-prod-20260728)

---

### Sheet 7: Inputs and Outputs
**Complete Process Mapping**:

| Process | Inputs | Outputs |
|---------|--------|---------|
| **STEP 1: Development** | MagMutual + 3rd party data | Scores, bins, configs |
| Data Loading | File paths | DataFrames |
| KPI Calculation | Raw columns | 23 features |
| Binning | 23 KPIs | Bin thresholds |
| Scoring | Binned features, weights | Composite scores (1-10) |
| **STEP 2: DHC** | DHC data + Step 1 bins | All US physician scores |
| Inference | DHC raw data, bins | Scored physicians |
| **STEP 3: Production** | Ongoing scores | Alerts, dashboards |
| PSI Detection | MagMutual vs DHC | PSI values (alert if >0.25) |
| Deployment Gates | Scores, metrics | Approve/block (exit 0 or 3) |
| API Service | HTTP requests | JSON scores, health |
| Dashboards | Score data | HTML/JSON reports |

---

## Key Insights

### The 3-Step Process

**Step 1: DEVELOPMENT**
- Use MagMutual (limited) data + 3rd party data
- Calculate 23 KPI variables
- **Create bins for each variable** ← These are critical!
- Test and validate
- Output: Bins, configurations, proven scores

**Step 2: SCALABILITY**
- Apply Step 1 bins to DHC (all US physicians)
- Use same binning strategy for portability
- Diagnose performance vs MagMutual
- Output: Scores for millions of physicians

**Step 3: MONITORING**
- Track score distributions over time
- **PSI detection**: Is DHC population different from MagMutual?
  - If PSI > 0.25: Distribution shifted significantly
  - Recommendation: Recalibrate bins on DHC data
- Deployment gates: 5 safety checks before production
- Continuous monitoring: Ensure scores still work

### Why Bins Are Critical

The **bins created in Step 1** (binner.py) are stored and reused by:
- Step 2 inference code → scores DHC with same binning
- Monitoring code → compares to baseline distributions
- Production code → ensures consistent scoring

If bins don't work well on DHC (high PSI), recommendation is to:
1. Recalibrate bins on DHC-specific data
2. Retrain scoring model
3. Redeploy with new version

---

## Testing Coverage

**Step 1 Tests**: 
- test_binner.py, test_scorer.py, test_validators.py
- 60+ unit tests

**Step 3 Tests**:
- monitoring, deployment, analytics modules
- 40+ unit tests

**Integration Tests**:
- PHASE1_PHASE2_TESTING.ipynb (8 test sections)
- PHASE3_TESTING.ipynb (11 test sections)

---

## File Locations

```
Account_Score/
├── src/account_score/
│   ├── [Step 1 modules]
│   ├── inference/ [Step 2 modules]
│   └── [Step 3 modules]
├── config/
│   ├── scoring_weights.json
│   ├── monitoring_config.json
│   └── monitoring_baseline.json
├── models/
│   ├── binning_v20260728/ ← THE BINS
│   ├── CURRENT/
│   └── CURRENT.txt
└── docs/
    └── TECHNICAL_ROADMAP.xlsx ← YOU ARE HERE
```

---

## Quick Reference

**3500+ Lines of Production Code**:
- Step 1: 1100 lines (develop & validate)
- Step 2: 800 lines (apply to DHC)
- Step 3: 1600 lines (monitor & deploy)

**30+ Code Modules**

**Complete Data Flow**: Raw Data → Bins → Scores → Monitor → Deploy → Serve

**All Inputs & Outputs Documented**: Every module has clear inputs and outputs

---

## How to Use This Document

1. **Executive Summary**: See Roadmap Overview sheet
2. **Understand Step 1**: See "Step 1 - Development" sheet + "Config and Bins"
3. **Understand Step 2**: See "Step 2 - DHC" sheet
4. **Understand Step 3**: See "Step 3 - Monitoring" sheet
5. **Full Data Flow**: See "Data Flow" sheet
6. **Process Details**: See "Inputs and Outputs" sheet

---

Generated: 2026-07-28
Status: **Complete**
