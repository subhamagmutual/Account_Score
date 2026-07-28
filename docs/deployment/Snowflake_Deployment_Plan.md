# PRODUCTION DEPLOYMENT PLAN
## PAS Scoring System on Snowflake + Python

**Database**: Snowflake  
**Language**: Python  
**Framework**: Snowpark + FastAPI (or Flask)  
**Deployment**: Snowflake Native or AWS/Azure with Snowflake SDK  

---

## ARCHITECTURE OPTIONS

### **OPTION A: Snowpark + Snowflake Native App (Recommended for Simplicity)**

```
┌─────────────────────────────────────────────────────────┐
│                   SNOWFLAKE CLOUD                       │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │     Snowflake Native App / Streamlit UI         │   │
│  │     (or external REST API calling Snowpark)     │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │                                   │
│  ┌──────────────────▼──────────────────────────────┐   │
│  │     Snowpark Session (Python UDF)               │   │
│  │     - Load config, compute scores               │   │
│  │     - Call SQL procedures                       │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │                                   │
│  ┌──────────────────▼──────────────────────────────┐   │
│  │     Snowflake Database                          │   │
│  │     - physicians table                          │   │
│  │     - physician_scores table                    │   │
│  │     - sub_scores table (detail)                 │   │
│  │     - Reference tables (tiers, binning)         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Pros**: 
- Everything in Snowflake (simple, integrated)
- No external server management
- Easy to scale with Snowflake
- Native audit trail

**Cons**:
- Limited to Snowflake ecosystem
- Snowpark can be slower than native compute

---

### **OPTION B: FastAPI + Snowflake Connector (Recommended for Flexibility)**

```
┌──────────────────────────┐
│   Underwriting App       │
│   (calls REST API)       │
└────────────┬─────────────┘
             │
┌────────────▼──────────────────────────┐
│   FastAPI Server (Python)              │
│   - POST /physicians/{npi}/score       │
│   - GET /physicians/{npi}/latest-score │
│   - Error handling, auth, logging      │
└────────────┬──────────────────────────┘
             │
┌────────────▼──────────────────────────┐
│   Snowflake Connector (Python SDK)     │
│   - Connect to Snowflake               │
│   - Query reference data (cached)      │
│   - Write scores + audit trail         │
└────────────┬──────────────────────────┘
             │
┌────────────▼──────────────────────────┐
│   Snowflake Database                   │
│   - All tables and data                │
└───────────────────────────────────────┘
```

**Pros**:
- Full control over API behavior
- Can run anywhere (AWS, Azure, on-prem)
- Easier to integrate with other systems
- Standard REST API

**Cons**:
- Need to manage API server
- Additional infrastructure

---

## RECOMMENDED APPROACH: OPTION B (FastAPI + Snowflake Connector)

**Why**: 
- Most flexible for enterprise integration
- Easy to add features (monitoring, rate limiting, auth)
- Team already knows Python
- Can deploy on any infrastructure

---

## PHASE 1: SNOWFLAKE SETUP

### 1.1 Create Database Schema

```sql
-- Connect to your Snowflake account
-- Use ACCOUNTADMIN or appropriate role

-- Create database
CREATE DATABASE IF NOT EXISTS PAS;
USE DATABASE PAS;

-- Create schema
CREATE SCHEMA IF NOT EXISTS SCORING;
USE SCHEMA SCORING;

