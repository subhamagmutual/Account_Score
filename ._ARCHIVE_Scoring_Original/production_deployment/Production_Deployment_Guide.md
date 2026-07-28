# PRODUCTION DEPLOYMENT GUIDE
## Physician Adequacy Scoring (PAS) System
### Integration • Architecture • Implementation
---

**July 2026**

---

## TABLE OF CONTENTS

1. Executive Summary
2. System Architecture & Integration Points
3. Database Schema Design
4. REST API Specification
5. Scoring Pipeline (Backend)
6. Triage Logic & Decision Rules
7. Example Workflows
8. Implementation Checklist

---

## 1. EXECUTIVE SUMMARY

The Physician Adequacy Scoring (PAS) system is a deterministic weighted-average model that produces a composite risk score (1-10) for each physician based on four components:

- **Adequacy (40%)**: Loss history, frequency, severity, loss ratio, loss-free years, limits
- **Capacity (25%)**: Coverage limits (per-occurrence, aggregate) and risk count
- **Appetite (25%)**: Specialty, state, experience, RVU ratio, tenure, hospital rating, practice size
- **Environment (10%)**: Regional socioeconomic factors (income inequality, population density, crime, uninsured rate)

This guide covers production deployment: how to integrate the model into your underwriting workflow via SQL schema, REST API, and automated triage logic.

### Key Deliverables

- Normalized database schema for storing physician scores and related data
- Stateless REST API for scoring new applications in real-time
- Triage decision rules (auto-approve, manual review, auto-decline)
- Implementation roadmap and validation checks

---

## 2. SYSTEM ARCHITECTURE & INTEGRATION POINTS

### 2.1 High-Level Architecture

The PAS system integrates into your underwriting workflow at four critical points:

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Underwriting   │─────>│  PAS Scoring API │─────>│   Score & Triage │
│   Application   │      │   (REST/GraphQL) │      │    Database      │
└─────────────────┘      └──────────────────┘      └──────────────────┘

        Input Data              Compute             Storage & Decision
    (physician details,      (weighted average)     (audit trail, rules)
     loss history, state)    (quantile binning)
