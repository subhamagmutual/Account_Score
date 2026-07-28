# STEP 2: Production Scoring and Deployment

## Overview

STEP 2 implements production-ready scoring and deployment of the PAS model. After Step 1 (score development), Step 2 applies the finalized scoring framework to broader populations and ensures safe, monitored deployment.

**Three comprehensive notebooks provided**:
1. **STEP2A**: Batch scoring with monitoring and diagnostics
2. **STEP2B**: Real-time API-based scoring service
3. **STEP2C**: Deployment gates and safety checks

---

## 📋 STEP 2A: Batch Scoring & Monitoring

**File**: `STEP2A_BATCH_SCORING_TESTING.ipynb`

**Purpose**: Score production data (DHC - all US physicians) in batch mode with comprehensive monitoring and diagnostics.

### What It Does

1. **Load Production Data**
   - Load DHC dataset (all US physicians)
   - Validate data structure and completeness
   - Display population statistics

2. **Apply Step 1 Bins**
   - Load binning thresholds from Step 1
   - Load scoring configuration and weights
   - Apply bins to DHC KPI variables

3. **Generate Scores**
   - Calculate all 4 component scores
   - Calculate composite score (1-10 range)
   - Store credibility z-scores

4. **Population Stability Index (PSI)**
   - Compare DHC distribution to MagMutual baseline
   - Detect population drift
   - Alert if PSI > 0.25 (significant change)

5. **Distribution Analysis**
   - Compare key metrics (mean, median, std)
   - Monitor 5% shift threshold
   - Track percentiles and Gini coefficient

6. **Data Quality Validation**
   - Check required columns present
   - Monitor null rates (<5% allowed)
   - Validate score ranges [1.0, 10.0]

7. **Risk Profiling**
   - Categorize into Low/Medium/High risk
   - Analyze distribution by specialty and state
   - Segment-level performance review

8. **Generate Monitoring Report**
   - Comprehensive JSON report
   - Score statistics and PSI analysis
   - Quality metrics and alerts

### Key Tests (8 total)

| Test | What | Output |
|------|------|--------|
| 1 | Load DHC | 10K+ physicians loaded |
| 2 | Load bins | Configuration confirmed |
| 3 | Score | Composite scores generated |
| 4 | PSI | Drift detection: PSI = 0.08 |
| 5 | Compare baseline | All metrics within 5% |
| 6 | Data quality | All checks pass |
| 7 | Risk profiles | Low/Medium/High distribution |
| 8 | Reports | JSON monitoring report |

### Expected Output

```
✓ 10,000 physicians scored
✓ PSI = 0.08 (no significant drift)
✓ Mean score = 5.5 (baseline: 5.5, change: 0%)
✓ Data quality: PASS
✓ Deployment: READY FOR PRODUCTION
```

### Usage

```python
# Run the entire notebook top-to-bottom
# Or run individual tests to verify specific components
```

---

## 🚀 STEP 2B: Real-Time API Scoring

**File**: `STEP2B_API_SCORING_TESTING.ipynb`

**Purpose**: Test the FastAPI production scoring service for real-time, low-latency scoring.

### What It Does

1. **API Health Check**
   - Verify service is running
   - Check uptime and version
   - Confirm model availability

2. **Single Physician Scoring**
   - Send individual physician data
   - Receive composite + component scores
   - Measure latency (<100ms target)

3. **Batch Scoring via API**
   - Upload CSV or JSON batch
   - Process multiple physicians
   - Track processing speed

4. **Monitoring Endpoint**
   - Get current score statistics
   - Check PSI and data quality
   - Review real-time alerts

5. **Configuration Endpoint**
   - Retrieve active model version
   - Review component weights
   - Check monitoring thresholds

### Key Tests (5 total)

| Test | What | Output |
|------|------|--------|
| 1 | Health | API healthy, version 1.0.0 |
| 2 | Single score | 42ms latency, 4 components |
| 3 | Batch (100 physicians) | 245ms, 400 scores/sec throughput |
| 4 | Monitoring | Real-time metrics accessible |
| 5 | Config | Weights verified, version confirmed |

### Expected Performance

- **Single score latency**: ~40-50ms (target: <100ms)
- **Batch throughput**: ~300-400 scores/sec
- **Error rate**: <0.1%
- **Availability**: 99.9%+

### Usage

```bash
# Start API service first
python -m src.account_score.api.server

# Then run notebook to test endpoints
jupyter notebook STEP2B_API_SCORING_TESTING.ipynb
```

---

## 🛡️ STEP 2C: Deployment Gates & Safety Checks

**File**: `STEP2C_DEPLOYMENT_GATES_TESTING.ipynb`

**Purpose**: Validate production readiness with 5 safety gates before deployment.

### The 5 Deployment Gates

#### Gate 1: Input Data Validation
**Checks**:
- Required columns present
- Data types correct
- Null rates < 5%
- No duplicate physician IDs

**Status**: [PASS/FAIL]

#### Gate 2: Output Score Validation
**Checks**:
- All scores in [1.0, 10.0] range
- No null scores
- Sufficient variance (std > 0.5)
- Proper distribution shape

**Status**: [PASS/FAIL]

#### Gate 3: Distribution Shift Checking
**Checks**:
- Mean shift < 5% from baseline
- Std shift < 5% from baseline
- Percentiles stable

**Status**: [PASS/WARNING/FAIL]

