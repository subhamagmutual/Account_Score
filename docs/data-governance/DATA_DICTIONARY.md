# PAS Data Dictionary

## Overview

The Physician Account Score (PAS) system uses 23 key performance indicators (KPIs) organized into 4 scoring components to calculate composite physician risk scores. This document provides detailed definitions, data ranges, and calculation methods for each variable.

**Scoring Framework:**
- **Composite Score Range:** 1-10 (integer, where 1 = lowest risk, 10 = highest risk)
- **Component Score Range:** 1-10 (based on sub-score distributions)
- **Sub-Score Range:** 1-30 (individual KPI binning output)

---

## Component 1: ADEQUACY (40% Weight)

**Definition:** Measures whether the physician has adequate loss reserves and premium relative to claims experience.

**Total Variables:** 9

### 1. Total Loss Cost
- **Full Name:** Total Loss Cost Per Basic Coverage Equivalent (BCE)
- **Weight:** 20% (within Adequacy)
- **Source Column:** `ULT_Total_LOSS_COST_PER_BCE`
- **Calculation:** `AMT_GROSS_RPTD_TOTAL_TRENDED / BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED`
- **Definition:** Ultimate total indemnity and defense losses divided by exposure (BCE). Normalized for development and inflation.
- **Range:** 0 - $500K+ per BCE
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes (Z-factor weighting for low-premium accounts)
- **Interpretation:** Higher values indicate greater claims activity; scores 1-10 reflect percentile rankings

### 2. Indemnity Loss Cost
- **Full Name:** Indemnity Loss Cost Per Basic Coverage Equivalent
- **Weight:** 10% (within Adequacy)
- **Source Column:** `ULT_Indemnity_LOSS_COST_PER_BCE`
- **Calculation:** `AMT_GROSS_RPTD_IND_TRENDED / BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED`
- **Definition:** Settlement and judgment amounts (indemnity only, excludes defense) per BCE.
- **Range:** 0 - $500K+ per BCE
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Interpretation:** Direct measure of settlement severity; drives high-risk assessment

### 3. Expense Loss Cost
- **Full Name:** Defense/Expense Loss Cost Per Basic Coverage Equivalent
- **Weight:** 5% (within Adequacy)
- **Source Column:** `ULT_Expense_LOSS_COST_PER_BCE`
- **Calculation:** `AMT_GROSS_RPTD_EXP_TRENDED / BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED`
- **Definition:** Defense costs, expert fees, and allocated loss adjustment expenses per BCE.
- **Range:** 0 - $100K+ per BCE
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Interpretation:** Defense costs correlate with litigousness; high values suggest difficult cases

### 4. Total Frequency
- **Full Name:** Total Claims Frequency Per Full-Time Equivalent (FTE)
- **Weight:** 10% (within Adequacy)
- **Source Column:** `ULT_Total_FREQUENCY_PER_FTE`
- **Calculation:** `CNT_GROSS_RPTD_TOTAL_GT_0 / FTE_EXPOSURE_CNT_GROSS_RPTD_TOTAL_GT_0_TRENDED_BURNED`
- **Definition:** Total claims (including denied and withdrawn) per full-time equivalent exposure.
- **Range:** 0 - 50+ claims per FTE per year
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Interpretation:** Frequency score (independent of severity); high = litigious environment

### 5. Indemnity Frequency
- **Full Name:** Indemnity Claims Frequency Per FTE
- **Weight:** 5% (within Adequacy)
- **Source Column:** `ULT_Indemnity_FREQUENCY_PER_FTE`
- **Calculation:** `CNT_GROSS_RPTD_IND_GT_0 / FTE_EXPOSURE_CNT_GROSS_RPTD_IND_GT_0_TRENDED_BURNED`
- **Definition:** Frequency of paid/settled claims (only those with indemnity payouts) per FTE.
- **Range:** 0 - 20+ paid claims per FTE per year
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Interpretation:** Subset of total frequency; indicates legitimate claim rate vs. frivolous

### 6. Total Severity
- **Full Name:** Average Claims Severity (Loss per Claim)
- **Weight:** 5% (within Adequacy)
- **Source Column:** `ULT_Total_SEVERITY`
- **Calculation:** `ADJ_LOSS_FOR_SEVERITY / CNT_GROSS_RPTD_TOTAL_GT_0`
- **Definition:** Average ultimate loss amount per reported claim (includes closed and pending).
- **Range:** $10K - $5M+ per claim
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Only When:** Claims exist (excludes claims-free physicians)
- **Interpretation:** Severity independent of frequency; high values = expensive claims

### 7. Actual Loss Ratio
- **Full Name:** Incurred Loss Ratio (Burned)
- **Weight:** 10% (within Adequacy)
- **Source Column:** `ULT_ACTUAL_LOSS_RATIO_BURNED`
- **Calculation:** `AMT_GROSS_RPTD_TOTAL_TRENDED / WRTN_PREM_AMT_ITD_BURNED_CLASS_OL`
- **Definition:** Total trended losses divided by written premiums (up to attachment point).
- **Range:** 0% - 500%+ (unbounded; values >100% indicate loss)
- **Binning Method:** Quantile (10 bins)
- **Credibility:** Yes
- **Interpretation:** Premium adequacy metric; >100% means premium insufficient for claims