```

### 2.2 Integration Points

#### A. Underwriting Application → PAS API

When a physician application is submitted:

- **Collect**: NPI, specialty, state, loss history, limits, practice data
- **Call**: `POST /physicians/{npi}/score`
- **Receive**: Composite score, component breakdown, triage recommendation

#### B. Data Sources for Scoring

The model requires real-time data on:

- **Loss Data**: Total/indemnity/expense loss costs, severity, frequency (from claims database)
- **Coverage Data**: Per-occurrence limits, aggregate limits, risk count (from policy database)
- **Physician Data**: Specialty, state, years since graduation, RVU ratio (from NPDB/AMA)
- **Environmental Data**: Income inequality, population density, crime rate (from US Census/CDC)

#### C. Output → Triage System

Scoring results feed into triage logic:

- **Scores 1-3**: Auto-approve (low risk) → Expedited
- **Scores 4-7**: Manual review required (medium risk) → Queue for underwriter
- **Scores 8-10**: Auto-decline or refer (high risk) → Escalation

### 2.3 Data Flow Example

Here's a complete flow from application to decision:

1. Underwriter enters physician details in system
2. System queries claims database for loss history
3. API receives data, binds to reference data (specialty tier, state tier)
4. Composite score computed (weighted average)
5. Score stored in database with audit trail
6. Triage rule applied → decision queued
7. Underwriter sees recommendation, makes final call

---

## 3. DATABASE SCHEMA DESIGN

The schema supports real-time scoring with full audit trail. Key principles:

- Normalize around physician (NPI) as primary key
- Store all inputs (sub-scores) separately for auditability
- Reference tables for categorical lookups (specialty, state tiers)
- Audit trail for compliance and debugging

### 3.1 Core Tables

#### physicians

```sql
CREATE TABLE physicians (
  npi BIGINT PRIMARY KEY,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  specialty VARCHAR(100),
  state CHAR(2),
  years_since_graduation INT,
  npi_record_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### physician_scores

```sql
CREATE TABLE physician_scores (
  score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  npi BIGINT NOT NULL REFERENCES physicians(npi),
  
  -- Component scores (1-10)
  adequacy_score NUMERIC(3,1),
  capacity_score NUMERIC(3,1),
  appetite_score NUMERIC(3,1),
  environment_score NUMERIC(3,1),
  
  -- Composite
  composite_score_raw NUMERIC(4,3),
  composite_score INT CHECK (composite_score BETWEEN 1 AND 10),
  
  -- Triage decision
  triage_category VARCHAR(20),  -- 'auto_approve', 'manual_review', 'auto_decline'
  
  -- Audit
  scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  application_id VARCHAR(50),
  scored_by_system VARCHAR(100),  -- API version/name
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_physician_scores_npi ON physician_scores(npi);
CREATE INDEX idx_physician_scores_created ON physician_scores(created_at DESC);
CREATE INDEX idx_physician_scores_triage ON physician_scores(triage_category);
```

#### sub_scores (Input Detail)

```sql
CREATE TABLE sub_scores (
  sub_score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  score_id UUID NOT NULL REFERENCES physician_scores(score_id),
  npi BIGINT NOT NULL,
  
  -- Variable name and value (1-10 scale, 0 = missing)
  variable_name VARCHAR(100),
  variable_value NUMERIC(3,1),
  component VARCHAR(50),  -- 'adequacy', 'capacity', 'appetite', 'environment'
  
  -- Raw data that led to this score (for auditability)
  raw_data JSONB,  -- e.g., {"total_loss_cost": 45000, "premium": 100000}
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sub_scores_score_id ON sub_scores(score_id);
CREATE INDEX idx_sub_scores_npi ON sub_scores(npi);
CREATE INDEX idx_sub_scores_variable ON sub_scores(variable_name);
```

### 3.2 Reference Tables

#### specialty_tiers

```sql
CREATE TABLE specialty_tiers (
  tier_id SERIAL PRIMARY KEY,
  specialty_description VARCHAR(255) UNIQUE,
  tier_score INT CHECK (tier_score BETWEEN 1 AND 10),
  tier_label VARCHAR(50),  -- 'Low', 'Medium', 'High', etc.
  loss_ratio_avg NUMERIC(5,3),  -- Historical reference
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Example:
INSERT INTO specialty_tiers (specialty_description, tier_score, tier_label)
VALUES 
  ('Nurse Practitioner', 1, 'Low'),
  ('Psychiatry', 2, 'Low'),
  ('Orthopedic Surgery', 5, 'Medium'),
  ('Cardiovascular Disease', 9, 'Very High');
```

#### state_tiers

```sql
CREATE TABLE state_tiers (
  tier_id SERIAL PRIMARY KEY,
  state_code CHAR(2) UNIQUE,
  tier_score INT CHECK (tier_score BETWEEN 1 AND 10),
  tier_label VARCHAR(50),
  tort_environment VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Example:
INSERT INTO state_tiers (state_code, tier_score, tier_label, tort_environment)
VALUES 
  ('NC', 1, 'Favorable', 'Low'),
  ('CA', 4, 'Average', 'Mixed'),
  ('IL', 9, 'Severe', 'High');
```

#### binning_thresholds

```sql
CREATE TABLE binning_thresholds (
  threshold_id SERIAL PRIMARY KEY,
  variable_name VARCHAR(100),
  bin_number INT,  -- 1-30
  lower_bound NUMERIC(12,2),
  upper_bound NUMERIC(12,2),
  score_1_to_10 INT,  -- Mapped score
  method VARCHAR(50),  -- 'quantile', 'equal_width', 'log_scale', 'categorical'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_binning_variable ON binning_thresholds(variable_name);
```

### 3.3 Audit & Logging Tables

#### score_audit_log

```sql
CREATE TABLE score_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  score_id UUID NOT NULL REFERENCES physician_scores(score_id),
  npi BIGINT NOT NULL,
  
  action VARCHAR(100),  -- 'created', 'modified', 'overridden'
  old_score INT,
  new_score INT,
  reason VARCHAR(500),
  modified_by VARCHAR(100),  -- Underwriter ID or system
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_score_id ON score_audit_log(score_id);
CREATE INDEX idx_audit_log_npi ON score_audit_log(npi);
```

### 3.4 Sample Queries

#### Get Latest Score for a Physician

```sql
SELECT ps.*, p.specialty, p.state
FROM physician_scores ps
JOIN physicians p ON ps.npi = p.npi
WHERE ps.npi = $1
ORDER BY ps.scored_at DESC
LIMIT 1;
```

#### Triage Report: All Manual Reviews Today

```sql
SELECT 
  p.npi, p.first_name, p.last_name, p.specialty, p.state,
  ps.composite_score, ps.triage_category,
  ps.scored_at, ps.application_id
FROM physician_scores ps
JOIN physicians p ON ps.npi = p.npi
WHERE ps.triage_category = 'manual_review'
  AND DATE(ps.scored_at) = CURRENT_DATE
ORDER BY ps.composite_score DESC;
```

#### Sub-Score Detail for Auditability

```sql
SELECT 
  ss.variable_name, ss.variable_value, ss.component,
  ss.raw_data
FROM sub_scores ss
WHERE ss.score_id = $1
ORDER BY ss.component, ss.variable_name;
```

---

## 4. REST API SPECIFICATION

The API provides stateless endpoints for scoring and retrieving scores. Design principle: API is read/compute only—all write operations are via internal pipeline.

### 4.1 Authentication & Headers

```
Authorization: Bearer <api_token>
Content-Type: application/json
X-Request-ID: <uuid>  -- Unique request ID for audit trail
X-User-ID: <underwriter_id>  -- For audit logging
```

### 4.2 Core Endpoints

#### POST /api/v1/physicians/{npi}/score

Score a physician application in real-time.

**Request Body**:

```json
{
  "npi": 1234567890,
  "specialty": "Orthopedic Surgery",
  "state": "CA",
  "loss_data": {
    "total_loss_cost_per_bce": 45000,
    "indemnity_loss_cost_per_bce": 28000,
    "expense_loss_cost_per_bce": 17000,
    "total_frequency_per_fte": 0.35,
    "indemnity_frequency_per_fte": 0.22,
    "total_severity": 125000,
    "actual_loss_ratio": 0.85,
    "loss_free_years": 2
  },
  "coverage_data": {
    "per_occurrence_limit_millions": 1.0,
    "aggregate_limit_millions": 3.0,
    "risk_count": 1
  },
  "physician_attributes": {
    "years_since_graduation": 15,
    "rvu_ratio": 1.05,
    "tenure_with_carrier_years": 8,
    "hospital_rating": 5,
    "practice_size": 3
  },
  "environmental_data": {
    "income_ratio": 7.2,
    "population_density": 1250,
    "violent_crime_rate": 150,
    "pct_uninsured": 12
  },
  "premium_for_credibility": 75000,
  "application_id": "APP-2026-07-12345"
}
```

**Response (200 OK)**:

```json
{
  "npi": 1234567890,
  "score_id": "550e8400-e29b-41d4-a716-446655440000",
  "components": {
    "adequacy": 6.5,
    "capacity": 7.0,
    "appetite": 5.5,
    "environment": 5.0
  },
  "composite_score_raw": 6.123,
  "composite_score": 6,
  "triage_decision": {
    "category": "manual_review",
    "reason": "Composite score 6 falls in manual review range (4-7)",
    "recommended_next_step": "Route to underwriter for loss history review"
  },
  "scoring_timestamp": "2026-07-28T14:32:15Z",
  "model_version": "PAS-v1.0",
  "audit_trail": {
    "application_id": "APP-2026-07-12345",
    "user_id": "underwriter_123",
    "request_id": "req-xyz-789"
  }
}
```

#### GET /api/v1/physicians/{npi}/latest-score

Retrieve the most recent score for a physician.

**Response (200 OK)**:

```json
{
  "npi": 1234567890,
  "composite_score": 6,
  "scored_at": "2026-07-28T14:32:15Z",
  "triage_category": "manual_review",
  "application_id": "APP-2026-07-12345",
  "score_detail": {
    "adequacy": 6.5,
    "capacity": 7.0,
    "appetite": 5.5,
    "environment": 5.0
  },
  "sub_scores": [
    {
      "variable": "total_loss_cost",
      "component": "adequacy",
      "score": 7,
      "raw_value": 45000
    }
  ]
}
```

#### GET /api/v1/physicians/{npi}/score-history

Get historical scores (last 10 or last 6 months).

**Query params**:
- `limit`: number of scores (default 10, max 100)
- `days`: how many days back (default all)

**Response**:

```json
{
  "npi": 1234567890,
  "scores": [
    {
      "score_id": "550e8400-e29b-41d4-a716-446655440000",
      "composite_score": 6,
      "scored_at": "2026-07-28T14:32:15Z",
      "application_id": "APP-2026-07-12345"
    },
    {
      "score_id": "660e8400-e29b-41d4-a716-446655440111",
      "composite_score": 5,
      "scored_at": "2026-03-10T09:15:42Z",
      "application_id": "APP-2026-03-54321"
    }
  ],
  "total_count": 2
}
```

### 4.3 Error Responses

#### 400 Bad Request

```json
{
  "error": "INVALID_INPUT",
  "message": "Missing required field: loss_data.total_loss_cost_per_bce",
  "request_id": "req-xyz-789"
}
```

#### 404 Not Found

```json
{
  "error": "PHYSICIAN_NOT_FOUND",
  "message": "No physician with NPI 1234567890 found",
  "request_id": "req-xyz-789"
}
```

#### 500 Internal Server Error

```json
{
  "error": "SCORING_FAILED",
  "message": "Error computing composite score",
  "detail": "Division by zero in component weighting",
  "request_id": "req-xyz-789"
}
```

### 4.4 Implementation Notes

**Statelessness**: 
- API does not store state. Each `/score` call recomputes from input data.
- Scores are written to database by the API but always in append-only manner (INSERT only).

**Performance**: 
- Expect latency: 50-200ms per score (binning lookups + database inserts).
- For high-volume batches, use batch endpoint or internal queue.

**Caching**: 
- Cache reference data (specialty/state tiers, binning thresholds) in application memory.
- Refresh cache on deploy or every 24 hours.

---

## 5. SCORING PIPELINE (BACKEND)

This section details the internal computation logic. Implementation can be in Python, Node.js, Java, etc.—the formula is language-agnostic.

### 5.1 The Weighted-Average Formula

Core formula with weight-zeroing for missing values:

```
component_score = SUM(W_i * S_i * I_i) / SUM(W_i * I_i)

where:
  W_i = weight of variable i (from config)
  S_i = score of variable i (1-10 or 0 if missing)
  I_i = indicator: 1 if S_i is not NaN/0, else 0

composite_score = SUM(W_c * C_c * I_c) / SUM(W_c * I_c)

where:
  W_c = weight of component c
  C_c = score of component c (1-10)
  I_c = indicator: 1 if C_c is not NaN, else 0
```

**Key insight**: If a variable/component is missing (NaN or 0), its weight is redistributed to other active variables/components.

### 5.2 Step-by-Step Computation

**Input**: Raw physician data (loss costs, limits, specialty, state, etc.)

#### Step 1: Lookup Categorical Variables

```python
specialty_score = specialty_tiers[specialty]  # 1-10
state_score = state_tiers[state]  # 1-10
if specialty not in specialty_tiers:
    specialty_score = 5  # default
```

#### Step 2: Normalize Continuous Variables (1-10 scale)

For each continuous variable, use pre-computed binning thresholds:

```python
# Example: total_loss_cost_per_bce
raw_value = 45000
bins = binning_thresholds['total_loss_cost']  # 30 bins
bin_idx = find_bin(raw_value, bins)
score = (bin_idx / 30) * 10  # Scaled to 1-10
```

#### Step 3: Apply Credibility Blending (Adequacy only)

If premium is low, pull Adequacy scores toward portfolio average (5):

```python
credibility_z = MIN(SQRT(premium / 50000), 1)
adequacy_raw = ... # computed from adequacy variables
adequacy_blended = credibility_z * adequacy_raw + (1 - credibility_z) * 5
```

#### Step 4: Compute Component Scores

Apply weighted average within each component:

```python
adequacy = weighted_avg(
    scores={
        'total_loss_cost': 6.5,
        'indemnity_loss_cost': 7.0,
        # ... other variables
    },
    weights={
        'total_loss_cost': 0.20,
        'indemnity_loss_cost': 0.10,
        # ... other weights
    }
)  # Result: 6.5

capacity = weighted_avg(...)  # Result: 6.8
appetite = weighted_avg(...)  # Result: 5.5
environment = weighted_avg(...)  # Result: 5.0
```

#### Step 5: Compute Composite Score

```python
composite_raw = weighted_avg(
    scores={
        'adequacy': 6.5,
        'capacity': 6.8,
        'appetite': 5.5,
        'environment': 5.0
    },
    weights={
        'adequacy': 0.40,
        'capacity': 0.25,
        'appetite': 0.25,
        'environment': 0.10
    }
)
# Result: 6.123
```

#### Step 6: Cap and Round

```python
composite_final = ROUND(composite_raw)  # 6
composite_final = CAP(composite_final, 1, 10)  # Ensure 1-10
```

#### Step 7: Write to Database with Audit Trail

```sql
INSERT INTO physician_scores 
  (npi, adequacy_score, capacity_score, appetite_score, 
   environment_score, composite_score_raw, composite_score, 
   triage_category, scored_at)
VALUES 
  (1234567890, 6.5, 6.8, 5.5, 5.0, 6.123, 6, 'manual_review', NOW());

INSERT INTO sub_scores 
  (score_id, npi, variable_name, variable_value, component, raw_data)
VALUES 
  (score_uuid, 1234567890, 'total_loss_cost', 6.5, 'adequacy', {...}),
  (score_uuid, 1234567890, 'specialty_score', 5.0, 'appetite', {...}),
  ...;
```

### 5.3 Pseudocode Implementation

```python
def weighted_avg(scores: dict, weights: dict) -> float:
    """Weighted average with weight-zeroing for missing values."""
    total = 0.0
    total_active_weight = 0.0
    
    for key, value in scores.items():
        if key in weights and not is_missing(value):
            w = weights[key]
            total += value * w
            total_active_weight += w
    
    if total_active_weight == 0:
        return NaN
    
    return total / total_active_weight


def compute_composite_score(physician_data):
    """Main scoring function."""
    
    # Load reference data
    specialty_tiers = load_specialty_tiers()
    state_tiers = load_state_tiers()
    binning_thresholds = load_binning_thresholds()
    weights = load_weights()
    
    # Normalize all inputs to 1-10 scale
    scores = {}
    
    # Adequacy variables
    scores['total_loss_cost'] = bin_and_scale(
        physician_data['total_loss_cost_per_bce'],
        binning_thresholds['total_loss_cost']
    )
    # ... more variables ...
    
    # Capacity variables
    scores['per_occurrence_limit'] = bin_and_scale(
        physician_data['per_occurrence_limit_millions'],
        binning_thresholds['per_occurrence_limit']
    )
    # ... more variables ...
    
    # Appetite variables (categorical lookups)
    scores['specialty_score'] = specialty_tiers.get(
        physician_data['specialty'], 5
    )
    scores['state_score'] = state_tiers.get(
        physician_data['state'], 5
    )
    # ... more variables ...
    
    # Environment variables
    # ... scoring logic ...
    
    # Apply credibility blending to Adequacy
    premium = physician_data['premium']
    z = min(sqrt(premium / 50000), 1)
    adequacy_raw = weighted_avg(
        scores={...},
        weights=weights['adequacy_sub_scores']
    )
    adequacy_score = z * adequacy_raw + (1 - z) * 5
    
    # Compute component scores
    adequacy = adequacy_score
    capacity = weighted_avg(...)
    appetite = weighted_avg(...)
    environment = weighted_avg(...)
    
    # Compute composite
    composite_raw = weighted_avg(
        scores={
            'adequacy': adequacy,
            'capacity': capacity,
            'appetite': appetite,
            'environment': environment
        },
        weights=weights['composite_weights']
    )
    composite = round(cap(composite_raw, 1, 10))
    
    # Determine triage decision
    triage = determine_triage(composite)
    
    return {
        'adequacy': adequacy,
        'capacity': capacity,
        'appetite': appetite,
        'environment': environment,
        'composite_raw': composite_raw,
        'composite': composite,
        'triage': triage,
        'sub_scores': scores
    }
```

---

## 6. TRIAGE LOGIC & DECISION RULES

Once a score is computed, triage rules determine the next action in underwriting.

### 6.1 Basic Triage Rules

**Composite Score 1-3**
- **Decision**: AUTO-APPROVE
- **Reason**: Low risk (1=best, 10=worst)
- **Action**: Issue policy (no manual review required)

**Composite Score 4-7**
- **Decision**: MANUAL REVIEW
- **Reason**: Medium risk (requires underwriter judgment)
- **Action**: Queue to underwriter for review; check loss history, verify medical records

**Composite Score 8-10**
- **Decision**: AUTO-DECLINE or REFER
- **Reason**: High risk (1=best, 10=worst)
- **Action**: Refer to senior underwriter or decline (policy dependent)

### 6.2 Enhanced Triage (Optional Rules)

Beyond simple score ranges, consider additional factors:

#### A. Component-Level Flags

```python
if adequacy > 7:
    # High loss history → require loss history review
    flag = 'LOSS_HISTORY_CONCERN'

if capacity < 3:
    # Low limits → require coverage adjustment
    flag = 'COVERAGE_CONCERN'

if appetite < 3:
    # High specialty risk → require specialty verification
    flag = 'SPECIALTY_CONCERN'
```

#### B. Trend Analysis

```python
# Get previous score
prev_score = get_previous_score(npi)

if prev_score and (current_score - prev_score) > 2:
    # Score jumped significantly → requires review
    flag = 'SCORE_DETERIORATION'
    action = 'manual_review'  # Override auto-approve if applicable
```

#### C. Specialty Overrides

```python
# Some specialties may have stricter thresholds
STRICTER_SPECIALTIES = ['Orthopedic Surgery', 'Cardiothoracic Surgery', ...]

if specialty in STRICTER_SPECIALTIES and composite >= 6:
    # Lower threshold for high-risk specialties
    triage = 'manual_review'  # Even if score = 5 normally
```

#### D. Multi-Location Policies

```python
if risk_count > 1:  # Physician with multiple practice locations
    # Aggregate risk across locations
    aggregate_score = aggregate_scores_by_physician(npi)
    if aggregate_score > 6:
        triage = 'manual_review'
```

### 6.3 Triage Decision Tree

```python
def determine_triage(composite, components, physician_data):
    
    # Check for component-level concerns
    flags = []
    
    if components['adequacy'] > 7:
        flags.append('LOSS_HISTORY_CONCERN')
    
    if components['capacity'] < 3:
        flags.append('COVERAGE_CONCERN')
    
    if physician_data['specialty'] in STRICTER_SPECIALTIES:
        threshold_manual = 6  # Lower threshold
    else:
        threshold_manual = 4
    
    # Primary decision by composite score
    if composite <= 3:
        decision = 'auto_approve'
    elif composite <= 7:
        decision = 'manual_review'
    else:
        decision = 'auto_decline'
    
    # Override for component flags or trends
    if len(flags) > 1:  # Multiple concerns
        decision = 'auto_decline' or 'escalate'
    
    # Override for deterioration
    prev_score = get_previous_score(physician_data['npi'])
    if prev_score and (composite - prev_score) > 3:
        decision = 'manual_review'  # Require re-evaluation
    
    return {
        'decision': decision,
        'flags': flags,
        'composite': composite,
        'reason': generate_reason_text(decision, composite, flags)
    }
```

### 6.4 Database Triggers & Workflow Integration

Automatically route scores:

```sql
CREATE TRIGGER trg_triage_routing AFTER INSERT ON physician_scores
FOR EACH ROW
EXECUTE FUNCTION route_to_queue();

CREATE FUNCTION route_to_queue() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.triage_category = 'auto_approve' THEN
        INSERT INTO approval_queue (score_id, status, action)
        VALUES (NEW.score_id, 'approved', 'issue_policy');
    ELSIF NEW.triage_category = 'manual_review' THEN
        INSERT INTO manual_review_queue (score_id, assigned_to, priority)
        VALUES (NEW.score_id, NULL, CASE 
            WHEN NEW.composite_score >= 6 THEN 'high'
            ELSE 'normal'
        END);
    ELSIF NEW.triage_category = 'auto_decline' THEN
        INSERT INTO decline_queue (score_id, status, reason)
        VALUES (NEW.score_id, 'pending_approval', 'high_composite_score');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### 6.5 Manual Review Guidelines

When a score falls in the manual review range (4-7), underwriters should check:

- **Loss History**: Verify accuracy of total loss cost, frequency, severity
- **Coverage Limits**: Ensure reported limits match policy documents
- **Specialty Classification**: Confirm specialty tier is correct (can shift score by ±2)
- **State Venue**: Verify location risk classification
- **Practice Details**: Check practice size, tenure, hospital affiliations
- **Outliers**: Look for any unusual or high-impact variables

### 6.6 Escalation Path

- **Score 8-10**: Refer to Senior Underwriter
- **Multiple Flags**: Route to Underwriting Manager
- **Repeated High Scores**: Route to Medical Director
- **Specialty Exception**: Route to Specialty Underwriter

---

## 7. EXAMPLE WORKFLOWS

### 7.1 Example 1: Auto-Approve Case

**Scenario**: 35-year-old Nurse Practitioner in North Carolina with clean loss history

**Input**:
- NPI: 1111111111
- Specialty: Nurse Practitioner (tier 1)
- State: NC (tier 1)
- Total loss cost: $15,000 (score 2)
- Frequency: 0.1 claims/FTE (score 1)
- Loss-free years: 5 (score 1)
- Limits: $1M/$3M (score 2)

**Computation**:
- Adequacy: (0.2×2 + 0.1×2 + 0.05×2 + 0.1×1 + ...) = 1.8 → score 2
- Capacity: (0.2×2 + 0.1×2 + 0.1×2) = 2.0 → score 2
- Appetite: (0.25×1 + 0.15×1 + ...) = 1.5 → score 1
- Environment: (regional factors) = 3.0 → score 3

**Composite**:
```
composite = (0.40×2 + 0.25×2 + 0.25×1 + 0.10×3) 
          = (0.80 + 0.50 + 0.25 + 0.30) 
          = 1.85 → ROUND = 2
```

**Triage**:
- Decision: AUTO-APPROVE (score 2, range 1-3)
- Reason: Excellent risk profile; no loss history; low-risk specialty
- Action: Issue policy immediately; no manual review needed
- Processing time: <1 minute

### 7.2 Example 2: Manual Review Case

**Scenario**: 55-year-old Cardiologist in Illinois with moderate loss history

**Input**:
- NPI: 2222222222
- Specialty: Cardiovascular Disease (tier 9)
- State: IL (tier 9)
- Total loss cost: $150,000 (score 7)
- Frequency: 0.8 claims/FTE (score 6)
- Loss-free years: 0 (score 8)
- Limits: $1M/$3M (score 5)

**Computation**:
- Adequacy: mixed high/low = 6.5 → score 6-7
- Capacity: moderate = 5.0 → score 5
- Appetite: specialty + state both high = 8.0 → score 8
- Environment: regional factors = 6.0 → score 6

**Composite**:
```
composite = (0.40×6.5 + 0.25×5.0 + 0.25×8.0 + 0.10×6.0)
          = (2.60 + 1.25 + 2.00 + 0.60)
          = 6.45 → ROUND = 6
```

**Triage**:
- Decision: MANUAL REVIEW (score 6, range 4-7)
- Reason: Moderate risk; high-risk specialty + high-risk state; loss history present
- Flags:
  - LOSS_HISTORY_CONCERN (adequacy 6.5 > 6)
  - SPECIALTY_CONCERN (Cardiology tier 9)
- Action: Queue to underwriter; review loss history detail, verify loss severity
- Processing time: 2-5 business days (underwriter review)

**Underwriter Review Checklist**:
- ✓ Verify 3 recent claims: dates, amounts, settlements
- ✓ Check if any claims are ongoing (open reserves)
- ✓ Confirm specialty classification (Cardiology vs. Interventional?)
- ✓ Review hospital affiliations; any restrictions?
- ✓ Check for any regulatory actions in IL
- Outcome: Possible approval with premium adjustment, or decline

### 7.3 Example 3: Auto-Decline Case

**Scenario**: 50-year-old Orthopedic Surgeon in New Mexico with severe loss history

**Input**:
- NPI: 3333333333
- Specialty: Orthopedic Surgery with spinal (tier 8)
- State: NM (tier 10)
- Total loss cost: $500,000 (score 10)
- Frequency: 2.5 claims/FTE (score 9)
- Loss-free years: 0 (score 10)
- Limits: $1M/$2M (score 4)

**Computation**:
- Adequacy: (0.2×10 + 0.1×10 + ...) mostly 9-10 = 9.5 → score 9
- Capacity: moderate = 5.0 → score 5
- Appetite: specialty high-risk + worst state = 9.5 → score 9
- Environment: worst decile = 8.0 → score 8

**Composite**:
```
composite = (0.40×9 + 0.25×5 + 0.25×9.5 + 0.10×8)
          = (3.60 + 1.25 + 2.38 + 0.80)
          = 8.03 → ROUND = 8
```

**Triage**:
- Decision: AUTO-DECLINE (score 8, range 8-10)
- Reason: High-risk profile; severe loss history; worst-in-class specialty + state combination
- Flags:
  - LOSS_HISTORY_CONCERN (adequacy 9)
  - SPECIALTY_CONCERN (Spinal Orthopedic Surgery, tier 8)
  - STATE_CONCERN (New Mexico, tier 10)
- Action: Refer to Medical Director for final review; likely decline
- Expected outcome: Policy declined or offered with severe restrictions

---

## 8. IMPLEMENTATION CHECKLIST

### 8.1 Pre-Deployment

#### ☐ Data Readiness
- Extract loss history data from claims system (5 years minimum)
- Validate loss cost calculations (trending, gross vs. net, coverage exclusions)
- Verify policy data: limits, coverage types, risk counts
- Obtain physician attributes: specialty, state, years since graduation, RVU data
- Obtain environmental data: income inequality, population density, crime, uninsured rate
- Map specialty descriptions to standard codes (use NPDB reference)

#### ☐ System Setup
- Create database (PostgreSQL recommended)
- Load reference tables: specialty_tiers, state_tiers, binning_thresholds
- Create core tables: physicians, physician_scores, sub_scores, audit_log
- Create indices for performance
- Set up backup/replication strategy

#### ☐ API Development
- Implement scoring logic in chosen language (Python/Node/Java)
- Build REST API endpoints (score, get-score, score-history)
- Implement authentication & logging
- Set up request/response validation
- Implement error handling & retry logic

#### ☐ Testing
- Unit tests: weighted_avg(), binning logic, credibility blending
- Integration tests: API → database writes
- Validation tests: verify scores match expected ranges (1-10)
- Manual walkthroughs: 3-5 real physician cases
- Load testing: Can API handle peak volume? (e.g., 100 scores/minute)
- Security testing: SQL injection, auth bypass, rate limiting

### 8.2 Pilot (Limited Rollout)

#### ☐ Controlled Rollout
- Select 50-100 test physicians from diverse specialties & states
- Score them and compare results to manual underwriter assessment
- Calculate agreement rate (target: >80% on triage category)
- Collect feedback from underwriters on score reasonableness

#### ☐ Monitor & Adjust
- Check distribution of scores (should span 1-10, not cluster at 5)
- Verify no data quality issues (missing inputs, out-of-range values)
- Monitor API latency (target: <200ms per request)
- Check for edge cases (e.g., physicians with no loss history)

#### ☐ Validation Against Historical Data
- Re-score 100 historical applications and compare to manual decisions
- Measure: precision, recall, F1 score for each triage category
- Identify systematic biases (does model over-penalize certain specialties?)
- Adjust weights if necessary

### 8.3 Full Deployment

#### ☐ Underwriter Training
- Conduct 2-3 training sessions on model logic, score interpretation
- Distribute quick-reference guide (1 page)
- Provide examples of auto-approve, manual review, auto-decline cases
- Q&A: address concerns about automation

#### ☐ Workflow Integration
- Wire API into underwriting application (front-end integration)
- Set up triage queues: auto-approve, manual-review, auto-decline
- Implement audit trail: log all scores, overrides, decisions
- Set up monitoring & alerting for API failures

#### ☐ Communication
- Notify applicants: explain scoring model to set expectations
- Prepare FAQ document
- Brief legal/compliance on model transparency & explainability

#### ☐ Go-Live
- Launch scoring for 100% of new applications
- Monitor for first 1 week: check for crashes, data issues, score outliers
- Track approval rate, manual review volume, processing time
- Conduct stand-ups: address issues, gather feedback

### 8.4 Post-Deployment (Ongoing)

#### ☐ Monitoring & Maintenance
- Track KPIs monthly:
  - Approval rate by specialty, state, score band
  - Manual review turnaround time
  - API uptime & latency
  - Score distribution (any unusual trends?)
- Audit scores quarterly: verify no data corruption
- Review weights annually: should they change based on experience?

#### ☐ Feedback Loop
- Collect underwriter feedback: does score match their judgment?
- Track outcomes: which auto-approves result in claims? Which declines regret?
- Adjust triage thresholds if needed (e.g., if score 6 has high claim rate, lower to manual-review)

#### ☐ Documentation
- Maintain runbook for API issues & troubleshooting
- Document any score exceptions or overrides (and reasons)
- Keep audit log of weight changes

### 8.5 Success Metrics

| Metric | Target | Definition |
|--------|--------|-----------|
| Processing Time (Auto-Approve) | < 1 day | Eliminate manual steps |
| Processing Time (Manual Review) | < 5 days | Reasonable turnaround |
| Approval Rate | 40-60% | Indicates good discrimination |
| Underwriter Satisfaction | 80%+ "reasonable" | Subjective validation |
| API Uptime | 99.5% | Production SLA |
| API Latency (p95) | < 200ms | User experience |
| Score Stability | Deterministic | Same input = same output |
| Claim Rate Validation | Approve < Review < Decline | Statistical validation |

---

## CONCLUSION

The PAS system provides a scalable, transparent, and auditable framework for physician risk scoring. By following this guide, you can integrate the model into your underwriting workflow with confidence, clear documentation, and built-in controls.

Key success factors:
1. **Clear separation of concerns**: API (stateless), database (persistent), UI (rules-driven)
2. **Full auditability**: All decisions traceable to input data
3. **Underwriter empowerment**: Auto-decisions for extremes, underwriter judgment for middle
4. **Continuous improvement**: Track outcomes, adjust thresholds, validate assumptions

Contact: [Your team contact]
Last Updated: July 28, 2026
