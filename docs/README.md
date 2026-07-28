# PAS Documentation

This directory contains all technical documentation for the Physician Account Score (PAS) system.

## Quick Links

### Getting Started
- [API Reference](api/API_REFERENCE.md) - Complete API documentation with examples
- [Deployment Checklist](deployment/DEPLOYMENT_CHECKLIST.md) - Production deployment guide

### Data Governance
- [Data Dictionary](data-governance/DATA_DICTIONARY.md) - Description of all 23 KPI variables
- [Data Lineage](data-governance/DATA_LINEAGE.md) - Data flow through the pipeline

## Directory Structure

```
docs/
├── api/                          API reference and function documentation
│   └── API_REFERENCE.md
├── deployment/                   Production deployment and runbooks
│   └── DEPLOYMENT_CHECKLIST.md
└── data-governance/              Data quality, governance, and lineage
    ├── DATA_DICTIONARY.md        Variable definitions
    └── DATA_LINEAGE.md           Data flow and transformations
```

## Key Sections

### 1. API Reference
Start here to understand how to use the PAS pipeline. Includes:
- Main pipeline functions
- Scoring functions
- Validation functions
- Analysis functions

### 2. Deployment Checklist
Complete guide for deploying PAS to production, including:
- Pre-deployment validation
- Test procedures
- Production cutover steps
- Monitoring and rollback procedures

### 3. Data Dictionary
Detailed description of all 23 KPI variables organized by scoring component:
- **Adequacy** (9 variables) - Loss coverage metrics
- **Capacity** (3 variables) - Premium capacity
- **Appetite** (7 variables) - Practice profile metrics
- **Environment** (4 variables) - Regional/specialty factors

### 4. Data Lineage
Documents the complete data flow:
- Input data validation
- KPI calculations
- Binning transformations
- Scoring logic
- Output formats

## Key Concepts

### Scoring Components (4)
1. **Adequacy** (40% weight) - Does this physician have adequate reserves?
2. **Capacity** (25% weight) - Can this physician afford appropriate insurance?
3. **Appetite** (25% weight) - Is this a desirable risk?
4. **Environment** (10% weight) - How favorable is the practice environment?

### Binning Methods (6)
- Quantile - Equal frequency across all data
- Equal Width - Equal-sized ranges
- Log Scale - For skewed distributions
- U-Shaped - For bimodal data (extremes are bad)
- Mean-Anchored - Portfolio-relative scoring
- Reciprocal - For inverted metrics

### Score Ranges
- **Sub-scores (individual KPIs)**: 1-30 scale
- **Component scores**: 1-10 scale
- **Composite score**: 1-10 scale (integer)
- **Credibility Z-factor**: 0-1 scale (weighting multiplier)

## Configuration Files

Located in `config/`:
- `pipeline_params.json` - Pipeline execution parameters
- `scoring_weights.json` - Component and sub-score weights
- `specialty_tiers.json` - Risk tiers by medical specialty
- `state_tiers.json` - Risk tiers by state

## Running the Pipeline

```bash
# Full pipeline (fit + score)
python run_pipeline.py --mode fit_and_score

# Fit only
python run_pipeline.py --mode fit_only

# Score only (using existing binning)
python run_pipeline.py --mode score_only

# Test with sample
python run_pipeline.py --sample 10000
```

## Troubleshooting

- See DEPLOYMENT_CHECKLIST.md for common issues
- Check logs in `logs/` directory for detailed diagnostics
- Review DATA_DICTIONARY.md if uncertain about variable definitions

## Contact

- **Technical Issues**: See deployment checklist for team contacts
- **Data Questions**: Refer to Data Dictionary and Data Lineage docs
- **Configuration Changes**: Requires actuarial review and approval

---

**Last Updated:** July 28, 2026  
**Version:** 1.0
