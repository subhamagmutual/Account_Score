# PAS Production Deployment Checklist

## Pre-Deployment Phase (Week 1-2)

### Configuration Validation

- [ ] All config files (pipeline_params.json, scoring_weights.json, etc.) present in `config/` directory
- [ ] Config validation passes: `python -m src.account_score.config_validator`
  - [ ] Composite weights sum to 1.0
  - [ ] All dimensions have sub-scores
  - [ ] Credibility parameters reasonable
  - [ ] Binning methods valid
- [ ] Specialty tiers configured for all 25+ specialties
- [ ] State tiers configured for all 38+ states
- [ ] Identifiers mapped correctly (NPI, specialty, state, year)
- [ ] Default scores set for unknown specialties/states

### Data Preparation

- [ ] Input data file location confirmed and accessible
- [ ] Input data has all required columns:
  - [ ] Identifier columns (NPI, COVEFF_DATE, specialty, state)
  - [ ] Loss/indemnity columns
  - [ ] Premium column
  - [ ] Exposure columns (years of experience, etc.)
- [ ] Input data quality validated: `python -c "from src.account_score.input_validator import validate_input_data; ..."`
  - [ ] No missing identifier columns
  - [ ] No excessive nulls (>50%) in key columns
  - [ ] No negative values in cost/premium metrics
  - [ ] Outliers identified and reviewed
- [ ] Sample data (10,000 records) prepared for testing

### Code Quality & Testing

- [ ] All unit tests passing: `pytest tests/ -v --cov=src.account_score`
  - [ ] test_binner.py: 100% pass
  - [ ] test_scorer.py: 100% pass
  - [ ] test_validators.py: 100% pass
  - [ ] Code coverage >=70%
- [ ] No critical errors in linting/type checking
- [ ] Logging configured and tested
  - [ ] Console logging working
  - [ ] File logging to `./logs/` directory
  - [ ] Log levels (INFO, WARNING, ERROR) functioning

### Configuration Review

- [ ] Technical team reviewed all Python code
- [ ] Actuarial team reviewed and approved:
  - [ ] Component definitions and sub-scores
  - [ ] Composite weights (40/25/25/10)
  - [ ] Binning method selection
  - [ ] Credibility weighting parameters
  - [ ] Specialty and state tier mappings
- [ ] Weights and parameters signed off by chief actuary
- [ ] Backup of current (staging) config created

### Test Run #1: Sample Data (10,000 records)

- [ ] Sample test completed: `python run_pipeline.py --sample 10000`
- [ ] Output files generated:
  - [ ] `physician_scores_YYYYMMDD_HHMMSS.csv`
  - [ ] `physician_scores_YYYYMMDD_HHMMSS.xlsx`
- [ ] Data lineage report reviewed:
  - [ ] No unexpected record loss at any step
  - [ ] All major steps complete with reasonable output counts
- [ ] Score distribution validated:
  - [ ] Mean approximately 5-6
  - [ ] Standard deviation 1.5-2.5
  - [ ] No clustering at extremes (>20% at score 1 or 10)
  - [ ] All scores in range [1, 10]
- [ ] Component scores reasonable:
  - [ ] All in range [1, 10]
  - [ ] Distributions similar to composite
- [ ] Spot-check on 10-20 records:
  - [ ] Specialty and state mappings correct
  - [ ] Credibility weighting applied (Z-factor 0-1)
  - [ ] Final composite score is integer 1-10

### Documentation & Knowledge Transfer

- [ ] API documentation reviewed: `docs/api/API_REFERENCE.md`
- [ ] Deployment checklist explained to ops team: `docs/deployment/DEPLOYMENT_CHECKLIST.md`
- [ ] Error handling and troubleshooting documented
- [ ] Runbooks created for common operations:
  - [ ] How to run fit_and_score
  - [ ] How to run score_only with new data
  - [ ] How to generate presentation
  - [ ] How to troubleshoot common errors
- [ ] Team trained on:
  - [ ] Config parameter meanings
  - [ ] Log interpretation
  - [ ] Output file formats
  - [ ] Common issues and fixes

---

## Deployment Phase (Day 1)

### Pre-Flight Checks (Morning)

- [ ] Database/data access confirmed
- [ ] Output directories created and tested for write access
- [ ] Logging directory created: `./logs/`
- [ ] Backup of any existing output files
- [ ] Config files backed up to version control

### Dry Run on Full Dataset

- [ ] Full pipeline run executed (no sampling): `python run_pipeline.py --mode fit_and_score`
  - [ ] Expected runtime: ~15-30 minutes for 3.8GB input
  - [ ] Monitor memory usage (target <16GB)
  - [ ] Check log file for warnings
- [ ] Pipeline completed successfully
- [ ] Output files generated and accessible:
  - [ ] CSV file with all physicians and scores
  - [ ] Excel file with multiple sheets
  - [ ] Binning thresholds saved: `config/binning_thresholds.json`

### Output Validation

- [ ] CSV file opened and spot-checked:
  - [ ] All expected columns present
  - [ ] Composite scores in range [1, 10]
  - [ ] Credibility Z-factors in range [0, 1]
  - [ ] Sample records match expected profiles
