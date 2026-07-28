# PAS System Deployment Guide

## Complete Production Deployment Steps

---

## 📋 Pre-Deployment Checklist

### Code & Configuration
- [ ] All 3 STEP notebooks created and tested
- [ ] Configuration files updated with Box paths
- [ ] GitHub code committed and reviewed
- [ ] CI/CD pipeline configured
- [ ] Monitoring baselines established

### Infrastructure
- [ ] Box.com folders created (`PAS/data/input`, `output`, `monitoring`, `logs`)
- [ ] API service configured (port 8000)
- [ ] Database connections verified
- [ ] File storage quota verified (50GB+ available)
- [ ] Network connectivity tested

### Access & Permissions
- [ ] Service account created for batch jobs
- [ ] Database credentials configured
- [ ] Box.com read/write permissions granted
- [ ] Slack webhook configured
- [ ] Email notifications configured
- [ ] PagerDuty escalation configured

### Data
- [ ] MagMutual baseline data uploaded to `data/input/`
- [ ] DHC production data prepared in `data/input/`
- [ ] Step 1 bins created and validated
- [ ] Baseline metrics calculated and stored

### Team
- [ ] Ops team trained on alert response
- [ ] Data science team trained on diagnostics
- [ ] Incident response procedure documented
- [ ] On-call escalation verified
- [ ] Runbook created and shared

---

## 🚀 Phase 1: Development Validation (Week 1)

### Day 1: Run STEP 1 (Score Development)

```bash
# 1. Run notebook
jupyter notebook notebooks/STEP1_SCORE_DEVELOPMENT_TESTING.ipynb

# 2. Verify outputs
ls -la C:\Box\Box\BOX\ Subhashree\ Singh\Business\PAS\data\output\

# 3. Validate results
# - Composite scores generated: ✓
# - Bins created: ✓
# - Configuration saved: ✓
```

**Success Criteria**:
- ✅ 500+ physicians scored
- ✅ All 4 component scores present
- ✅ Scores in range [1.0, 10.0]
- ✅ Bins saved to models/binning_v{date}/

### Day 2: Run STEP 2 (Production Scoring)

```bash
# 1. Batch Scoring
jupyter notebook notebooks/STEP2A_BATCH_SCORING_TESTING.ipynb

# 2. API Service
python -m src.account_score.api.server
# In another terminal:
jupyter notebook notebooks/STEP2B_API_SCORING_TESTING.ipynb

# 3. Deployment Gates
jupyter notebook notebooks/STEP2C_DEPLOYMENT_GATES_TESTING.ipynb
```

**Success Criteria**:
- ✅ 10,000+ physicians scored
- ✅ PSI < 0.25 (no significant drift)
- ✅ API latency < 100ms
- ✅ All 5 deployment gates pass (exit code 0)

### Day 3-7: Run STEP 3 (Production Monitoring)

```bash
# 1. Continuous Monitoring
jupyter notebook notebooks/STEP3A_CONTINUOUS_MONITORING_TESTING.ipynb

# 2. Alerts & Escalation
jupyter notebook notebooks/STEP3B_ALERTS_AND_ESCALATION_TESTING.ipynb

# 3. Batch Job Scheduling
jupyter notebook notebooks/STEP3C_BATCH_JOB_SCHEDULING_TESTING.ipynb
```

**Success Criteria**:
- ✅ Monitoring dashboard generates correctly
- ✅ Alert rules trigger appropriately
- ✅ Batch jobs execute successfully
- ✅ Reports saved to monitoring folder
- ✅ Alerts escalate to correct channels

---

## 🔧 Phase 2: Infrastructure Deployment (Week 2)

### Step 1: Deploy API Service

```bash
# 1. Create systemd service file
sudo tee /etc/systemd/system/pas-api.service > /dev/null <<EOF
[Unit]
Description=PAS API Service
After=network.target

[Service]
Type=notify
User=pas_service
WorkingDirectory=/opt/pas
ExecStart=/usr/bin/python3 -m src.account_score.api.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 2. Enable and start service
sudo systemctl enable pas-api
sudo systemctl start pas-api

# 3. Verify service status
sudo systemctl status pas-api
```

### Step 2: Configure Batch Jobs

```bash
# 1. Create cron jobs directory
mkdir -p /opt/pas/jobs

# 2. Create daily batch job script
cat > /opt/pas/jobs/daily_batch.sh <<'EOF'
#!/bin/bash
date >> /var/log/pas/batch.log
python3 /opt/pas/run_daily_batch.py >> /var/log/pas/batch.log 2>&1
EOF

chmod +x /opt/pas/jobs/daily_batch.sh

# 3. Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/pas/jobs/daily_batch.sh") | crontab -
(crontab -l 2>/dev/null; echo "0 6 * * * /opt/pas/jobs/daily_monitoring.sh") | crontab -
(crontab -l 2>/dev/null; echo "0 3 * * 1 /opt/pas/jobs/weekly_diagnostics.sh") | crontab -
```

### Step 3: Set Up Monitoring

```bash
# 1. Configure monitoring dashboard (Grafana/DataDog)
# - Connect to monitoring folder: data/monitoring/
# - Import daily_report JSON
# - Create PSI alert at threshold 0.25
# - Create distribution shift alert at 5%

# 2. Configure alert channels
# - Slack: Add PAS app to #data-science, #devops
# - Email: Configure sendmail/SMTP
# - PagerDuty: Create escalation policy

# 3. Set up log aggregation
# - Configure fluentd/logstash
# - Point to data/logs/pipeline/
```

---

