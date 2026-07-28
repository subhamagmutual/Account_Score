# Physician Account Score (PAS) System - Architecture Diagram

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHYSICIAN ACCOUNT SCORE (PAS) SYSTEM                    │
│                            Production-Ready Solution                        │
└─────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────┐
                                    │  INPUT DATA  │
                                    └──────────────┘
                                           │
                ┌──────────────────────────┼──────────────────────────┐
                │                          │                          │
        ┌───────▼────────┐        ┌───────▼────────┐        ┌───────▼────────┐
        │ MagMutual Data │        │   DHC Data     │        │  3rd Party     │
        │ (500 phys)     │        │ (10K+ phys)    │        │  Vendors       │
        └────────────────┘        └────────────────┘        └────────────────┘

                                            │
                                            ▼

                           ┌──────────────────────────┐
                           │  DATA LOADING & VALIDATION
                           │  - Input validation      │
                           │  - Deduplication         │
                           │  - Schema validation     │
                           └──────────────────────────┘

                                            │
                                            ▼

                    ┌────────────────────────────────────────┐
                    │         STEP 1: SCORE DEVELOPMENT      │
                    ├────────────────────────────────────────┤
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │   KPI Calculation (23 variables) │  │
                    │  │                                  │  │
                    │  │  Adequacy (8 KPIs):              │  │
                    │  │   - Claims history               │  │
                    │  │   - Board certification          │  │
                    │  │   - Continuing education         │  │
                    │  │   - Loss frequency               │  │
                    │  │   - Payment delay history        │  │
                    │  │   - Claim denial rate            │  │
                    │  │   - Specialty tier               │  │
                    │  │   - Location reputation          │  │
                    │  │                                  │  │
                    │  │  Capacity (5 KPIs):              │  │
                    │  │   - Patient volume               │  │
                    │  │   - Procedure complexity         │  │
                    │  │   - Risk management score        │  │
                    │  │   - Facilities rating            │  │
                    │  │   - Staffing adequacy            │  │
                    │  │                                  │  │
                    │  │  Appetite (7 KPIs):              │  │
                    │  │   - Years in practice            │  │
                    │  │   - Market segments served       │  │
                    │  │   - Portfolio diversification    │  │
                    │  │   - Geographic distribution      │  │
                    │  │   - Litigation history           │  │
                    │  │   - Regulatory compliance        │  │
                    │  │   - Industry reputation          │  │
                    │  │                                  │  │
                    │  │  Environment (3 KPIs):           │  │
                    │  │   - State regulations            │  │
                    │  │   - Economic factors             │  │
                    │  │   - Market conditions            │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Credibility Weighting           │  │
                    │  │   - Data completeness (0-1)      │  │
                    │  │   - Z-factor adjustments         │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Binning (Quintiles)             │  │
                    │  │   - 23 variables × 5 bins each   │  │
                    │  │   - Equal frequency distribution │  │
                    │  │   - Threshold creation           │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Component Scoring               │  │
                    │  │   - Adequacy: 0-10 (40% weight)  │  │
                    │  │   - Capacity: 0-10 (25% weight)  │  │
                    │  │   - Appetite: 0-10 (25% weight)  │  │
                    │  │   - Environment: 0-10 (10%)      │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Composite Score                 │  │
                    │  │   - Weighted sum of components   │  │
                    │  │   - Range: 1.0 - 10.0            │  │
                    │  │   - Risk categories (L/M/H)      │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Validation                      │  │
                    │  │   - Score range checks           │  │
                    │  │   - Distribution validation      │  │
                    │  │   - Quality metrics              │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    └────────────────────────────────────────┘

                                            │
                                            ▼

                    ┌────────────────────────────────────────┐
                    │      STEP 2: PRODUCTION DEPLOYMENT     │
                    ├────────────────────────────────────────┤
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Batch Scoring                   │  │
                    │  │  (/batch endpoint)               │  │
                    │  │   - Score 10K+ physicians        │  │
                    │  │   - Daily at 2 AM                │  │
                    │  │   - Parallel processing          │  │
                    │  │   - Output: CSV + reports        │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Real-Time API                   │  │
                    │  │  (FastAPI on port 8000)          │  │
                    │  │   - POST /score endpoint         │  │
                    │  │   - Single physician: <100ms     │  │
                    │  │   - Health check: /health        │  │
                    │  │   - Config: /config              │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Deployment Gates (5 checks)     │  │
                    │  │   1. Input validation            │  │
                    │  │   2. Output validation           │  │
                    │  │   3. Distribution shift (5%)     │  │
                    │  │   4. PSI drift detection (0.25)  │  │
                    │  │   5. Diagnostic validation       │  │
                    │  │                                  │  │
                    │  │  Exit Codes:                     │  │
                    │  │   0 = SAFE (deploy)              │  │
                    │  │   3 = BLOCKED (investigation)    │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Version Management              │  │
                    │  │   - Track all versions           │  │
                    │  │   - Instant rollback             │  │
                    │  │   - Backward compatibility       │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    └────────────────────────────────────────┘

                                            │
                                            ▼

                    ┌────────────────────────────────────────┐
                    │   STEP 3: PRODUCTION MONITORING        │
                    ├────────────────────────────────────────┤
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Continuous Monitoring           │  │
                    │  │   - Real-time score tracking     │  │
                    │  │   - Distribution analysis        │  │
                    │  │   - Gini coefficient            │  │
                    │  │   - Percentile monitoring        │  │
                    │  │   - Daily dashboards             │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  PSI Drift Detection             │  │
                    │  │   - Continuous calculation       │  │
                    │  │   - Baseline comparison          │  │
                    │  │   - Thresholds:                  │  │
                    │  │     <0.10 = OK                   │  │
                    │  │     0.10-0.25 = WARNING          │  │
                    │  │     >0.25 = BLOCKER              │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Alert Management                │  │
                    │  │   - 4 alert rules                │  │
                    │  │   - 3 severity levels            │  │
                    │  │   - Escalation matrix            │  │
                    │  │                                  │  │
                    │  │  INFO:    Log only               │  │
                    │  │  WARNING: Slack + email (1h)     │  │
                    │  │  BLOCKER: Email+Slack+Pager(15m)│  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Batch Job Scheduling            │  │
                    │  │  (APScheduler + cron)            │  │
                    │  │                                  │  │
                    │  │  Daily:                          │  │
                    │  │   - 2 AM: Batch scoring          │  │
                    │  │   - 6 AM: Monitoring report      │  │
                    │  │                                  │  │
                    │  │  Weekly:                         │  │
                    │  │   - Mon 3 AM: Diagnostics        │  │
                    │  │                                  │  │
                    │  │  Error Handling:                 │  │
                    │  │   - Retry 3x w/ backoff          │  │
                    │  │   - Timeout handling (1h)        │  │
                    │  │   - Failure escalation           │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Health Checks                   │  │
                    │  │   - Hourly: API + batch status   │  │
                    │  │   - Daily: Full diagnostics      │  │
                    │  │   - Weekly: Trend analysis       │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    └────────────────────────────────────────┘

                                            │
                                            ▼

                    ┌────────────────────────────────────────┐
                    │      OUTPUTS & NOTIFICATION SYSTEM     │
                    ├────────────────────────────────────────┤
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Output Files                    │  │
                    │  │  (Box.com directory)             │  │
                    │  │                                  │  │
                    │  │  /data/output/                   │  │
                    │  │   - step1_scores_*.csv           │  │
                    │  │   - step2_scores_*.csv           │  │
                    │  │   - batch_results_*.json         │  │
                    │  │                                  │  │
                    │  │  /data/monitoring/               │  │
                    │  │   - daily_report_*.json          │  │
                    │  │   - psi_analysis_*.json          │  │
                    │  │   - distribution_analysis_*.html │  │
                    │  │   - deployment_gates_*.json      │  │
                    │  │                                  │  │
                    │  │  /data/logs/pipeline/            │  │
                    │  │   - pipeline_*.log               │  │
                    │  │   - batch_job_*.log              │  │
                    │  │   - api_service_*.log            │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    │  ┌──────────────────────────────────┐  │
                    │  │  Alert Channels                  │  │
                    │  │   - Email (ops, data-science)    │  │
                    │  │   - Slack (#data-science, #ops)  │  │
                    │  │   - PagerDuty (oncall escalation)│  │
                    │  │   - Dashboard (web UI)           │  │
                    │  └──────────────────────────────────┘  │
                    │                                        │
                    └────────────────────────────────────────┘

                                            │
                                            ▼

                    ┌────────────────────────────────────────┐
                    │      STAKEHOLDER ACCESS LAYER          │
                    ├────────────────────────────────────────┤
                    │                                        │
                    │  Data Scientists:                      │
                    │   - Monitoring dashboard               │
                    │   - PSI analysis                       │
                    │   - Model performance metrics          │
                    │                                        │
                    │  Operations Team:                      │
                    │   - API health checks                  │
                    │   - Batch job status                   │
                    │   - Alert response procedures          │
                    │                                        │
                    │  Executives:                           │
                    │   - Risk distribution reports          │
                    │   - Physician cohort analysis          │
                    │   - Business impact metrics            │
                    │                                        │
                    └────────────────────────────────────────┘
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────┐
│   INPUT DATA        │  MagMutual data + DHC data + 3rd party data
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ DATA VALIDATION     │  Check schema, nulls, duplicates
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ KPI CALCULATION     │  Create 23 engineered features
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ CREDIBILITY         │  Weight by data completeness
│ WEIGHTING           │  
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ BINNING             │  Create quintile thresholds
│ (First time only)   │  Save bin configurations
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ APPLY BINS          │  Convert continuous → discrete (0-1)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ COMPONENT SCORING   │  Calculate 4 component scores
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ COMPOSITE SCORE     │  Weighted sum → 1.0-10.0 range
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ OUTPUT VALIDATION   │  Check ranges, distributions
└──────────┬──────────┘
           │
           ├─────────────────────────────┐
           │                             │
           ▼                             ▼
    ┌──────────────┐           ┌──────────────┐
    │ SAVE SCORES  │           │ SAVE REPORTS │
    │ (CSV)        │           │ (JSON, HTML) │
    └──────────────┘           └──────────────┘
           │
           ▼
    ┌──────────────────────────┐
    │ DEPLOYMENT GATES CHECK   │
    │                          │
    │ 1. Input validation ✓    │
    │ 2. Output validation ✓   │
    │ 3. Distribution shift ✓  │
    │ 4. PSI drift ✓           │
    │ 5. Diagnostics ✓         │
    │                          │
    │ Exit: 0 (SAFE) / 3 (X)   │
    └──────────┬───────────────┘
               │
    ┌──────────▼───────────┐
    │ SAFE TO DEPLOY?      │
    ├──────────┬───────────┤
    │    YES   │     NO    │
    ▼          │           ▼
  PROD    LOG  │       ALERT
  RELEASE FAIL │      TEAM
               │
    ┌──────────▼───────────┐
    │ MONITORING & ALERTS  │
    ├──────────────────────┤
    │                      │
    │ - PSI check          │
    │ - Distribution shift │
    │ - Data quality       │
    │ - API latency        │
    │                      │
    │ - Escalate if needed │
    │ - Update dashboard   │
    │                      │
    └──────────────────────┘
```

---

## 🔄 Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PACKAGE STRUCTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  src/account_score/                                                     │
│  │                                                                      │
│  ├── STEP 1: Score Development (10 modules)                            │
│  │   ├── data_loader.py          (Load raw data)                       │
│  │   ├── kpi_calculator.py        (Calculate 23 variables)             │
│  │   ├── credibility.py           (Data quality scoring)               │
│  │   ├── binner.py                (Quintile binning)                   │
│  │   ├── scorer.py                (Component + composite scoring)       │
│  │   ├── config_loader.py         (Configuration management)           │
│  │   ├── validators.py            (Input/output/schema validation)     │
│  │   ├── utils.py                 (Helper functions)                   │
│  │   ├── pipeline.py              (Orchestration)                      │
│  │   └── __init__.py              (Package initialization)             │
│  │                                                                      │
│  ├── STEP 2: Deployment (9 modules)                                    │
│  │   ├── api/                                                          │
│  │   │   ├── server.py            (FastAPI application)                │
│  │   │   ├── routes.py            (API endpoints)                      │
│  │   │   └── models.py            (Pydantic models)                    │
│  │   │                                                                  │
│  │   ├── deployment/                                                   │
│  │   │   ├── gates.py             (5 safety gates)                     │
│  │   │   └── versioning.py        (Version management)                 │
│  │   │                                                                  │
│  │   ├── batch/                                                        │
│  │   │   └── scheduler.py         (Batch job orchestration)            │
│  │   │                                                                  │
│  │   ├── inference/                                                    │
│  │   │   └── pipeline.py          (Inference orchestration)            │
│  │   │                                                                  │
│  │   └── alerts/                                                       │
│  │       └── manager.py           (Alert rules and routing)            │
│  │                                                                      │
│  └── STEP 3: Monitoring (7 modules)                                    │
│      ├── monitoring/                                                   │
│      │   ├── score_monitor.py     (Score distribution tracking)        │
│      │   ├── psi.py               (PSI drift calculation)              │
│      │   ├── data_quality.py      (Data quality checks)                │
│      │   └── anomalies.py         (Anomaly detection)                  │
│      │                                                                  │
│      ├── analytics/                                                    │
│      │   ├── distribution.py      (Distribution analysis)              │
│      │   ├── reporting.py         (Report generation)                  │
│      │   ├── diagnostics.py       (Diagnostic reports)                 │
│      │   └── visualization.py     (Chart generation)                   │
│      │                                                                  │
│      └── validation/                                                   │
│          └── health_check.py      (System health validation)           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Design Patterns

### 1. **Pipeline Orchestration**
   - STEP 1: Data → KPI → Binning → Scoring → Validation
   - STEP 2: Apply bins → Score → Gate checks → Deploy/Block
   - STEP 3: Monitor → Detect drift → Alert → Escalate

### 2. **Safety Gates**
   Five independent checks before production:
   - Input validation (schema, nulls, ranges)
   - Output validation (score ranges, distributions)
   - Distribution shift detection (5% threshold)
   - PSI drift detection (0.25 threshold)
   - Diagnostic validation (quality checks)

### 3. **Alert Escalation**
   ```
   Detection → INFO (log) → WARNING (slack, 1h) → BLOCKER (email+pager, 15m)
   ```

### 4. **Version Management**
   - Track all deployed versions
   - Instant rollback capability
   - Configuration versioning
   - Model artifact versioning

### 5. **Configuration as Code**
   - `pipeline_params.json` - Data paths and processing
   - `scoring_weights.json` - Score weights and mappings
   - `monitoring_config.json` - Alert rules and thresholds
   - `monitoring_baseline.json` - Baseline metrics

---

## 🔌 External Integrations

### Input Sources
- **MagMutual Data**: Historical physician performance data
- **DHC Data**: Broader physician cohort (10K+ records)
- **3rd Party Vendors**: Specialty, geographic, compliance data

### Output Destinations
- **Box.com**: Centralized data storage (C:/Box/...)
- **Email**: Alert notifications (ops, data-science)
- **Slack**: Real-time alerts (#data-science, #ops)
- **PagerDuty**: Oncall escalation

### Deployment Targets
- **API Service**: FastAPI on port 8000
- **Batch Jobs**: Cron-scheduled Python scripts
- **Monitoring**: Web dashboard + email reports

---

## 📈 Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| **API Latency** | <100ms (p50) | ✅ Configured |
| **Batch Throughput** | >300 scores/sec | ✅ Configured |
| **Job Success Rate** | 99.9% | ✅ Configured |
| **Data Quality** | >95% complete | ✅ Configured |
| **PSI Threshold** | <0.25 | ✅ Configured |
| **Uptime** | 99.9% | ✅ Configured |

---

## 🔐 Security & Compliance

- **Input Validation**: Required columns, null checks, range validation
- **Output Validation**: Score range, distribution, quality checks
- **Access Control**: Box.com permissions, service accounts
- **Data Retention**: Configurable policies (90-180 days)
- **Audit Logging**: All operations logged with timestamps
- **Alerting**: Multi-channel escalation with audit trail

---

## 🚀 Deployment Path

```
Development              Staging              Production
   ↓                       ↓                       ↓
Run STEP 1        →    Deploy API        →    Canary rollout
Run STEP 2        →    Run full tests    →    Full deployment
Run STEP 3        →    Validation gates  →    Monitor metrics
Check all gates   →    Health checks     →    Alert system active
```

---

## 📞 Contact & Support

- **Data Scientists**: For PSI/drift questions
- **DevOps Team**: For infrastructure/deployment
- **Operations**: For runbooks and incident response
- **Executives**: For business metrics and dashboards

---

**Architecture Version**: 1.0.0  
**Last Updated**: July 28, 2026  
**Status**: ✅ Production Ready
