# PAS SYSTEM - IMPLEMENTATION ROADMAP
## Snowflake + Python Deployment

**Status**: Analysis Complete → **Deployment Phase**  
**Timeline**: 4-6 weeks (depending on existing infrastructure)  
**Team**: Python developers, Snowflake admin, DevOps

---

## YOUR TECHNOLOGY STACK

```
┌─────────────────────────────────────────┐
│ Database: Snowflake                     │
│ API Language: Python (FastAPI)          │
│ Deployment: Native to Snowflake Cloud   │
└─────────────────────────────────────────┘
```

---

## WEEK-BY-WEEK PLAN

### **WEEK 1: Snowflake Setup**
- [ ] **Monday**: Create Snowflake database schema (SQL provided)
- [ ] **Tuesday**: Load reference tables (specialty_tiers, state_tiers, binning_thresholds)
- [ ] **Wednesday**: Set up Snowflake user/role/permissions
- [ ] **Thursday**: Test connectivity from local machine
- [ ] **Friday**: Validate data quality in Snowflake

**Deliverable**: Empty but ready Snowflake schema with reference data loaded

**Success Criteria**:
- Schema exists in Snowflake
- Can query specialty_tiers, state_tiers
- Reference data is correct

---

### **WEEK 2: Python API Development**
- [ ] **Monday**: Set up project structure, create requirements.txt
- [ ] **Tuesday**: Implement config.py and models.py
- [ ] **Wednesday**: Implement snowflake_connector.py (DB connections)
- [ ] **Thursday**: Implement scorer.py (scoring logic)
- [ ] **Friday**: Implement main.py (FastAPI endpoints)

**Deliverable**: Working API that scores physicians

**Success Criteria**:
- API starts without errors
- Can POST to `/api/v1/physicians/{npi}/score`
- Scores save to Snowflake
- Response includes all expected fields

---

### **WEEK 3: Testing & Validation**
- [ ] **Monday**: Unit tests (weighted_avg, scoring logic)
- [ ] **Tuesday**: Integration tests (API → Snowflake)
- [ ] **Wednesday**: Manual testing with 5-10 test cases
- [ ] **Thursday**: Performance testing (latency, throughput)
- [ ] **Friday**: Error handling & edge cases

**Deliverable**: Validated, tested API ready for pilot

**Success Criteria**:
- 90%+ test pass rate
- API latency < 200ms
- Handles invalid inputs gracefully
- Correct scores on all test cases

---

### **WEEK 4: Pilot (Limited Rollout)**
- [ ] **Monday**: Score 50-100 real physicians
- [ ] **Tuesday**: Compare results to manual underwriter assessments
- [ ] **Wednesday**: Gather feedback from underwriters
- [ ] **Thursday**: Identify issues, fix bugs
- [ ] **Friday**: Document findings, prepare for full deployment

**Deliverable**: Validated model, ready for production

**Success Criteria**:
- 80%+ agreement with underwriter judgment
- No critical bugs
- Underwriters confident in scores
- Processing time meets targets

---

### **WEEK 5: Production Deployment**
- [ ] **Monday**: Finalize deployment infrastructure (AWS, Azure, or on-prem)
- [ ] **Tuesday**: Set up monitoring, alerting, logging
- [ ] **Wednesday**: Underwriter training
- [ ] **Thursday**: Integration with underwriting system (UI)
- [ ] **Friday**: Go-live! 🚀

**Deliverable**: Production system scoring real applications

**Success Criteria**:
- API running 24/7
- Scores visible in underwriting system
- Triage queues populated correctly
- Team trained and confident

---

### **WEEK 6: Monitoring & Optimization**
- [ ] **Ongoing**: Track KPIs (uptime, latency, approval rates)
- [ ] **Ongoing**: Gather feedback from underwriters
- [ ] **Ongoing**: Fix any issues discovered in production

**Deliverable**: Stable, monitored production system

**Success Criteria**:
- 99.5%+ uptime
- < 200ms latency
- Clear triage routing
- Team satisfied

---

## DETAILED TASKS

### **PHASE 1: SNOWFLAKE SETUP** (1 week)

**Task 1.1: Create Schema**
```bash
# Time: 1 hour
# Copy-paste the SQL from Snowflake_Deployment_Plan.md Phase 1.1
# Run in Snowflake web UI or IDE
```

**Task 1.2: Load Reference Data**
```bash
# Time: 2-3 hours
# Get specialty_tiers.json, state_tiers.json from your uploaded files
# Run Python script to load into specialty_tiers, state_tiers tables
# Verify: SELECT COUNT(*) FROM specialty_tiers; # Should be ~25
```

**Task 1.3: Set Up Snowflake User**
```bash
# Time: 30 minutes
# Create app user with password
# Grant SELECT on reference tables
# Grant INSERT, UPDATE on score tables
# Test connection from local machine
```

**Task 1.4: Create .env File**
```bash
# Time: 15 minutes
# File: .env (keep secure, don't commit to git)
SNOWFLAKE_USER=app_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
```

---

### **PHASE 2: API IMPLEMENTATION** (1-2 weeks)