### 8. Loss-Free Years
- **Full Name:** Years Since Last Claim
- **Weight:** 10% (within Adequacy)
- **Source Column:** `CV_LOSS_FREE_YEARS`
- **Definition:** Count of consecutive years with zero reported claims.
- **Range:** 0 - 50+ years
- **Binning Method:** Quantile (10 bins)
- **Invert Score:** Yes (higher years = better = lower score 1-10)
- **Credibility:** Yes
- **Interpretation:** Clean history; 5+ years loss-free = improved score

### 9. Limits to Premium Ratio
- **Full Name:** Coverage Limits Relative to Premium
- **Weight:** 10% (within Adequacy)
- **Source Column:** TOP_PER_M (per occurrence limit)
- **Calculation:** `(TOP_PER_M * 1,000,000) / WRTN_PREM_AMT_ITD_BURNED`
- **Definition:** Ratio of per-occurrence limit to annual premium. High ratio = large limits, low premium = aggressive coverage.
- **Range:** 0.5x - 50x+ premium
- **Binning Method:** Quantile (10 bins)
- **Credibility:** No
- **Interpretation:** Aggressive underwriting (high limits, low premium) = risk

---

## Component 2: CAPACITY (25% Weight)

**Definition:** Assesses the physician's financial and operational capacity to handle insurance obligations.

**Total Variables:** 3

### 10. Per-Occurrence Limit
- **Full Name:** Per-Occurrence Coverage Limit
- **Weight:** 20% (within Capacity)
- **Source Column:** `TOP_PER_M`
- **Definition:** Maximum coverage amount per single claim/occurrence (in millions).
- **Range:** $0.5M - $10M+
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Higher limits = better financial safety; low limits = elevated risk

### 11. Aggregate Limit
- **Full Name:** Annual Aggregate Coverage Limit
- **Weight:** 10% (within Capacity)
- **Source Column:** `TOP_AGG_M`
- **Definition:** Maximum total coverage amount per policy year (in millions).
- **Range:** $1M - $20M+
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Portfolio protection; aggregate exhaustion = uninsured future claims

### 12. Risk Count
- **Full Name:** Number of Distinct Locations/Operations
- **Weight:** 10% (within Capacity)
- **Source Column:** `RISK_COUNT`
- **Definition:** Count of separate practice locations, hospital affiliations, or operational entities.
- **Range:** 1 - 100+ locations
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Complex operations (many locations) = administrative burden and higher coordination risk

---

## Component 3: APPETITE (25% Weight)

**Definition:** Evaluates whether the physician represents a good "appetite fit" for the carrier based on practice and demographic factors.

**Total Variables:** 7

### 13. Specialty Risk Tier
- **Full Name:** Medical Specialty Risk Classification
- **Weight:** 25% (within Appetite)
- **Source Column:** `OL_RISK_SPECIALTY_DESC`
- **Lookup Config:** `specialty_tiers.json`
- **Definition:** Specialty-based risk tier (1-10) for common MPL specialties. Reflects litigation frequency and claim severity by specialty.
- **Range:** 1 - 10
- **Common Tiers:** 
  - Tier 1-2: Low-risk (Family Medicine, Psychiatry)
  - Tier 5: Medium (General Surgery, Internal Medicine)
  - Tier 8-10: High-risk (Neurosurgery, Cardiac Surgery, OB/GYN)
- **Default:** 5 (for unknown specialties)
- **Binning Method:** Categorical lookup
- **Interpretation:** Single largest appetite driver; specialty selection is primary underwriting decision

### 14. State Venue Risk
- **Full Name:** State/Jurisdiction Legal Environment
- **Weight:** 15% (within Appetite)
- **Source Column:** `ST`
- **Lookup Config:** `state_tiers.json`
- **Definition:** Risk tier (1-10) by state reflecting legal climate, jury verdicts, regulatory environment.
- **Range:** 1 - 10
- **Factors:** Jury tendencies, damage caps, statute of limitations, healthcare litigation trends
- **Default:** 5 (for unknown states)
- **Binning Method:** Categorical lookup
- **Interpretation:** Geographic risk; high-loss states (e.g., CA, NY, TX) score 8-10

### 15. Years Since Graduation
- **Full Name:** Physician Career Stage
- **Weight:** 10% (within Appetite)
- **Source Column:** `YEARS_SINCE_GRAD_IMPUTED`
- **Definition:** Years since medical school graduation (proxy for career maturity).
- **Range:** 0 - 60+ years
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Recent graduates (0-5 years) = higher risk; established physicians (20+ years) = lower risk

### 16. RVU Ratio
- **Full Name:** Relative Value Unit Productivity vs. Specialty Average
- **Weight:** 10% (within Appetite)
- **Source Column:** `RVU_WORK_TOTAL_RATIO_SPEC_OL`
- **Definition:** Physician's total RVU production divided by specialty average RVU. Ratio >1.0 = above-average productivity.
- **Range:** 0.2 - 3.0+
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** High RVU (>1.5x specialty average) = high-volume practice = higher claims exposure

