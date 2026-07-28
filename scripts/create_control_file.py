"""Generate the PAS-style Excel control file for Physician MPL Account Scoring.

This creates a single Excel workbook with 7 sheets that serves as an alternative
configuration source to the JSON files. Run once to generate, then edit the Excel
file to adjust parameters.

Usage:
    python create_control_file.py
"""

import pandas as pd
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "config" / "PAS_control_file.xlsx"


def create_variables_sheet():
    """Master variable registry with all 23 scoring variables."""
    rows = [
        # --- Adequacy (9 variables) ---
        {"LOB": "MPL", "Component": "Adequacy", "Variable": "total_loss_cost",
         "Type": "Ratio", "Numerator": "AMT_GROSS_RPTD_TOTAL_TRENDED",
         "Denominator": "BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED", "Multiplier": 1,
         "Weight": 0.20, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "indemnity_loss_cost",
         "Type": "Ratio", "Numerator": "AMT_GROSS_RPTD_IND_TRENDED",
         "Denominator": "BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED", "Multiplier": 1,
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "expense_loss_cost",
         "Type": "Ratio", "Numerator": "AMT_GROSS_RPTD_EXP_TRENDED",
         "Denominator": "BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED", "Multiplier": 1,
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "total_frequency",
         "Type": "Ratio", "Numerator": "CNT_GROSS_RPTD_TOTAL_GT_0",
         "Denominator": "FTE_EXPOSURE_CNT_GROSS_RPTD_TOTAL_GT_0_TRENDED_BURNED", "Multiplier": 1,
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "indemnity_frequency",
         "Type": "Ratio", "Numerator": "CNT_GROSS_RPTD_IND_GT_0",
         "Denominator": "FTE_EXPOSURE_CNT_GROSS_RPTD_IND_GT_0_TRENDED_BURNED", "Multiplier": 1,
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "total_severity",
         "Type": "Ratio", "Numerator": "ADJ_LOSS_FOR_SEVERITY",
         "Denominator": "CNT_GROSS_RPTD_TOTAL_GT_0", "Multiplier": 1,
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": True},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "actual_loss_ratio",
         "Type": "Ratio", "Numerator": "AMT_GROSS_RPTD_TOTAL_TRENDED",
         "Denominator": "WRTN_PREM_AMT_ITD_BURNED_CLASS_OL", "Multiplier": 1,
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": True, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "loss_free_years",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "CV_LOSS_FREE_YEARS",
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_RA",
         "Apply_Credibility": True, "Invert_Score": True, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Adequacy", "Variable": "limits_to_premium",
         "Type": "Ratio", "Numerator": "TOP_PER_M",
         "Denominator": "WRTN_PREM_AMT_ITD_BURNED", "Multiplier": 1000000,
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        # --- Capacity (3 variables) ---
        {"LOB": "MPL", "Component": "Capacity", "Variable": "per_occurrence_limit",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "TOP_PER_M",
         "Weight": 0.20, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Capacity", "Variable": "aggregate_limit",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "TOP_AGG_M",
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Capacity", "Variable": "risk_count",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "RISK_COUNT",
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        # --- Appetite (7 variables) ---
        {"LOB": "MPL", "Component": "Appetite", "Variable": "specialty_risk_tier",
         "Type": "Categorical", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "OL_RISK_SPECIALTY_DESC", "Lookup_Config": "specialty_tiers.json",
         "Weight": 0.25, "Bins": 10, "Binning_Method": "categorical",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "state_venue_risk",
         "Type": "Categorical", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "ST", "Lookup_Config": "state_tiers.json",
         "Weight": 0.15, "Bins": 10, "Binning_Method": "categorical",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "years_since_graduation",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "YEARS_SINCE_GRAD_IMPUTED",
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "rvu_ratio",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "RVU_WORK_TOTAL_RATIO_SPEC_OL",
         "Weight": 0.10, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "tenure_with_carrier",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "CV_YEARS_WITH_MAG",
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_RA",
         "Apply_Credibility": False, "Invert_Score": True, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "hospital_rating",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "HOSP_HOSPITALCOMPARE_OVERALLRATING",
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_RA",
         "Apply_Credibility": False, "Invert_Score": True, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Appetite", "Variable": "practice_size",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "WITH_WHOM_LOCATION_DISTINCT_NPI",
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        # --- Environment (4 variables) ---
        {"LOB": "MPL", "Component": "Environment", "Variable": "income_inequality",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "INCOME_RATIO",
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Environment", "Variable": "population_density",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "POP_DENSITY_SQ_MILES",
         "Weight": 0.05, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Environment", "Variable": "violent_crime_rate",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "VIOLENT_CRIME_RATE_PER_100K",
         "Weight": 0.03, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},

        {"LOB": "MPL", "Component": "Environment", "Variable": "pct_uninsured",
         "Type": "Direct", "Numerator": "", "Denominator": "", "Multiplier": 1,
         "Source_Column": "PCT_UNINSURED",
         "Weight": 0.02, "Bins": 10, "Binning_Method": "bin_All",
         "Apply_Credibility": False, "Invert_Score": False, "Only_When_Claims": False},
    ]

    df = pd.DataFrame(rows)
    df["Source_Column"] = df.get("Source_Column", "")
    df["Lookup_Config"] = df.get("Lookup_Config", "")
    df = df.fillna("")
    return df


def create_composite_weights_sheet():
    """Component-level weights for the final composite score."""
    return pd.DataFrame([
        {"Component": "Adequacy", "Weight": 0.40},
        {"Component": "Capacity", "Weight": 0.25},
        {"Component": "Appetite", "Weight": 0.25},
        {"Component": "Environment", "Weight": 0.10},
    ])


def create_credibility_sheet():
    """Credibility parameters for adequacy sub-score blending."""
    return pd.DataFrame([
        {"Parameter": "full_credibility_premium", "Value": 50000},
        {"Parameter": "complement_score", "Value": 5},
        {"Parameter": "premium_column", "Value": "WRTN_PREM_AMT_ITD_BURNED"},
    ])


def create_filters_sheet():
    """Data filtering parameters."""
    return pd.DataFrame([
        {"Parameter": "min_written_premium", "Value": "0", "Column": "WRTN_PREM_AMT_ITD_BURNED_CLASS_OL"},
        {"Parameter": "min_bce", "Value": "0", "Column": "BCE_ST"},
        {"Parameter": "coverage_year_min", "Value": "2017", "Column": "COVEFF_DATE"},
        {"Parameter": "coverage_year_max", "Value": "2023", "Column": "COVEFF_DATE"},
        {"Parameter": "policy_year_min", "Value": "2017", "Column": "POLEFF_DATE"},
    ])


def create_identifiers_sheet():
    """Record identifier columns."""
    return pd.DataFrame([
        {"Identifier": "physician_id", "Column": "NPI"},
        {"Identifier": "policy_number", "Column": "POL_NUM_ID"},
        {"Identifier": "coverage_year", "Column": "COVEFF_DATE"},
        {"Identifier": "specialty", "Column": "OL_RISK_SPECIALTY_DESC"},
        {"Identifier": "state", "Column": "ST"},
    ])


def create_data_paths_sheet():
    """Data paths for input/output."""
    return pd.DataFrame([
        {"Parameter": "input_path",
         "Value": "C:/Box/Box/BOX Subhashree Singh/Business/Modeling/data/regression/input/2025_refresh/modeling_data/2025_mr_dhc_merged_features.csv"},
        {"Parameter": "output_dir",
         "Value": "C:/Box/Box/BOX Subhashree Singh/Business/PAS"},
    ])


def create_scoring_params_sheet():
    """Scoring scale parameters."""
    return pd.DataFrame([
        {"Parameter": "sub_score_min", "Value": 1},
        {"Parameter": "sub_score_max", "Value": 10},
        {"Parameter": "composite_min", "Value": 1},
        {"Parameter": "composite_max", "Value": 10},
        {"Parameter": "portfolio_avg_band", "Value": 4.5},
        {"Parameter": "missing_value_sentinel", "Value": 0},
    ])


if __name__ == "__main__":
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        create_variables_sheet().to_excel(writer, sheet_name="Variables", index=False)
        create_composite_weights_sheet().to_excel(writer, sheet_name="Composite_Weights", index=False)
        create_credibility_sheet().to_excel(writer, sheet_name="Credibility", index=False)
        create_filters_sheet().to_excel(writer, sheet_name="Filters", index=False)
        create_identifiers_sheet().to_excel(writer, sheet_name="Identifiers", index=False)
        create_data_paths_sheet().to_excel(writer, sheet_name="Data_Paths", index=False)
        create_scoring_params_sheet().to_excel(writer, sheet_name="Scoring_Params", index=False)

    print(f"Control file created: {OUTPUT_PATH}")