## ✅ Phase 3: Production Cutover (Week 3)

### Day 1: Blue-Green Deployment

```bash
# 1. Deploy to BLUE environment (staging)
./deploy.sh blue

# 2. Run smoke tests
./smoke_tests.sh blue
# - Single score latency < 100ms
# - Batch scoring 100 records < 2s
# - Health check passes
# - Monitoring dashboard updates

# 3. Run full validation
./validate.sh blue
# - API returns correct scores
# - Batch results match STEP 2
# - Deployments gates pass
# - Alerts trigger correctly
```

### Day 2-5: Canary Deployment

```bash
# 1. Route 5% traffic to BLUE
# - Monitor error rates, latency
# - Check alert system
# - Verify PSI stays < 0.25

# 2. If successful, gradually increase to 25%, 50%, 100%
# - Monitor metrics at each step
# - Watch for any anomalies
# - Be ready to rollback immediately

# 3. Final validation
# - Run full test suite
# - Verify all reports generated
# - Check database consistency
```

### Day 6: Production Rollout

```bash
# 1. Final health checks
./health_check.sh production

# 2. Enable GREEN (production)
./deploy.sh green

# 3. Monitor production metrics
# - API throughput: > 100 req/sec
# - Error rate: < 0.1%
# - Latency p95: < 200ms
# - PSI: < 0.25
```

---

## 🔄 Phase 4: Post-Deployment (Ongoing)

### Daily Operations

```bash
# 1. Morning check (08:00 AM)
./health_check.sh production
./check_reports.sh production

# 2. Monitor dashboard
# - Review PSI from previous day
# - Check for any alerts
# - Review batch job logs

# 3. Weekly diagnostics (Monday morning)
./diagnostics.sh production
# - Compare to baseline
# - Check for data drift
# - Review performance trends
```

### Incident Response

**If PSI > 0.25 (BLOCKER)**:
1. Alert team immediately (Slack + Email + PagerDuty)
2. Investigate source of drift
3. Check data quality
4. Consider rollback
5. Document incident

**If Null Rate > 5% (BLOCKER)**:
1. Stop batch jobs
2. Investigate data source
3. Fix data pipeline
4. Resume scoring

**If API Latency > 200ms (WARNING)**:
1. Check server load
2. Review recent changes
3. Scale API if needed
4. Monitor for recovery

---

## 🔙 Rollback Procedures

### Quick Rollback (< 5 minutes)

```bash
# 1. Stop current version
systemctl stop pas-api

# 2. Switch to previous version
./switch_version.sh previous

# 3. Start old version
systemctl start pas-api

# 4. Verify functionality
./smoke_tests.sh production
```

### Full Rollback (< 30 minutes)

```bash
# 1. Notify team
echo "Rolling back to version 1.0.0" | mail ops@magmutual.com

# 2. Revert database changes
./revert_database.sh version=1.0.0

# 3. Revert configuration
git checkout config/ --version=1.0.0

# 4. Restart all services
systemctl restart pas-api
systemctl restart batch-jobs

# 5. Run validation
./validate.sh production
```

---

## 📊 Health Check Procedures

### Hourly

```bash
# Check API health
curl -s http://localhost:8000/health | jq .

# Check recent batch jobs
ls -lt data/logs/pipeline/*.log | head -3

# Check PSI (last 24h)
tail -10 data/monitoring/*.json | grep psi
```

### Daily

```bash
# Full monitoring dashboard
./health_check.sh production

# Review yesterday's reports
ls -la data/output/daily_scores_*.csv

# Check alert logs
tail -100 data/logs/alerts.log
```

### Weekly

```bash
# Run comprehensive diagnostics
./diagnostics.sh production

# Compare to baseline
python -c "import analysis; analysis.compare_to_baseline()"

# Review trends
./generate_trend_report.sh week
```

---

## 📞 Runbook

### Alert: PSI > 0.25
1. Check monitoring dashboard
2. Review last 24h of scores
3. Compare DHC distribution to MagMutual
4. Investigate root cause
5. Contact data science team
6. Consider model retraining

### Alert: Data Quality
1. Check input data source
2. Verify pipeline status
3. Check null rates by column
4. Fix pipeline if needed
5. Resume scoring
6. Validate output

### Incident: API Down
1. Check systemd status: `systemctl status pas-api`
2. Review error logs: `journalctl -u pas-api -50`
3. Restart service: `systemctl restart pas-api`
4. If restart fails, rollback
5. Notify team
6. Post-mortem after recovery

---

## 🎓 Training Materials

### For Operations Team
- Alert response playbook
- Health check procedures
- Incident response guide
- Escalation matrix

### For Data Science Team
- Monitoring dashboard walkthrough
- How to interpret PSI
- How to debug distribution shifts
- Model retraining procedure

### For All Teams
- System architecture diagram
- Data flow overview
- Contact list and escalation
- Business impact of failures

---

## ✨ Success Metrics

### Availability
- ✅ 99.9% uptime
- ✅ < 1 incident per month
- ✅ < 5 minute MTTR

### Performance
- ✅ API latency < 100ms p50
- ✅ Batch throughput > 300 scores/sec
- ✅ Error rate < 0.1%

### Data Quality
- ✅ Null rate < 5%
- ✅ PSI < 0.25
- ✅ Score distribution stable
- ✅ Gini > 0.15

### Operations
- ✅ All daily reports generated
- ✅ All alerts escalate correctly
- ✅ All batch jobs complete
- ✅ Zero production incidents

---

**Document created**: 2026-07-28  
**Last updated**: 2026-07-28  
**Version**: 1.0.0
