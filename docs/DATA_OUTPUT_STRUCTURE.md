# Data Output Directory Structure

## Primary Output Location

**All pipeline data files must be saved to**:
```
C:\Box\Box\BOX Subhashree Singh\Business\PAS\data
```

This is the centralized location for all PAS data outputs and is configured in:
- `config/pipeline_params.json` (base_output_dir)
- `config/monitoring_config.json` (reporting.output_directory)

---

## Directory Structure

```
C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\
│
├── input/                          # Input data files
│   ├── magmutual_scored_data.csv   # Step 1 development data
│   └── dhc_raw_data.csv            # Step 2 production data (all US physicians)
│
├── output/                         # Step 1 & 2 scored outputs
│   ├── step1_magmutual_scores_20260728.csv
│   ├── step2_dhc_scores_20260728.csv
│   ├── step2_batch_results_20260728.json
│   └── step2_performance_metrics_20260728.json
│
├── monitoring/                     # Step 2 & 3 monitoring reports
│   ├── batch_20260728_report.json
│   ├── psi_analysis_20260728.json
│   ├── distribution_analysis_20260728.html
│   ├── anomaly_report_20260728.json
│   └── health_check_20260728.json
│
├── logs/
│   └── pipeline/                   # Execution logs
│       ├── pipeline_20260728_0800.log
│       ├── api_service_20260728.log
│       └── batch_job_20260728.log
│
└── models/                         # (reference only, actual models in project)
    └── binning_v20260728/
        ├── thresholds.json
        └── metadata.json
```

---

## Step-by-Step Output Flow

### STEP 1: Score Development
**Input**: `data/input/magmutual_scored_data.csv`
**Output**: 
- `data/output/step1_magmutual_scores_20260728.csv`
- `data/models/binning_v20260728/` (bins created)
- `data/models/binning_v20260728/metadata.json`

### STEP 2A: Batch Scoring
**Input**: `data/input/dhc_raw_data.csv`
**Output**:
- `data/output/step2_dhc_scores_20260728.csv`
- `data/output/step2_batch_results_20260728.json`
- `data/monitoring/batch_20260728_report.json`
- `data/monitoring/psi_analysis_20260728.json`

### STEP 2B: API Scoring
**Input**: Real-time requests
**Output**: 
- `data/monitoring/health_check_20260728.json`
- `data/logs/pipeline/api_service_20260728.log`

### STEP 2C: Deployment Gates
**Input**: Scored data
**Output**:
- `data/monitoring/deployment_gates_20260728.json`
- `data/monitoring/anomaly_report_20260728.json`

### STEP 3: Continuous Monitoring
**Input**: Production scores
**Output**:
- `data/monitoring/daily_report_20260728.json`
- `data/monitoring/psi_trend_20260728.csv`
- `data/monitoring/distribution_analysis_20260728.html`
- `data/logs/pipeline/batch_job_20260728.log`

---

## File Naming Convention

All output files follow this naming pattern:

```
{pipeline_stage}_{cohort/batch}_{date}_{optional_time}.{extension}

Examples:
- step1_magmutual_scores_20260728.csv
- step2_dhc_scores_20260728.csv
- batch_20260728_report.json
- psi_analysis_20260728.json
- daily_report_20260728.json
- api_service_20260728.log
```

### Date Format
- **Date**: YYYYMMDD (e.g., 20260728 = July 28, 2026)
- **Time** (optional): HHMM (e.g., 0800 = 8:00 AM)

---

## Configuration Files

### pipeline_params.json
```json
{
  "data": {
    "base_output_dir": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data",
    "output_dir": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/output/",
    "monitoring_output": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/monitoring/",
    "logs_dir": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/logs/pipeline/"
  }
}
```

### monitoring_config.json
```json
{
  "reporting": {
    "output_directory": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/monitoring/"
  }
}
```

---

## Environment Setup

### Windows Path Format
Use forward slashes in JSON configs:
```
C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/output/
```

Python code will automatically handle conversion:
```python
import os
output_dir = "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/output/"
# Python converts to Windows format automatically
```

### Create Directories
If directories don't exist, create them:

```python
import os

output_dir = "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/output/"
os.makedirs(output_dir, exist_ok=True)
```

---

## Output File Types

### CSV Files
- **Step 1 Scores**: `step1_magmutual_scores_{date}.csv`
  - Columns: physician_id, composite_score, score_adequacy, score_capacity, score_appetite, score_environment, credibility_z_factor

- **Step 2 Scores**: `step2_dhc_scores_{date}.csv`
  - Same columns as Step 1 scores
  - 10K+ rows (all US physicians in batch)

### JSON Reports
- **Batch Results**: `step2_batch_results_{date}.json`
  ```json
  {
    "total_records": 10000,
    "successful": 10000,
    "failed": 0,
    "processing_time_ms": 245,
    "score_statistics": {...}
  }
  ```

