# PAS SYSTEM - QUICK REFERENCE GUIDE
**Physician Adequacy Scoring | July 2026**

---

## ⚡ AT A GLANCE

**What is PAS?** A deterministic weighted-average model that scores physician risk 1-10 (1=low, 10=high).

**Where does it run?** REST API that scores applications in real-time. Stores results in database.

**Who uses it?** Underwriters, underwriting applications, triage systems.

**How accurate?** Deterministic & transparent—same input always produces same score. Explained by input data.

---

## 🎯 THE SCORE FORMULA

**Composite Score = Weighted Average of 4 Components**

| Component | Weight | What It Measures |
|-----------|--------|-----------------|
| **Adequacy** | 40% | Loss history, frequency, severity, loss-free years |
| **Capacity** | 25% | Coverage limits (per-occurrence, aggregate), risk count |
| **Appetite** | 25% | Specialty risk, state risk, experience, RVU ratio, tenure |
| **Environment** | 10% | Regional factors (income inequality, population density, crime, uninsured %) |

**Formula**: `composite = SUM(W_c × Score_c) / SUM(W_c)` where missing components' weights redistribute proportionally.

---

## 📊 TRIAGE BY SCORE

| Score | Decision | Action | Time |
|-------|----------|--------|------|
| **1-3** | ✅ AUTO-APPROVE | Issue policy immediately | <1 min |
| **4-7** | ⏸️ MANUAL REVIEW | Underwriter judgment needed | 2-5 days |
| **8-10** | ❌ AUTO-DECLINE | Refer to senior underwriter/decline | 1-3 days |

**Manual Review Checklist** (scores 4-7):
- [ ] Verify loss history accuracy (3 recent claims)
- [ ] Confirm coverage limits match policy documents
- [ ] Check specialty classification is correct
- [ ] Verify state/location is accurate
- [ ] Look for outliers or unusual patterns

---

## 🔧 FOR DEVELOPERS

### API Endpoints

```
POST   /api/v1/physicians/{npi}/score          → Compute score
GET    /api/v1/physicians/{npi}/latest-score   → Get most recent score
GET    /api/v1/physicians/{npi}/score-history  → Get historical scores
```

### Minimum Request Payload

```json
{
  "npi": 1234567890,
  "specialty": "Orthopedic Surgery",
  "state": "CA",
  "loss_data": {
    "total_loss_cost_per_bce": 45000,
    "total_frequency_per_fte": 0.35,
    "actual_loss_ratio": 0.85,
    "loss_free_years": 2
  },
  "coverage_data": {
    "per_occurrence_limit_millions": 1.0,
    "aggregate_limit_millions": 3.0
  },
  "premium_for_credibility": 75000
}
```

### Response

```json
{
  "composite_score": 6,
  "components": {
    "adequacy": 6.5,
    "capacity": 7.0,
    "appetite": 5.5,
    "environment": 5.0
  },
  "triage_decision": {
    "category": "manual_review",
    "reason": "Composite score 6 falls in manual review range"
  }
}
```

### Implementation Checklist

- [ ] Load config (weights, thresholds, tiers) from files
- [ ] Create database tables (physicians, physician_scores, sub_scores)
- [ ] Implement weighted_avg() with weight-zeroing for missing values
- [ ] Apply credibility blending: `Z = MIN(SQRT(premium / 50000), 1)`
- [ ] Implement binning logic (quantile, equal_width, log_scale)
- [ ] Build REST endpoints with auth, logging, error handling
- [ ] Cache reference data (specialty/state tiers)
- [ ] Write audit trail on every score
- [ ] Test with 50-100 real physician cases
- [ ] Validate latency <200ms, uptime >99.5%

---

## 📋 KEY INSIGHTS FROM IMPORTANCE ANALYSIS

### Top 5 Variables (by direct impact)

1. **total_loss_cost** (Adequacy) — Loss history is king
2. **specialty_risk_tier** (Appetite) — Specialty matters a lot
3. **per_occurrence_limit** (Capacity) — Coverage limits important
4. **indemnity_loss_cost** (Adequacy) — Detailed loss breakdown
5. **total_frequency** (Adequacy) — Claims frequency counts

### Dead Weight (Candidates for Removal)

All 4 **Environment variables** combined = <2% importance:
- income_inequality
- population_density
- violent_crime_rate
- pct_uninsured

**Recommendation**: Consider dropping environment component entirely (10% weight) and reallocating.

---

## 🚨 COMMON EDGE CASES

| Scenario | How It's Handled |
|----------|-----------------|
| **Missing loss history** | Score pulled toward 5 via credibility blending; weight redistributed |
| **Very low premium (<$50K)** | Credibility Z decreases; Adequacy pulled toward portfolio avg (5) |
| **Multiple practice locations** | Score each NPI separately; can aggregate if needed |
| **Specialty not in lookup table** | Default score = 5 (portfolio average) |
| **All components missing** | Returns NaN (invalid) |
| **Score exactly 3.5** | Rounds to 4 (manual_review) |

---

## 📊 SAMPLE DATA VALIDATION

Check your data before going live:

```sql
-- Should have ~25% auto-approve, ~50% manual, ~25% auto-decline (rough guide)
SELECT 
  triage_category, 
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM physician_scores), 1) as pct
FROM physician_scores
GROUP BY triage_category;

-- Check for missing/invalid scores
SELECT COUNT(*) FROM physician_scores WHERE composite_score IS NULL;

-- Check latency
SELECT 
  AVG(EXTRACT(EPOCH FROM (created_at - scored_at))) as avg_sec,
  MAX(EXTRACT(EPOCH FROM (created_at - scored_at))) as max_sec
FROM physician_scores;
```

---

## 🔗 INTEGRATION POINTS

1. **Underwriting Application** → Calls API when application submitted
2. **Claims Database** → Provides loss history data
3. **Policy Database** → Provides coverage limits, risk count
4. **NPDB/AMA** → Provides physician attributes (specialty, tenure, etc.)
5. **Triage Queue** → Receives decision, routes application

---

## 📞 TROUBLESHOOTING

| Issue | Check |
|-------|-------|
| All scores = 5 | Are reference tables (specialty_tiers, state_tiers) loaded? |
| Scores outside 1-10 | Check rounding & capping logic |
| High latency (>500ms) | Check database indices, binning threshold lookups |
| Inconsistent scores | Verify input normalization, missing value handling |
| Audit trail gaps | Ensure INSERT to sub_scores happens atomically with physician_scores |

---

## 📖 DOCUMENTATION

- **Production_Deployment_Guide.docx** — Full technical deployment guide (7 sections, 25+ pages)
- **feature_importance_analysis.xlsx** — Sensitivity analysis, variable importance ranking
- **feature_importance_analysis.py** — Python tool for running your own importance analysis
- **scoring_weights.json** — All weights and variable definitions
- **specialty_tiers.json** — Specialty risk mapping (1-10 scale)
- **state_tiers.json** — State risk mapping (1-10 scale)

---

## ✅ SUCCESS METRICS

Monitor these after go-live:

| Metric | Target |
|--------|--------|
| API Uptime | 99.5% |
| API Latency (p95) | <200ms |
| Underwriter Satisfaction | 80%+ say score is "reasonable" |
| Processing Time (Auto-Approve) | <1 day |
| Processing Time (Manual Review) | <5 days |
| Score Distribution | Spans 1-10, not clustered at 5 |
| Data Quality | 0 invalid/missing scores |

---

**Last Updated**: July 28, 2026  
**Model Version**: PAS v1.0  
**Contact**: [Your team]