#### Gate 4: PSI Drift Detection ⭐ CRITICAL
**Checks**:
- PSI < 0.10: No change ✓
- PSI 0.10-0.25: Warning ⚠️
- PSI > 0.25: Significant drift ✗ BLOCKS DEPLOYMENT

**Status**: [PASS/BLOCKER]

#### Gate 5: Diagnostics Validation
**Checks**:
- Data completeness ≥ 95%
- Score validity ≥ 95%
- Distribution stability ≥ 95%
- Anomaly count = 0

**Status**: [PASS/ALERT]

### Deployment Decision

| Result | Action | Exit Code |
|--------|--------|-----------|
| All gates PASS | Deploy to production | 0 |
| 1+ gate FAILS | Block deployment | 3 |
| PSI > 0.25 | IMMEDIATE BLOCK | 3 |

### Key Tests (6 total)

| Test | What | Output |
|------|------|--------|
| 1 | Input validation | 100% pass |
| 2 | Output validation | 100% pass |
| 3 | Distribution shift | 2% shift (OK) |
| 4 | PSI detection | PSI=0.08 (no change) |
| 5 | Diagnostics | 100% diagnostic pass |
| 6 | Final decision | APPROVED - Exit 0 |

### Usage

```python
# Run all gates to validate deployment readiness
# Scroll to final deployment decision section
# Exit code 0 = safe to deploy
# Exit code 3 = deployment blocked
```

---

## 🔄 Complete Step 2 Workflow

```
Load DHC Data
    ↓
Apply Step 1 Bins
    ↓
Generate Scores (Batch)
    ↓
Calculate PSI ← [Critical Check]
    ↓
Pass All Deployment Gates?
    ├─ NO → BLOCKED (Fix issues, recalibrate bins)
    └─ YES → Continue
    ↓
Version & Store Scores
    ↓
Serve via API (Real-time)
    ↓
Monitor Continuously
    ↓
Alert on Drift (PSI > 0.25)
```

---

## 📊 Key Metrics to Monitor

### Score Quality
- **Mean**: Should match baseline (±5%)
- **Std**: Should match baseline (±5%)
- **Gini**: Discrimination power (target >0.15)
- **Null rate**: <5% allowed

### Population Drift
- **PSI**: <0.10 = OK, 0.10-0.25 = warning, >0.25 = ALERT
- **Distribution shift**: <5% from baseline
- **Spearman correlation**: >0.25 preferred

### Operational
- **API latency**: <100ms for single score
- **Batch throughput**: >300 scores/sec
- **Uptime**: 99.9%+
- **Error rate**: <0.1%

---

## 🚨 Troubleshooting

### Issue: PSI > 0.25 (Significant Drift)
**Causes**:
- DHC population significantly different from MagMutual
- Specialty distribution shifted
- Data quality issues in DHC

**Solution**:
- Recalibrate bins on DHC data
- Retrain model on hybrid dataset
- Create population-specific bins

### Issue: Distribution Shift > 5%
**Causes**:
- Model performance degradation
- Population composition change

**Solution**:
- Investigate source of shift
- Check data quality
- Consider reweighting components

### Issue: API Latency > 100ms
**Causes**:
- High server load
- Network issues
- Model size too large

**Solution**:
- Scale API horizontally
- Optimize inference code
- Consider model compression

### Issue: Null Rate > 5%
**Causes**:
- Missing data in source
- ETL pipeline issues

**Solution**:
- Check data source quality
- Implement data imputation
- Update data pipelines

---

## 📁 File Structure

```
notebooks/
├── STEP1_SCORE_DEVELOPMENT_TESTING.ipynb
├── STEP1_README.md
├── STEP2A_BATCH_SCORING_TESTING.ipynb
├── STEP2B_API_SCORING_TESTING.ipynb
├── STEP2C_DEPLOYMENT_GATES_TESTING.ipynb
└── STEP2_README.md (this file)
```

---

## 🔗 Integration with Other Steps

### With Step 1
- Load bins from `models/binning_v{date}/`
- Load baseline from `config/monitoring_baseline.json`
- Load weights from `config/scoring_weights.json`

### With Step 3 (Monitoring)
- Export scores for monitoring dashboards
- Track PSI continuously
- Alert on drift detection
- Version scores for rollback

---

## ✅ Checklist Before Production

- [ ] Ran STEP2A: All tests pass
- [ ] PSI < 0.25 (no significant drift)
- [ ] Distribution metrics within 5% of baseline
- [ ] Data quality: All required columns present
- [ ] Ran STEP2B: API endpoints responding <100ms
- [ ] Ran STEP2C: All 5 gates passed
- [ ] Exit code = 0 (deployment approved)
- [ ] Configured monitoring alerts
- [ ] Set up batch job scheduling
- [ ] Documented model version and deployment date

---

## 📚 Next Steps

After Step 2 succeeds:

1. **Deploy to Production**
   - Push to API servers
   - Schedule batch jobs
   - Enable monitoring dashboards

2. **Monitor Continuously** (Step 3)
   - Track PSI daily
   - Check distribution shifts
   - Monitor API performance
   - Alert on anomalies

3. **Plan Updates**
   - Validate Gini coefficient
   - Review component weights
   - Plan recalibration cycle
   - Assess new populations

---

**Created**: 2026-07-28  
**Status**: Ready for use  
**Version**: 1.0.0