### 17. Tenure with Carrier
- **Full Name:** Years Insured with Mag Mutual
- **Weight:** 5% (within Appetite)
- **Source Column:** `CV_YEARS_WITH_MAG`
- **Definition:** Consecutive years of active coverage with Mag Mutual.
- **Range:** 0 - 50+ years
- **Binning Method:** Quantile (10 bins)
- **Invert Score:** Yes (longer = better = lower score)
- **Interpretation:** Loyalty/history; new physicians = higher risk; 10+ year customers = retention value

### 18. Hospital Rating
- **Full Name:** Hospital Quality Rating
- **Weight:** 5% (within Appetite)
- **Source Column:** `HOSP_HOSPITALCOMPARE_OVERALLRATING`
- **Definition:** CMS Hospital Compare overall quality rating (1-5 stars) for primary affiliated hospital.
- **Range:** 1 - 5 stars
- **Binning Method:** Quantile (5 bins)
- **Invert Score:** Yes (higher rating = better = lower score)
- **Interpretation:** Hospital safety culture impacts physician risk; poor-rated hospitals = higher risk

### 19. Practice Size
- **Full Name:** Number of Providers in Group
- **Weight:** 5% (within Appetite)
- **Source Column:** `WITH_WHOM_LOCATION_DISTINCT_NPI`
- **Definition:** Count of distinct NPIs (providers) at the same location/practice.
- **Range:** 1 - 1000+ (solo to large group)
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Solo practitioners = isolated decision-making (risk); large groups = peer review/oversight (safety)

---

## Component 4: ENVIRONMENT (10% Weight)

**Definition:** Captures external socioeconomic and demographic factors affecting claims environment.

**Total Variables:** 4

### 20. Income Inequality
- **Full Name:** Gini Coefficient (Income Inequality)
- **Weight:** 5% (within Environment)
- **Source Column:** `INCOME_RATIO`
- **Definition:** Gini coefficient for county-level income distribution (0-1 scale; 0=equal, 1=complete inequality).
- **Range:** 0.3 - 0.6+
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** High inequality = social tension = more litigation risk

### 21. Population Density
- **Full Name:** Population Density
- **Weight:** 5% (within Environment)
- **Source Column:** `POP_DENSITY_SQ_MILES`
- **Definition:** County population density (persons per square mile).
- **Range:** 1 - 50,000+ per sq. mile
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** High density = urban litigation culture = higher risk; rural = lower risk

### 22. Violent Crime Rate
- **Full Name:** Violent Crime Rate
- **Weight:** 3% (within Environment)
- **Source Column:** `VIOLENT_CRIME_RATE_PER_100K`
- **Definition:** FBI-reported violent crimes per 100,000 population (county level).
- **Range:** 0 - 2000+ per 100K
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** Crime correlates with litigious environment; proxy for social cohesion

### 23. Percent Uninsured
- **Full Name:** Percentage of Uninsured Population
- **Weight:** 2% (within Environment)
- **Source Column:** `PCT_UNINSURED`
- **Definition:** Percent of county population without health insurance (ACS Census data).
- **Range:** 1% - 40%+
- **Binning Method:** Quantile (10 bins)
- **Interpretation:** High uninsured = financial stress on patients = collection disputes, hostile interactions

---

## Scoring Rules & Special Cases

### Credibility Weighting (Z-Factor)
- **Applied To:** Adequacy sub-scores and Loss-Free Years
- **Full Credibility Premium:** $50,000 written premium
- **Partial Credibility:** Linear interpolation between 0 and 1.0
- **Z-Factor Formula:** `min(1.0, Premium / 50,000)`
- **Effect:** Sub-scores < $50K premium are pulled toward portfolio mean (score 15), reducing extreme scores

### Loss-Free Years Special Handling
- **Inverted Scoring:** Loss-free physicians score LOWER (better) on 1-10 scale
- **Example:** 10 years loss-free → Score 1; 0 years → Score 10

### Missing/Null Data
- **Default Bin Score:** -1 (invalid; triggers credibility adjustment)
- **Handling:** Records with credibility Z-factor <1.0 use portfolio mean as default
- **Clean Records:** All 23 variables present and non-null required for composite score

### Component Score Calculation
- **Weighting:** Weighted average of sub-scores (rescaled 1-10)
- **Null Sub-Scores:** Excluded from component average (denominator reduced)
- **Composite Score:** Weighted average of 4 component scores, capped at 1-10, rounded to integer

---

## Data Quality Standards

| Issue | Standard | Action |
|-------|----------|--------|
| Missing Values | <5% per variable | Flag for investigation |
| Outliers | >3 SD from mean | Document; may retain |
| Duplicates | 0 allowed | Remove, investigate source |
| Data Staleness | <2 years | Refresh annually |
| Null Frequency | <50% per column | Acceptable; use defaults |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-28 | Initial data dictionary for 23 KPI variables |

---

**Last Updated:** July 28, 2026  
**Document Owner:** Actuarial Analytics  
**Review Frequency:** Annual