**Task 2.1: Project Setup**
```bash
# Time: 30 minutes
mkdir pas_api
cd pas_api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Task 2.2: Implement Modules**
- **config.py**: 30 min (just copy from guide)
- **models.py**: 30 min (Pydantic schemas)
- **snowflake_connector.py**: 2-3 hours (DB queries)
- **scorer.py**: 3-4 hours (scoring logic)
- **main.py**: 2-3 hours (API endpoints)

**Task 2.3: Test Locally**
```bash
# Time: 2 hours
# Start API: python main.py
# Test with curl/Postman
# Check Snowflake for saved scores
```

---

### **PHASE 3: TESTING** (1 week)

**Task 3.1: Unit Tests**
```python
# Test weighted_avg function
# Test component scoring
# Test binning logic
```

**Task 3.2: Integration Tests**
```python
# Test full API flow
# Verify scores save to Snowflake
# Check response format
```

**Task 3.3: Manual Validation**
```bash
# Pick 5-10 real physician cases
# Score them with API
# Compare results manually
# Document any discrepancies
```

**Task 3.4: Load Testing**
```bash
# Simulate 100 requests/minute
# Check latency and error rate
# Verify Snowflake can handle throughput
```

---

### **PHASE 4: DEPLOYMENT** (1-2 weeks)

**Task 4.1: Choose Deployment Option**

| Option | Best For | Setup Time |
|--------|----------|-----------|
| **AWS EC2** | Full control, scalable | 1-2 days |
| **Docker + ECS** | Containerized, cloud-agnostic | 2-3 days |
| **AWS Lambda** | Serverless, auto-scaling | 3-5 days |
| **Snowflake Native** | Simplest, native to platform | 2-3 days |

**Recommendation**: Start with **EC2 or native Snowflake** for simplicity.

**Task 4.2: Set Up Monitoring**
```
- CloudWatch (if AWS) or equivalent
- Track: uptime, latency, error rate
- Set up alerts for failures
```

**Task 4.3: Integrate with Underwriting System**
```
- Add API endpoint to underwriting app UI
- Display scores and triage category
- Route to appropriate queue
```

---

## QUICK START CHECKLIST

### Before You Start
- [ ] Snowflake account access
- [ ] Python 3.8+ installed
- [ ] Git (for version control)
- [ ] IDE (VS Code, PyCharm, etc.)

### Week 1 - Snowflake
- [ ] Snowflake schema created
- [ ] Reference data loaded
- [ ] Snowflake user created
- [ ] Local connection tested

### Week 2 - Python API
- [ ] Project structure set up
- [ ] All 5 Python modules implemented
- [ ] API starts and responds to requests
- [ ] Scores saved to Snowflake

### Week 3 - Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] 5-10 manual cases validated
- [ ] Performance meets targets

### Week 4 - Pilot
- [ ] 50-100 physicians scored
- [ ] Feedback from underwriters
- [ ] Issues documented and fixed
- [ ] Go-live approval obtained

### Week 5 - Production
- [ ] Deployment infrastructure ready
- [ ] Monitoring in place
- [ ] Team trained
- [ ] System live

---

## COMMON QUESTIONS

### Q: How long does each request take?
**A**: Expected: 50-200ms per score (binning lookup + Snowflake INSERT)

### Q: How much will this cost?
**A**: Snowflake costs depend on warehouse size/compute usage. API compute can be $200-500/month on AWS depending on volume.

### Q: What happens if the API goes down?
**A**: Underwriters fall back to manual review. No automatic approvals/declines are queued until API is back up.

### Q: Can I change the weights later?
**A**: Yes! Edit `config.py` and restart API. Scores are deterministic—same input always produces same score.

### Q: How do I handle physicians with missing data?
**A**: The model uses weight-zeroing. Missing components' weights redistribute to present ones. All calculations work with partial data.

---

## SUCCESS METRICS

After deployment, measure these KPIs:

```
✓ API Uptime:        99.5% (< 4 hours downtime/month)
✓ API Latency (p95): < 200ms
✓ Scores/day:        Track volume of scores computed
✓ Triage Split:      ~25% auto-approve, 50% manual, 25% auto-decline
✓ Underwriter Agree: 80%+ say scores are "reasonable"
✓ Processing Time:   < 1 day for auto-approve, < 5 days for manual review
```

---

## RESOURCES

1. **Snowflake Documentation**: https://docs.snowflake.com/
2. **FastAPI Tutorial**: https://fastapi.tiangolo.com/
3. **Snowflake Python Connector**: https://docs.snowflake.com/en/user-guide/python-connector.html
4. **PAS Deployment Guide**: `Snowflake_Deployment_Plan.md` (in your outputs folder)

---

## WHO SHOULD OWN WHAT

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Snowflake schema | Database Admin | Data Engineer |
| Python API | Backend Dev | Lead Developer |
| Monitoring/Alerts | DevOps | Infrastructure Lead |
| Underwriting Integration | Underwriting App Team | Business Analyst |
| Testing | QA / Developer | Project Manager |
| Documentation | Tech Lead | Project Lead |

---

## NEXT IMMEDIATE ACTION

**Go to `Snowflake_Deployment_Plan.md` and:**

1. **Review the SQL** in Phase 1.1
2. **Gather your Snowflake credentials** (account ID, warehouse, user)
3. **Identify your IT/Database team** to run the schema setup
4. **Have your Python team review** the code structure in Phases 2-3

**Then come back and let's start!** 🚀

