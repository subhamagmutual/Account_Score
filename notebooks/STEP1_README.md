# STEP 1: Score Development & Validation Testing Notebook

**File**: `STEP1_SCORE_DEVELOPMENT_TESTING.ipynb`

This notebook provides a comprehensive walkthrough of the complete Step 1 workflow for developing physician account scores using MagMutual data.

---

## 📋 What This Notebook Covers

### Test 1: Data Loading
- Load MagMutual physician data from CSV
- Load 3rd party data sources (demographics, credentials, etc.)
- Explore data structure and basic statistics
- **Status**: Ready to use with your actual MagMutual data

### Test 2: KPI Calculation
- Calculate **23 KPI variables** from raw data
- KPIs include:
  - Volume metrics (annual claims, specialty volume)
  - Experience metrics (years in specialty, board certification)
  - Risk metrics (loss frequency, complication rate)
  - Quality metrics (facility rating, compliance score)
  - Peer comparison metrics (volume ratio, loss ratio)
- **Output**: 23 engineered features ready for binning

### Test 3: Credibility Weighting
- Calculate data quality/completeness scores
- Assign credibility z-factors
- Weight physicians based on data reliability
- **Output**: Credibility scores for each physician

### Test 4: Binning (⭐ THE CRITICAL STEP)
- **Create binning thresholds for all 23 KPI variables**
- Binning strategies:
  - Equal Frequency (quintiles - 20% each)
  - Equal Width (equal intervals)
  - Percentile-based (custom)
- **Output**: Bin thresholds saved to `models/binning_v{date}/`
- **Key Point**: These bins are REUSED by Step 2 inference code!

### Test 5: Apply Binning
- Convert continuous KPI variables to binned scores
- Normalize to 0-1 range for consistent scoring
- **Output**: Binned KPI values ready for component scores

### Test 6: Scoring
- Calculate **4 component scores**:
  - Adequacy (40% weight)
  - Capacity (25% weight)
  - Appetite (25% weight)
  - Environment (10% weight)
- Calculate **composite score** (weighted average, 1-10 scale)
- **Output**: Composite scores for all physicians

### Test 7: Input Validation
- Validate required columns present
- Check data types
- Monitor null values (<5% allowed)
- Detect and report duplicates
- **Output**: Validation report with pass/fail status

### Test 8: Output Validation
- Verify scores are in valid range [1.0, 10.0]
- Check for null scores
- Analyze score distribution
- Detect constant values
- **Output**: Score quality report

### Test 9: Configuration Management
- Create configuration dictionary with:
  - Scoring weights (40/25/25/10)
  - Bin thresholds for all 23 variables
  - Baseline statistics (mean, median, std, percentiles)
  - Metadata (version, creation date, cohort)
- **Output**: Configuration ready to save to JSON files

### Test 10: Complete Pipeline
- End-to-end execution of all steps
- Summarize outputs and metrics
- Verify all validations passed
- **Output**: Complete pipeline confirmation

### Test 11: Risk Profile Analysis
- Categorize physicians into risk levels:
  - **Low Risk**: Scores 1-4 (good candidates)
  - **Medium Risk**: Scores 4-7 (monitor)
  - **High Risk**: Scores 7-10 (elevated attention)
- Visualize distribution
- **Output**: Risk category counts and percentages

### Test 12: Summary Report
- Final summary of entire Step 1 process
- Confirmation of all outputs
- Next steps for Step 2 & 3
- **Output**: Complete summary report

---

## 🚀 How to Use This Notebook

### 1. **Prepare Your Data**
```python
# Replace the sample data generator with your actual MagMutual data
magmutual_data = pd.read_csv('your_magmutual_data.csv')
```

### 2. **Run the Notebook Top-to-Bottom**
- Start with Test 1 (Data Loading)
- Progress through each test sequentially
- Each test builds on previous outputs

### 3. **Expected Outputs**
After running all tests, you'll have:
- ✅ Composite scores for all physicians (1-10 scale)
- ✅ 4 component scores (adequacy, capacity, appetite, environment)
- ✅ Binning configuration (quintile thresholds for 23 variables)
- ✅ Credibility/confidence scores
- ✅ Validation reports (input and output)
- ✅ Configuration files ready to save
- ✅ Risk profiles for all physicians