- **PSI Analysis**: `psi_analysis_{date}.json`
  ```json
  {
    "psi_value": 0.08,
    "threshold": 0.25,
    "status": "OK",
    "interpretation": "No significant drift"
  }
  ```

- **Monitoring Report**: `batch_{date}_report.json`
  ```json
  {
    "report_date": "2026-07-28T10:00:00",
    "records_scored": 10000,
    "success_rate": 100.0,
    "score_statistics": {...},
    "psi_analysis": {...},
    "quality_checks": {...}
  }
  ```

### HTML Reports
- **Distribution Analysis**: `distribution_analysis_{date}.html`
  - Interactive charts and visualizations
  - Score distribution plots
  - Risk profile breakdown
  - Trend analysis

### Log Files
- **Pipeline Logs**: `pipeline_{date}_{time}.log`
- **API Service Logs**: `api_service_{date}.log`
- **Batch Job Logs**: `batch_job_{date}.log`

---

## Data Retention Policy

### Output Files
- **CSV scores**: Keep indefinitely (archive older than 1 year)
- **JSON reports**: Keep 90 days (configurable in monitoring_config.json)
- **HTML reports**: Keep 30 days
- **Log files**: Keep 30 days

### Models/Bins
- **Current bins**: Keep in production
- **Previous versions**: Archive in `models/binning_v{old_date}/`
- **Rollback capability**: Keep 2-3 recent versions

---

## Access & Permissions

### Folder Access
```
C:\Box\Box\BOX Subhashree Singh\Business\PAS\data
```

**Permissions Required**:
- Read: Load input files
- Write: Create output files and reports
- Delete: Archive old files

### Service Account
Configure with appropriate Box.com permissions for:
- Reading input files
- Writing output files
- Creating logs
- Monitoring reports

---

## Monitoring & Alerts

### Output File Size Monitoring
- **Input files**: Typically 100MB-1GB (depends on cohort size)
- **Output files**: ~100-500MB per batch run
- **Monitoring reports**: ~5-50MB per day
- **Logs**: ~10-100MB per day

### Alert Thresholds
- If output folder >10GB: Archive and compress old files
- If monitoring folder >5GB: Clean up reports older than 90 days
- If logs folder >2GB: Compress logs older than 30 days

---

## Integration with Pipeline Code

### Python Code Example
```python
import json
import os
from datetime import datetime

# Load configuration
with open('config/pipeline_params.json', 'r') as f:
    config = json.load(f)

# Get output directory
output_dir = config['data']['output_dir']
monitoring_dir = config['data']['monitoring_output']

# Create directories if needed
os.makedirs(output_dir, exist_ok=True)
os.makedirs(monitoring_dir, exist_ok=True)

# Generate filename with date
date_str = datetime.now().strftime('%Y%m%d')
output_file = os.path.join(output_dir, f'step2_dhc_scores_{date_str}.csv')

# Save scores
scores_df.to_csv(output_file, index=False)
print(f"Scores saved to: {output_file}")

# Save monitoring report
report_file = os.path.join(monitoring_dir, f'batch_{date_str}_report.json')
with open(report_file, 'w') as f:
    json.dump(monitoring_report, f, indent=2)
print(f"Report saved to: {report_file}")
```

---

## Troubleshooting

### Issue: "Permission denied" when writing to Box folder
**Solution**:
1. Verify folder access permissions
2. Check if Box sync is running
3. Ensure service account has write permissions
4. Try writing to local folder first, then sync

### Issue: "Path not found" error
**Solution**:
1. Create missing directories: `mkdir -p "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/{input,output,monitoring,logs}"`
2. Use forward slashes in JSON configs
3. Don't use relative paths; always use absolute paths

### Issue: Network timeout when accessing Box folder
**Solution**:
1. Verify network connection to Box
2. Check if Box sync is responsive
3. Implement retry logic with exponential backoff
4. Consider writing to local folder first, then uploading

---

## Backup & Disaster Recovery

### Critical Files to Backup
- `data/output/` - All scored data
- `data/monitoring/` - All reports and diagnostics
- `data/models/` - All bin configurations
- `config/` - Configuration files (version controlled)

### Backup Strategy
- Daily automated backups to secondary storage
- Weekly archive to long-term storage
- Monthly verification of backup integrity
- Disaster recovery test quarterly

---

## Documentation References

Related documents:
- `TECHNICAL_ROADMAP.xlsx` - Complete specification
- `PHASE_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `config/pipeline_params.json` - Pipeline configuration
- `config/monitoring_config.json` - Monitoring configuration

---

**Created**: 2026-07-28  
**Version**: 1.0.0  
**Last Updated**: 2026-07-28