- [ ] Excel file sheets verified:
  - [ ] Scores sheet: All physicians scored
  - [ ] Score_Distribution sheet: Frequency table complete
  - [ ] Component_Stats sheet: Summary by component
  - [ ] By_Specialty sheet: Average scores by specialty
  - [ ] By_State sheet: Average scores by state
- [ ] Data lineage report generated and reviewed
- [ ] Score distribution report generated:
  - [ ] Mean, std, median within expected ranges
  - [ ] Distribution looks reasonable (not bimodal/multimodal)

### Comparison with Baseline (if applicable)

- [ ] Results compared to previous scoring version:
  - [ ] Mean composite score similar (within ±0.5)
  - [ ] Component scores correlated
  - [ ] Specialty rankings make sense
  - [ ] State rankings make sense
- [ ] Any significant differences documented and understood
- [ ] Actuarial team signs off on differences

### Production Cutover

- [ ] Backup of previous binning_thresholds.json (if exists)
- [ ] Config files moved to production location:
  - [ ] `pipeline_params.json`
  - [ ] `scoring_weights.json`
  - [ ] `specialty_tiers.json`
  - [ ] `state_tiers.json`
  - [ ] `binning_thresholds.json` (generated from fit)
- [ ] Output files moved to production location (if separate from staging)
- [ ] Access controls verified (read/write permissions)

---

## Post-Deployment Phase (Days 2-5)

### Monitoring & Validation

- [ ] Daily log review for errors/warnings:
  - [ ] No critical errors in pipeline
  - [ ] Data quality warnings monitored
  - [ ] Performance metrics logged
- [ ] Spot-check of recent output:
  - [ ] 10 random physicians reviewed
  - [ ] Scores make sense given their profiles
  - [ ] Specialty and state mappings correct
- [ ] System performance monitored:
  - [ ] Memory usage acceptable
  - [ ] Runtime stable
  - [ ] Disk space sufficient

### Stakeholder Communication

- [ ] Results presented to underwriting team:
  - [ ] High-risk physicians identified
  - [ ] Score distribution explained
  - [ ] How to interpret individual PAS cards
- [ ] System demo in underwriting workflow
- [ ] Feedback collected from users
- [ ] Any issues or concerns logged and addressed

### Documentation Updates

- [ ] Post-deployment runbook created
- [ ] Known issues documented
- [ ] Performance baseline established (runtime, memory)
- [ ] Troubleshooting guide updated with real issues encountered

---

## Ongoing Operations

### Regular Monitoring

- [ ] Daily: Log file review for errors
- [ ] Weekly: Data quality metrics check
- [ ] Monthly:
  - [ ] Score distribution analysis
  - [ ] Performance trending
  - [ ] Config change audit (if any)

### Maintenance Tasks

- [ ] Archive old log files (keep 3+ months)
- [ ] Archive old output files (keep 6+ months)
- [ ] Update documentation as needed
- [ ] Version control commits for all changes

### Change Management

- [ ] Weight changes require:
  - [ ] Actuarial review and approval
  - [ ] Testing on sample data
  - [ ] Comparison to previous results
  - [ ] Stakeholder communication
  - [ ] Version increment
- [ ] Config changes tracked in git
- [ ] Binning thresholds re-fit if:
  - [ ] Population characteristics change significantly
  - [ ] New data source added
  - [ ] Policy annual review occurs

### Sensitivity Testing (Quarterly)

- [ ] Test impact of ±5% weight changes
- [ ] Test impact of ±$10k credibility threshold change
- [ ] Document impact metrics
- [ ] Present results to actuarial team

---

## Rollback Plan

If critical issues discovered:

### Immediate Actions (Rollback)

1. Stop production pipeline runs
2. Revert config files to previous known-good version:
   ```bash
   git checkout HEAD~1 -- config/
   ```
3. Re-run pipeline with previous config
4. Verify output acceptable
5. Communication to stakeholders

### Investigation & Resolution

1. Root cause analysis documented
2. Fix applied and tested
3. Unit tests added for regression
4. Code review before re-deployment
5. Stakeholder approval before production

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Chief Actuary** | | | |
| **VP Underwriting** | | | |
| **Director of Pricing** | | | |
| **Director of IT/Operations** | | | |
| **Project Manager** | | | |

---

## Success Criteria

### Launch is successful when:

✅ All configuration validation passes  
✅ All unit tests passing (≥70% coverage)  
✅ Sample data test run completes successfully  
✅ Full dataset test run completes successfully  
✅ Score distribution validated and reasonable  
✅ Actuarial team approves results  
✅ Underwriting team trained and confident  
✅ Logs and monitoring configured  
✅ Rollback plan documented  
✅ Sign-offs obtained from all stakeholders  

---

## Contact Information

- **Technical Support:** [Ops Team Email]
- **Actuarial Questions:** [Actuarial Lead Email]
- **On-Call Contact:** [Phone/Slack]
- **Escalation:** [VP Contact]

---

**Created:** July 2026  
**Version:** 1.0  
**Last Updated:** July 28, 2026