### 4. **Save Your Results**
```python
# Save composite scores
binned_data[['physician_id', 'composite_score', 'score_adequacy', 'score_capacity', 'score_appetite', 'score_environment']].to_csv('magmutual_scores.csv', index=False)

# Save bin thresholds (would be saved in Step 1)
with open('models/binning_v20260728/thresholds.json', 'w') as f:
    json.dump(bin_thresholds, f, indent=2)

# Save configuration
with open('config/scoring_weights.json', 'w') as f:
    json.dump(config['scoring_weights'], f, indent=2)
```

---

## 📊 Key Metrics to Monitor

### Score Distribution
- **Mean**: Target ~5.5 (middle of 1-10 scale)
- **Std Dev**: Target 1.5-2.0 (good variance)
- **Range**: All physicians should be [1.0, 10.0]

### Component Scores
Should have similar distributions:
- **Adequacy**: Mean ~5.5
- **Capacity**: Mean ~5.5
- **Appetite**: Mean ~5.5
- **Environment**: Mean ~5.5

### Risk Distribution
Typically balanced:
- **Low Risk (1-4)**: 20-30% of population
- **Medium Risk (4-7)**: 50-60% of population
- **High Risk (7-10)**: 10-20% of population

### Data Quality
- **Null values**: <5% in required columns
- **Duplicates**: None
- **Data types**: All correct

---

## ⚠️ Critical Steps

### Step 4: Binning
This is the **MOST CRITICAL** step because:
- Bins define how KPI variables are discretized
- Bins are **REUSED** in Step 2 (DHC application)
- Same bins ensure **consistent scoring** across populations
- PSI (Population Stability Index) in Step 3 compares distributions using these bins

**If bins don't fit DHC data well (high PSI):**
1. Option A: Recalibrate bins on DHC data
2. Option B: Use DHC-specific stratification

### Step 6: Scoring
- Component weights MUST sum to 1.0 (40+25+25+10 = 100%)
- Composite score = Σ(component_score × weight)
- All scores must be in [1.0, 10.0] range

### Test 8-9: Validation
- Both input AND output must pass validation
- Failing validation blocks deployment (in Step 3)

---

## 📈 Next Steps

After completing Step 1:

1. **Review scores** for face validity
2. **Validate discrimination** (correlation to loss outcomes)
3. **Calculate Gini coefficient** for discrimination power
4. **Approve configuration** for production use

Then proceed to:
- **Step 2**: Apply bins to DHC data (all US physicians)
- **Step 3**: Set up monitoring and production pipeline

---

## 🔗 Related Documentation

- **TECHNICAL_ROADMAP.xlsx**: Complete technical specification
- **TECHNICAL_ROADMAP_README.md**: Detailed explanation
- **PHASE_IMPLEMENTATION_SUMMARY.md**: Full implementation details
- **PHASE1_PHASE2_TESTING.ipynb**: Tests for monitoring (Phase 1) and API (Phase 2)
- **PHASE3_TESTING.ipynb**: Tests for analytics (Phase 3)

---

## 💡 Tips

1. **Start with small sample**: Test with 100-500 physicians before full dataset
2. **Verify bin thresholds**: Check if bins make business sense
3. **Validate correlations**: Check if scores correlate to loss outcomes
4. **Save everything**: Keep configurations for reproducibility
5. **Document changes**: Track any adjustments to weights or bins

---

## ❓ Common Issues

### Issue: Scores all fall in narrow range
**Solution**: Check KPI distributions; may need log transformation or scaling

### Issue: High null rates in specific column
**Solution**: May be missing in data source; consider dropping or imputing

### Issue: Binning fails with error
**Solution**: Check for NaN values in KPI column before binning

### Issue: Scores don't correlate to loss
**Solution**: May need different weights or additional features

---

**Created**: 2026-07-28
**Status**: Ready for use
**Last Updated**: 2026-07-28
