# Data Directory Location

## External Data Storage

The `data/` folder is stored externally in Box to keep the git repository clean and avoid large file issues.

**Location:** `C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\`

**Subdirectories:**
- `data/input/` - Raw input files (CSV, etc.)
- `data/output/` - Pipeline outputs and reports
- `data/processed/` - Intermediate processed datasets

## Configuration

The pipeline expects data in the Box location. Update `config/pipeline_params.json` if needed:

```json
{
  "data": {
    "input_file": "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\input\your_file.csv"
  }
}
```

## Running Pipeline

```bash
python run_pipeline.py --input "C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\input\data.csv"
```

Or modify `config/pipeline_params.json` to set default paths.
