"""Output builder: Assembles final scored DataFrame and exports to CSV/Excel.

Exports include:
- Full scored dataset
- Composite score distribution with embedded chart
- Component statistics
- Per-variable deployment tables with charts
- Breakdowns by specialty and state
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .deployment_tables import create_composite_deployment_table


def build_output_dataframe(
    df: pd.DataFrame,
    config: Dict[str, Any]
) -> pd.DataFrame:
    """
    Select and order the final output columns.

    Output includes:
    - Identifiers (NPI, policy, year, specialty, state)
    - Key KPIs
    - All sub-scores (1-30)
    - Component scores (Adequacy, Capacity, Appetite, Environment)
    - Composite score (1-10)
    - Credibility weight Z
    """
    identifiers = config.get("pipeline_params", {}).get("identifiers", {})

    id_cols = [v for v in identifiers.values() if v in df.columns]
    kpi_cols = sorted([c for c in df.columns if c.startswith("kpi_")])
    score_cols = sorted([c for c in df.columns if c.startswith("score_")])
    component_cols = ["adequacy_score", "capacity_score", "appetite_score", "environment_score"]
    component_cols = [c for c in component_cols if c in df.columns]
    composite_cols = ["composite_score_raw", "composite_score"]
    composite_cols = [c for c in composite_cols if c in df.columns]
    cred_cols = ["credibility_z"] if "credibility_z" in df.columns else []

    prem_col = "WRTN_PREM_AMT_ITD_BURNED"
    extra_cols = [prem_col] if prem_col in df.columns else []

    output_cols = id_cols + extra_cols + kpi_cols + score_cols + cred_cols + component_cols + composite_cols
    output_cols = [c for c in output_cols if c in df.columns]

    return df[output_cols].copy()


def export_to_csv(df: pd.DataFrame, output_path: str) -> str:
    """Export scored results to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Exported {len(df):,} records to CSV: {output_path}")
    return output_path


def export_to_excel(
    df: pd.DataFrame,
    output_path: str,
    config: Optional[Dict] = None,
    deployment_tables: Optional[Dict[str, pd.DataFrame]] = None
) -> str:
    """
    Export scored results to multi-sheet Excel workbook with charts.

    Sheets:
    - Scored_Data: Full scored dataset
    - Composite_Summary: Distribution with bar chart
    - Component_Stats: Statistical summary
    - By_Specialty / By_State: Score breakdowns
    - DT_* per-variable deployment tables with charts
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        # 1. Full scored data
        df.to_excel(writer, sheet_name="Scored_Data", index=False)

        # 2. Composite score distribution with chart
        composite_table = create_composite_deployment_table(df)
        if not composite_table.empty:
            composite_table.to_excel(writer, sheet_name="Composite_Summary", index=False)
            _add_bar_chart(writer, "Composite_Summary", composite_table,
                           value_col_idx=1, category_col_idx=0,
                           title="Composite Score Distribution",
                           x_label="Score", y_label="Policy Count")

        # 3. Component statistics
        component_cols = ["adequacy_score", "capacity_score", "appetite_score",
                         "environment_score", "composite_score_raw", "composite_score"]
        available = [c for c in component_cols if c in df.columns]
        if available:
            stats = df[available].describe().T
            stats.to_excel(writer, sheet_name="Component_Stats")

        # 4. Score by specialty
        identifiers = config.get("pipeline_params", {}).get("identifiers", {}) if config else {}
        specialty_col = identifiers.get("specialty")
        if specialty_col and specialty_col in df.columns and "composite_score" in df.columns:
            spec_summary = df.groupby(specialty_col).agg(
                count=("composite_score", "count"),
                mean_score=("composite_score", "mean"),
                median_score=("composite_score", "median")
            ).sort_values("mean_score").reset_index()
            spec_summary.to_excel(writer, sheet_name="By_Specialty", index=False)

        # 5. Score by state
        state_col = identifiers.get("state")
        if state_col and state_col in df.columns and "composite_score" in df.columns:
            state_summary = df.groupby(state_col).agg(
                count=("composite_score", "count"),
                mean_score=("composite_score", "mean"),
                median_score=("composite_score", "median")
            ).sort_values("mean_score").reset_index()
            state_summary.to_excel(writer, sheet_name="By_State", index=False)

        # 6. Per-variable deployment tables with charts
        if deployment_tables:
            for var_name, table in deployment_tables.items():
                if table.empty:
                    continue
                sheet_name = f"DT_{var_name}"[:31]
                table.to_excel(writer, sheet_name=sheet_name, index=False)
                _add_bar_chart(writer, sheet_name, table,
                               value_col_idx=3, category_col_idx=0,
                               title=f"{var_name} - Score Distribution",
                               x_label="Score", y_label="Policy Count")

    print(f"  Exported {len(df):,} records to Excel: {output_path}")
    return output_path


def _add_bar_chart(
    writer,
    sheet_name: str,
    table: pd.DataFrame,
    value_col_idx: int,
    category_col_idx: int,
    title: str,
    x_label: str,
    y_label: str
):
    """Add a column chart to an Excel sheet."""
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    max_row = len(table)

    chart = workbook.add_chart({"type": "column"})
    chart.add_series({
        "values": [sheet_name, 1, value_col_idx, max_row, value_col_idx],
        "categories": [sheet_name, 1, category_col_idx, max_row, category_col_idx],
        "fill": {"color": "#FFC000"},
        "name": "Count"
    })
    chart.set_x_axis({"name": x_label})
    chart.set_y_axis({"name": y_label, "major_gridlines": {"visible": True}})
    chart.set_legend({"position": "none"})
    chart.set_title({"name": title})

    max_col = len(table.columns)
    worksheet.insert_chart(1, max_col + 2, chart)