-- Create physicians table
CREATE TABLE IF NOT EXISTS physicians (
  npi BIGINT PRIMARY KEY,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  specialty VARCHAR(255),
  state CHAR(2),
  years_since_graduation INT,
  npi_record_updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Create physician_scores table (main results)
CREATE TABLE IF NOT EXISTS physician_scores (
  score_id VARCHAR(36) PRIMARY KEY DEFAULT UUID_STRING(),
  npi BIGINT NOT NULL REFERENCES physicians(npi),
  
  -- Component scores (1-10)
  adequacy_score NUMERIC(3,1),
  capacity_score NUMERIC(3,1),
  appetite_score NUMERIC(3,1),
  environment_score NUMERIC(3,1),
  
  -- Composite
  composite_score_raw NUMERIC(4,3),
  composite_score INT,
  
  -- Triage decision
  triage_category VARCHAR(50),  -- 'auto_approve', 'manual_review', 'auto_decline'
  
  -- Metadata
  scored_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  application_id VARCHAR(100),
  scored_by_system VARCHAR(100),
  
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE INDEX IF NOT EXISTS idx_physician_scores_npi ON physician_scores(npi);
CREATE INDEX IF NOT EXISTS idx_physician_scores_created ON physician_scores(created_at);
CREATE INDEX IF NOT EXISTS idx_physician_scores_triage ON physician_scores(triage_category);

-- Create sub_scores table (audit detail)
CREATE TABLE IF NOT EXISTS sub_scores (
  sub_score_id VARCHAR(36) PRIMARY KEY DEFAULT UUID_STRING(),
  score_id VARCHAR(36) NOT NULL,
  npi BIGINT NOT NULL,
  
  variable_name VARCHAR(100),
  variable_value NUMERIC(3,1),
  component VARCHAR(50),
  raw_data VARIANT,  -- JSON in Snowflake
  
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  
  FOREIGN KEY (score_id) REFERENCES physician_scores(score_id)
);

CREATE INDEX IF NOT EXISTS idx_sub_scores_score_id ON sub_scores(score_id);
CREATE INDEX IF NOT EXISTS idx_sub_scores_npi ON sub_scores(npi);

-- Create reference tables
CREATE TABLE IF NOT EXISTS specialty_tiers (
  tier_id INT AUTOINCREMENT,
  specialty_description VARCHAR(500) UNIQUE,
  tier_score INT,
  tier_label VARCHAR(100),
  loss_ratio_avg NUMERIC(5,3),
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (tier_id)
);

CREATE TABLE IF NOT EXISTS state_tiers (
  tier_id INT AUTOINCREMENT,
  state_code CHAR(2) UNIQUE,
  tier_score INT,
  tier_label VARCHAR(100),
  tort_environment VARCHAR(100),
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (tier_id)
);

CREATE TABLE IF NOT EXISTS binning_thresholds (
  threshold_id INT AUTOINCREMENT,
  variable_name VARCHAR(255),
  bin_number INT,
  lower_bound NUMERIC(12,2),
  upper_bound NUMERIC(12,2),
  score_1_to_10 INT,
  method VARCHAR(100),
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (threshold_id)
);

-- Audit table
CREATE TABLE IF NOT EXISTS score_audit_log (
  audit_id VARCHAR(36) PRIMARY KEY DEFAULT UUID_STRING(),
  score_id VARCHAR(36),
  npi BIGINT,
  action VARCHAR(100),
  old_score INT,
  new_score INT,
  reason VARCHAR(1000),
  modified_by VARCHAR(100),
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Grant permissions (update roles as needed)
GRANT USAGE ON DATABASE PAS TO ROLE SYSADMIN;
GRANT USAGE ON SCHEMA PAS.SCORING TO ROLE SYSADMIN;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA PAS.SCORING TO ROLE SYSADMIN;
```

### 1.2 Load Reference Data

```python
# Load specialty_tiers.json, state_tiers.json into Snowflake

import json
import snowflake.connector

conn = snowflake.connector.connect(
    user='YOUR_USER',
    password='YOUR_PASSWORD',
    account='YOUR_ACCOUNT_ID',
    warehouse='YOUR_WAREHOUSE',
    database='PAS',
    schema='SCORING'
)

cursor = conn.cursor()

# Load specialty tiers
with open('specialty_tiers.json', 'r') as f:
    specialty_data = json.load(f)

for specialty, tier_score in specialty_data['tiers'].items():
    cursor.execute("""
        INSERT INTO specialty_tiers (specialty_description, tier_score, tier_label)
        VALUES (%s, %s, %s)
    """, (specialty, tier_score, specialty_data['tier_labels'][str(tier_score)]))

conn.commit()
cursor.close()
conn.close()
```

---

## PHASE 2: PYTHON API IMPLEMENTATION

### 2.1 Project Structure

```
pas_api/
├── main.py                 # FastAPI app
├── config.py               # Configuration (weights, thresholds)
├── snowflake_connector.py  # Snowflake connection & queries
├── scorer.py               # Scoring logic
├── models.py               # Pydantic models (request/response)
├── requirements.txt        # Dependencies
└── .env                    # Environment variables (DB credentials)
```

### 2.2 requirements.txt

```
fastapi==0.104.1
uvicorn==0.24.0
snowflake-connector-python==3.5.0
snowflake-sqlalchemy==1.5.1
pydantic==2.5.0
pandas==2.1.3
numpy==1.26.2
python-dotenv==1.0.0
```

### 2.3 config.py - Load Weights & Thresholds

```python
# config.py
import json
from typing import Dict

class ScoringConfig:
    def __init__(self):
        # Composite weights
        self.composite_weights = {
            'adequacy': 0.40,
            'capacity': 0.25,
            'appetite': 0.25,
            'environment': 0.10
        }
        
        # Variable weights
        self.adequacy_vars = {
            'total_loss_cost': 0.20,
            'indemnity_loss_cost': 0.10,
            'expense_loss_cost': 0.05,
            'total_frequency': 0.10,
            'indemnity_frequency': 0.05,
            'total_severity': 0.05,
            'actual_loss_ratio': 0.10,
            'loss_free_years': 0.10,
            'limits_to_premium': 0.10,
        }
        
        self.capacity_vars = {
            'per_occurrence_limit': 0.20,
            'aggregate_limit': 0.10,
            'risk_count': 0.10,
        }
        
        self.appetite_vars = {
            'specialty_risk_tier': 0.25,
            'state_venue_risk': 0.15,
            'years_since_graduation': 0.10,
            'rvu_ratio': 0.10,
            'tenure_with_carrier': 0.05,
            'hospital_rating': 0.05,
            'practice_size': 0.05,
        }
        
        self.environment_vars = {
            'income_inequality': 0.05,
            'population_density': 0.05,
            'violent_crime_rate': 0.03,
            'pct_uninsured': 0.02,
        }

config = ScoringConfig()
```

### 2.4 snowflake_connector.py - Database Connection

```python
# snowflake_connector.py
import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv()

class SnowflakeDB:
    def __init__(self):
        self.conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database='PAS',
            schema='SCORING'
        )
        self.cursor = self.conn.cursor()
    
    def get_specialty_tier(self, specialty: str) -> int:
        """Get specialty tier from database"""
        self.cursor.execute(
            "SELECT tier_score FROM specialty_tiers WHERE specialty_description = %s",
            (specialty,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 5  # Default to 5
    
    def get_state_tier(self, state: str) -> int:
        """Get state tier from database"""
        self.cursor.execute(
            "SELECT tier_score FROM state_tiers WHERE state_code = %s",
            (state,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 5  # Default to 5
    
    def get_binning_score(self, variable_name: str, value: float) -> int:
        """Get binned score for a continuous variable"""
        self.cursor.execute(f"""
            SELECT score_1_to_10 FROM binning_thresholds
            WHERE variable_name = %s
            AND lower_bound <= %s AND upper_bound > %s
            LIMIT 1
        """, (variable_name, value, value))
        result = self.cursor.fetchone()
        return result[0] if result else 5  # Default to 5
    
    def save_score(self, npi: int, components: dict, composite: dict, 
                   application_id: str, sub_scores: dict):
        """Save score and audit trail to database"""
        
        # Insert physician_scores
        score_id = self.cursor.execute("""
            INSERT INTO physician_scores 
            (npi, adequacy_score, capacity_score, appetite_score, environment_score,
             composite_score_raw, composite_score, triage_category, application_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING score_id
        """, (
            npi,
            components['adequacy'],
            components['capacity'],
            components['appetite'],
            components['environment'],
            composite['raw'],
            composite['final'],
            composite['triage'],
            application_id
        )).fetchone()[0]
        
        # Insert sub_scores
        for var_name, var_score in sub_scores.items():
            self.cursor.execute("""
                INSERT INTO sub_scores (score_id, npi, variable_name, variable_value)
                VALUES (%s, %s, %s, %s)
            """, (score_id, npi, var_name, var_score))
        
        self.conn.commit()
        return score_id
    
    def close(self):
        self.cursor.close()
        self.conn.close()
```

### 2.5 scorer.py - Scoring Logic

```python
# scorer.py
import numpy as np
import pandas as pd
from config import config
from snowflake_connector import SnowflakeDB

class ScoreCalculator:
    def __init__(self):
        self.db = SnowflakeDB()
        self.config = config
    
    def weighted_avg(self, values: dict, weights: dict) -> float:
        """Weighted average with weight-zeroing for missing values"""
        total_weighted = 0.0
        total_active_weight = 0.0
        
        for key, value in values.items():
            if key in weights and pd.notna(value):
                w = weights[key]
                total_weighted += value * w
                total_active_weight += w
        
        if total_active_weight == 0:
            return np.nan
        
        return total_weighted / total_active_weight
    
    def score_physician(self, physician_data: dict) -> dict:
        """
        Main scoring function.
        
        Args:
            physician_data: {
                'npi': int,
                'specialty': str,
                'state': str,
                'loss_data': {...},
                'coverage_data': {...},
                'premium': float,
                'application_id': str
            }
        
        Returns:
            {
                'npi': int,
                'components': {'adequacy': float, ...},
                'composite_raw': float,
                'composite': int,
                'triage': str,
                'sub_scores': {...}
            }
        """
        
        npi = physician_data['npi']
        premium = physician_data.get('premium', 0)
        application_id = physician_data.get('application_id', '')
        
        # Step 1: Normalize all variables to 1-10 scale
        sub_scores = {}
        
        # Adequacy variables
        for var_name, var_weight in self.config.adequacy_vars.items():
            if var_name in physician_data.get('loss_data', {}):
                raw_value = physician_data['loss_data'][var_name]
                binned_score = self.db.get_binning_score(var_name, raw_value)
                sub_scores[var_name] = binned_score
            else:
                sub_scores[var_name] = np.nan
        
        # Capacity variables
        for var_name, var_weight in self.config.capacity_vars.items():
            if var_name in physician_data.get('coverage_data', {}):
                raw_value = physician_data['coverage_data'][var_name]
                binned_score = self.db.get_binning_score(var_name, raw_value)
                sub_scores[var_name] = binned_score
            else:
                sub_scores[var_name] = np.nan
        
        # Appetite variables (categorical lookups)
        sub_scores['specialty_risk_tier'] = self.db.get_specialty_tier(
            physician_data.get('specialty', 'Unknown')
        )
        sub_scores['state_venue_risk'] = self.db.get_state_tier(
            physician_data.get('state', 'XX')
        )
        
        for var_name in ['years_since_graduation', 'rvu_ratio', 'tenure_with_carrier', 
                        'hospital_rating', 'practice_size']:
            if var_name in physician_data.get('physician_attributes', {}):
                raw_value = physician_data['physician_attributes'][var_name]
                binned_score = self.db.get_binning_score(var_name, raw_value)
                sub_scores[var_name] = binned_score
            else:
                sub_scores[var_name] = np.nan
        
        # Environment variables
        for var_name in ['income_inequality', 'population_density', 'violent_crime_rate', 'pct_uninsured']:
            if var_name in physician_data.get('environmental_data', {}):
                raw_value = physician_data['environmental_data'][var_name]
                binned_score = self.db.get_binning_score(var_name, raw_value)
                sub_scores[var_name] = binned_score
            else:
                sub_scores[var_name] = np.nan
        
        # Step 2: Apply credibility blending (Adequacy only)
        z = min(np.sqrt(premium / 50000), 1.0)
        adequacy_raw = self.weighted_avg(
            {k: sub_scores[k] for k in self.config.adequacy_vars.keys()},
            self.config.adequacy_vars
        )
        adequacy_score = z * adequacy_raw + (1 - z) * 5.0
        
        # Step 3: Compute component scores
        capacity_score = self.weighted_avg(
            {k: sub_scores[k] for k in self.config.capacity_vars.keys()},
            self.config.capacity_vars
        )
        
        appetite_score = self.weighted_avg(
            {k: sub_scores[k] for k in self.config.appetite_vars.keys()},
            self.config.appetite_vars
        )
        
        environment_score = self.weighted_avg(
            {k: sub_scores[k] for k in self.config.environment_vars.keys()},
            self.config.environment_vars
        )
        
        # Step 4: Compute composite
        components = {
            'adequacy': adequacy_score,
            'capacity': capacity_score,
            'appetite': appetite_score,
            'environment': environment_score
        }
        
        composite_raw = self.weighted_avg(components, self.config.composite_weights)
        composite_final = int(np.round(np.clip(composite_raw, 1, 10)))
        
        # Step 5: Determine triage
        if composite_final <= 3:
            triage = 'auto_approve'
        elif composite_final <= 7:
            triage = 'manual_review'
        else:
            triage = 'auto_decline'
        
        # Step 6: Save to database
        self.db.save_score(npi, components, 
                          {'raw': composite_raw, 'final': composite_final, 'triage': triage},
                          application_id, sub_scores)
        
        return {
            'npi': npi,
            'components': components,
            'composite_raw': composite_raw,
            'composite': composite_final,
            'triage': triage,
            'sub_scores': sub_scores
        }
```

### 2.6 models.py - Request/Response Schemas

```python
# models.py
from pydantic import BaseModel
from typing import Optional, Dict

class LossData(BaseModel):
    total_loss_cost_per_bce: float
    indemnity_loss_cost_per_bce: Optional[float] = None
    expense_loss_cost_per_bce: Optional[float] = None
    total_frequency_per_fte: float
    indemnity_frequency_per_fte: Optional[float] = None
    total_severity: Optional[float] = None
    actual_loss_ratio: float
    loss_free_years: int

class CoverageData(BaseModel):
    per_occurrence_limit_millions: float
    aggregate_limit_millions: float
    risk_count: int = 1

class PhysicianAttributes(BaseModel):
    years_since_graduation: int
    rvu_ratio: Optional[float] = None
    tenure_with_carrier_years: Optional[int] = None
    hospital_rating: Optional[int] = None
    practice_size: Optional[int] = None

class EnvironmentalData(BaseModel):
    income_ratio: Optional[float] = None
    population_density: Optional[float] = None
    violent_crime_rate: Optional[float] = None
    pct_uninsured: Optional[float] = None

class ScoreRequest(BaseModel):
    npi: int
    specialty: str
    state: str
    loss_data: LossData
    coverage_data: CoverageData
    physician_attributes: PhysicianAttributes
    environmental_data: Optional[EnvironmentalData] = None
    premium_for_credibility: float
    application_id: str

class ComponentScores(BaseModel):
    adequacy: float
    capacity: float
    appetite: float
    environment: float

class TriageDecision(BaseModel):
    category: str
    reason: str

class ScoreResponse(BaseModel):
    npi: int
    score_id: str
    components: ComponentScores
    composite_score_raw: float
    composite_score: int
    triage_decision: TriageDecision
    scoring_timestamp: str
    model_version: str = "PAS-v1.0"
```

### 2.7 main.py - FastAPI Application

```python
# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

from models import ScoreRequest, ScoreResponse, TriageDecision, ComponentScores
from scorer import ScoreCalculator

app = FastAPI(
    title="PAS Scoring API",
    description="Physician Adequacy Scoring System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scorer
calculator = ScoreCalculator()

@app.post("/api/v1/physicians/{npi}/score", response_model=ScoreResponse)
async def score_physician(npi: int, request: ScoreRequest):
    """
    Score a physician application in real-time.
    """
    try:
        # Prepare physician data
        physician_data = {
            'npi': npi,
            'specialty': request.specialty,
            'state': request.state,
            'loss_data': request.loss_data.dict(),
            'coverage_data': request.coverage_data.dict(),
            'physician_attributes': request.physician_attributes.dict(),
            'environmental_data': request.environmental_data.dict() if request.environmental_data else {},
            'premium': request.premium_for_credibility,
            'application_id': request.application_id
        }
        
        # Score
        result = calculator.score_physician(physician_data)
        
        # Format response
        reason_map = {
            'auto_approve': 'Low risk profile - score 1-3',
            'manual_review': 'Medium risk - requires underwriter review',
            'auto_decline': 'High risk - refer to senior underwriter'
        }
        
        return ScoreResponse(
            npi=npi,
            score_id=str(uuid.uuid4()),
            components=ComponentScores(**result['components']),
            composite_score_raw=result['composite_raw'],
            composite_score=result['composite'],
            triage_decision=TriageDecision(
                category=result['triage'],
                reason=reason_map[result['triage']]
            ),
            scoring_timestamp=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

@app.get("/api/v1/physicians/{npi}/latest-score")
async def get_latest_score(npi: int):
    """Get the most recent score for a physician"""
    # Query Snowflake for latest score
    # Implementation details...
    pass

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## PHASE 3: DEPLOYMENT OPTIONS

### Option 1: Run on AWS EC2 / Compute Instance

```bash
# 1. Create .env file with Snowflake credentials
cat > .env << EOF
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account_id
SNOWFLAKE_WAREHOUSE=your_warehouse
EOF

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run API
python main.py

# Or use Gunicorn for production
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

### Option 2: Docker + Any Cloud Platform

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build & run
docker build -t pas-api:latest .
docker run -p 8000:8000 --env-file .env pas-api:latest
```

### Option 3: AWS Lambda + API Gateway (Serverless)

Use Snowflake's Lambda integration or serverless compute tier.

---

## PHASE 4: TESTING CHECKLIST

- [ ] Unit tests for `weighted_avg()`, `score_physician()`
- [ ] Integration tests: API → Snowflake writes
- [ ] Validation tests: scores within 1-10 range
- [ ] Manual walkthroughs with 5 real cases
- [ ] Load testing: 100 scores/minute
- [ ] Security: auth, SQL injection prevention, rate limiting
- [ ] Error handling: invalid inputs, missing data, DB connection issues

---

## PHASE 5: MONITORING & OPERATIONS

### Key Metrics to Track

```
- API uptime (target: 99.5%)
- API latency (p95: < 200ms)
- Scores per day
- Score distribution (should span 1-10)
- Triage category distribution (expect ~25% auto-approve, ~50% manual, ~25% auto-decline)
- Error rate (should be < 1%)
```

### Sample Snowflake Queries for Monitoring

```sql
-- Score distribution today
SELECT 
  composite_score,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM physician_scores
WHERE DATE(scored_at) = CURRENT_DATE()
GROUP BY composite_score
ORDER BY composite_score;

-- Triage category breakdown
SELECT 
  triage_category,
  COUNT(*) as count
FROM physician_scores
WHERE DATE(scored_at) = CURRENT_DATE()
GROUP BY triage_category;

-- API performance
SELECT 
  AVG(TIMESTAMPDIFF(second, scored_at, created_at)) as avg_latency_sec,
  MAX(TIMESTAMPDIFF(second, scored_at, created_at)) as max_latency_sec
FROM physician_scores
WHERE DATE(scored_at) = CURRENT_DATE();
```

---

## NEXT STEPS (IN ORDER)

1. **Set up Snowflake schema** (run SQL from Phase 1)
2. **Load reference data** (specialty/state tiers, binning thresholds)
3. **Implement Python API** (Phases 2 & 3)
4. **Test locally** with mock Snowflake data
5. **Deploy to staging** and validate
6. **Run pilot** with 50-100 real cases
7. **Full production deployment**
8. **Monitor & iterate**

---

## QUESTIONS TO ANSWER BEFORE STARTING

- Which Snowflake region/cloud?
- What are your DB credentials?
- Do you have existing deployment infrastructure (AWS, Azure, GCP)?
- What auth method for the API (API key, OAuth, IP whitelist)?
- Who owns the API (IT, Data, Underwriting)?
- Monitoring/alerting tool (DataDog, New Relic, Splunk)?

