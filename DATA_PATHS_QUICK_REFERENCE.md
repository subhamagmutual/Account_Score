# Data Paths - Quick Reference

## 🎯 Primary Output Location

```
C:\Box\Box\BOX Subhashree Singh\Business\PAS\data
```

**All pipeline outputs go here** ✅

---

## 📁 Key Directories

| Directory | Purpose | Created By |
|-----------|---------|-----------|
| `data/input/` | Input data (MagMutual, DHC) | Manual upload |
| `data/output/` | Scored results | Step 1, 2A |
| `data/monitoring/` | Reports & diagnostics | Step 2A, 2C, 3 |
| `data/logs/pipeline/` | Execution logs | All steps |

---

## 📊 Sample Output Files

### Step 1 Output
```
data/output/step1_magmutual_scores_20260728.csv
```

### Step 2A Output
```
data/output/step2_dhc_scores_20260728.csv
data/monitoring/batch_20260728_report.json
data/monitoring/psi_analysis_20260728.json
```

### Step 2C Output
```
data/monitoring/deployment_gates_20260728.json
data/monitoring/anomaly_report_20260728.json
```

### Step 3 Output
```
data/monitoring/daily_report_20260728.json
data/monitoring/distribution_analysis_20260728.html
data/logs/pipeline/batch_job_20260728.log
```

---

## ⚙️ Configuration

**File**: `config/pipeline_params.json`

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

**File**: `config/monitoring_config.json`

```json
{
  "reporting": {
    "output_directory": "C:/Box/Box/BOX Subhashree Singh/Business/PAS/data/monitoring/"
  }
}
```

---

## 🔄 Data Flow

```
INPUT FILES
    ↓
data/input/magmutual_scored_data.csv (Step 1)
data/input/dhc_raw_data.csv (Step 2)
    ↓
PROCESSING
    ↓
OUTPUT FILES
    ↓
data/output/step1_magmutual_scores_YYYYMMDD.csv
data/output/step2_dhc_scores_YYYYMMDD.csv
    ↓
MONITORING REPORTS
    ↓
data/monitoring/batch_YYYYMMDD_report.json
data/monitoring/psi_analysis_YYYYMMDD.json
data/monitoring/distribution_analysis_YYYYMMDD.html
    ↓
LOGS
    ↓
data/logs/pipeline/pipeline_YYYYMMDD_HHMM.log
data/logs/pipeline/batch_job_YYYYMMDD.log
```

---

## ✅ Before Running Pipeline

1. ✅ Verify Box folder exists:
   ```
   C:\Box\Box\BOX Subhashree Singh\Business\PAS\data
   ```

2. ✅ Create subdirectories:
   ```
   mkdir "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\input"
   mkdir "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\output"
   mkdir "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\monitoring"
   mkdir "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\logs\pipeline"
   ```

3. ✅ Upload input files to:
   ```
   data/input/magmutual_scored_data.csv
   data/input/dhc_raw_data.csv
   ```

4. ✅ Verify configuration files point to correct paths

---

## 🚨 Important Notes

### Path Format
- ✅ Use forward slashes in JSON configs
- ✅ Use absolute paths (not relative)
- ❌ Don't use backslashes in JSON
- ❌ Don't use relative paths like `./data/`

### Box.com Sync
- Ensure Box Sync is running on your machine
- Verify network connectivity to Box
- Check folder permissions (read/write access)

### File Naming
All outputs follow this pattern:
```
{step}_{cohort}_{date}[_{time}].{extension}

Examples:
step1_magmutual_scores_20260728.csv
step2_dhc_scores_20260728.csv
batch_20260728_report.json
psi_analysis_20260728.json
pipeline_20260728_0800.log
```

---

## 📞 Troubleshooting

### Permission Denied
- Check folder permissions
- Verify Box Sync is running
- Ensure service account has write access

### Path Not Found
- Create missing directories
- Use absolute paths
- Use forward slashes in JSON

### Network Timeout
- Check Box connectivity
- Wait for Box Sync to complete
- Try local folder first

---

## 📋 Full Documentation

For complete details, see:
- `docs/DATA_OUTPUT_STRUCTURE.md` - Detailed directory structure
- `config/pipeline_params.json` - Pipeline configuration
- `config/monitoring_config.json` - Monitoring configuration

---

**Updated**: 2026-07-28
**Status**: All paths configured ✅
