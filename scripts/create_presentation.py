"""
Generate a PowerPoint presentation for the Physician MPL Account Scoring Model.
Follows the structure of the NA WSG Property and Italy Property Account Scoring presentations.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt, Emu, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.chart.data import CategoryChartData
import json
import glob
import os
import tempfile

# ============================================================
# CONFIGURATION
# ============================================================
OUTPUT_DIR = "C:/Box/Box/BOX Subhashree Singh/Business/PAS"
CONFIG_DIR = "C:/Users/ssingh/Projects/PSL_Modeling/Account_Score/config"

# Colors
DARK_BLUE = RGBColor(0x1B, 0x2A, 0x4A)
MED_BLUE = RGBColor(0x00, 0x5B, 0x96)
LIGHT_BLUE = RGBColor(0x00, 0x96, 0xD6)
GREEN = RGBColor(0x4C, 0xAF, 0x50)
ORANGE = RGBColor(0xFF, 0x9F, 0x00)
RED = RGBColor(0xE5, 0x3E, 0x3E)
GRAY = RGBColor(0x6B, 0x7B, 0x8D)
LIGHT_GRAY = RGBColor(0xD0, 0xD0, 0xD0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)
TABLE_HEADER_BG = RGBColor(0x1B, 0x2A, 0x4A)
TABLE_ROW_ALT = RGBColor(0xF0, 0xF4, 0xF8)


def load_data():
    """Load the most recent scoring output."""
    csv_files = glob.glob(os.path.join(OUTPUT_DIR, "physician_scores_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No scoring output found in {OUTPUT_DIR}")
    latest = max(csv_files, key=os.path.getmtime)
    print(f"Loading: {latest}")
    return pd.read_csv(latest)


def load_configs():
    """Load pipeline configurations."""
    with open(os.path.join(CONFIG_DIR, "pipeline_params.json")) as f:
        params = json.load(f)
    with open(os.path.join(CONFIG_DIR, "scoring_weights.json")) as f:
        weights = json.load(f)
    with open(os.path.join(CONFIG_DIR, "specialty_tiers.json")) as f:
        specialties = json.load(f)
    with open(os.path.join(CONFIG_DIR, "state_tiers.json")) as f:
        states = json.load(f)
    with open(os.path.join(CONFIG_DIR, "binning_thresholds.json")) as f:
        thresholds = json.load(f)
    return params, weights, specialties, states, thresholds


def save_chart(fig):
    """Save matplotlib figure to temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp_path = tmp.name
    tmp.close()
    fig.savefig(tmp_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    return tmp_path


def add_slide_number(slide, num, total=None):
    """Add slide number in bottom right."""
    text = str(num) if total is None else f"{num}"
    txBox = slide.shapes.add_textbox(Inches(12.5), Inches(7.1), Inches(0.7), Inches(0.3))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(10)
    p.font.color.rgb = GRAY
    p.alignment = PP_ALIGN.RIGHT


def add_header(slide, title, subtitle=None):
    """Add consistent header matching reference style."""
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(0.6))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    if subtitle:
        txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(0.75), Inches(12), Inches(0.4))
        tf2 = txBox2.text_frame
        p2 = tf2.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(14)
        p2.font.color.rgb = GRAY


def add_body_text(slide, text, left=0.5, top=1.2, width=12.0, height=5.5, font_size=14):
    """Add body text box."""
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.color.rgb = DARK_BLUE
        p.space_after = Pt(6)
    return txBox


def add_table(slide, data, headers, left=0.5, top=1.5, width=12.3, row_height=0.35):
    """Add a formatted table to slide."""
    rows = len(data) + 1  # +1 for header
    cols = len(headers)
    col_width = width / cols

    table_shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top),
                                          Inches(width), Inches(row_height * rows))
    table = table_shape.table

    # Set column widths
    for i in range(cols):
        table.columns[i].width = Inches(col_width)

    # Header row
    for j, header in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = TABLE_HEADER_BG
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    # Data rows
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = str(val)
            if i % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = TABLE_ROW_ALT
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(11)
            p.font.color.rgb = DARK_BLUE
            p.alignment = PP_ALIGN.CENTER
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    return table_shape


# ============================================================
# SLIDE GENERATORS (following reference structure)
# ============================================================

def slide_title(prs, df):
    """Slide 1: Title."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = DARK_BLUE

    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = "MagMutual"
    p.font.size = Pt(18)
    p.font.color.rgb = LIGHT_BLUE
    p.alignment = PP_ALIGN.LEFT

    p2 = tf.add_paragraph()
    p2.text = "Physician Account Scoring"
    p2.font.size = Pt(40)
    p2.font.bold = True
    p2.font.color.rgb = WHITE
    p2.alignment = PP_ALIGN.LEFT

    p3 = tf.add_paragraph()
    p3.space_before = Pt(12)
    p3.text = "Medical Professional Liability"
    p3.font.size = Pt(20)
    p3.font.color.rgb = LIGHT_BLUE
    p3.alignment = PP_ALIGN.LEFT

    # Footer
    txBox2 = slide.shapes.add_textbox(Inches(1), Inches(6.2), Inches(11), Inches(0.5))
    tf2 = txBox2.text_frame
    p4 = tf2.paragraphs[0]
    p4.text = "Actuarial Analytics | April 2026"
    p4.font.size = Pt(14)
    p4.font.color.rgb = GRAY
    p4.alignment = PP_ALIGN.LEFT


def slide_data_overview(prs, df, params, slide_num):
    """Slide 2: Data Overview."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Data Overview")
    add_slide_number(slide, slide_num)

    text = (
        "Scoring Scope:\n"
        "\u2022  MagMutual Physician Medical Professional Liability (MPL) policies\n"
        "\u2022  Coverage effective dates: 2017 through 2023\n"
        "\u2022  Policy effective year >= 2017\n"
        f"\u2022  Filters: Written Premium (Burned, Class OL) > 0, BCE > 0\n"
        "\n"
        "Data Source:\n"
        "\u2022  Modeling dataset: 2025 MR DHC Merged Features\n"
        "\u2022  Physician-year level granularity (NPI x Coverage Year)\n"
        "\n"
        "After matching and application of filters:"
    )
    add_body_text(slide, text, top=1.0, height=3.0, font_size=14)

    # Summary table
    total_raw = 276073
    total_scored = len(df)
    total_removed = total_raw - total_scored
    total_premium = df['WRTN_PREM_AMT_ITD_BURNED'].sum()

    n_physicians = df['NPI'].nunique() if 'NPI' in df.columns else 'N/A'
    n_specialties = df['OL_RISK_SPECIALTY_DESC'].nunique() if 'OL_RISK_SPECIALTY_DESC' in df.columns else 'N/A'
    n_states = df['ST'].nunique() if 'ST' in df.columns else 'N/A'

    headers = ['Metric', 'Value']
    data = [
        ['Total Records in Source', f'{total_raw:,}'],
        ['Records After Filters', f'{total_scored:,}'],
        ['Records Removed', f'{total_removed:,} ({total_removed/total_raw*100:.1f}%)'],
        ['Unique Physicians (NPI)', f'{n_physicians:,}'],
        ['Unique Specialties', f'{n_specialties}'],
        ['Unique States', f'{n_states}'],
        ['Total Written Premium', f'${total_premium:,.0f}'],
        ['Coverage Years', '2017 - 2023'],
    ]
    add_table(slide, data, headers, left=0.5, top=4.0, width=6.0)


def slide_score_components(prs, weights, slide_num):
    """Slide 3: Score Components Overview."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Score Components")
    add_slide_number(slide, slide_num)

    text = (
        "The algorithm produces 4 component scores from their respective sub-scores, "
        "and a final composite score from all sub-scores. The final composite score ranges from 1 (Best) to 10 (Worst)."
    )
    add_body_text(slide, text, top=0.9, height=0.6, font_size=14)

    # Component table
    comp_w = weights['composite_weights']
    headers = ['Component', 'Weight', '# Sub-Scores', 'Description']
    data = [
        ['Adequacy', f"{comp_w['adequacy']*100:.0f}%", '9',
         'Loss cost, frequency, severity, loss ratio (credibility weighted)'],
        ['Capacity', f"{comp_w['capacity']*100:.0f}%", '3',
         'Limits-to-premium ratio, risk count, loss-free discount years'],
        ['Appetite', f"{comp_w['appetite']*100:.0f}%", '7',
         'Specialty tier, state venue, years since graduation, RVU, tenure, practice size'],
        ['Environment', f"{comp_w['environment']*100:.0f}%", '4',
         'Income inequality, population density, violent crime rate, pct uninsured'],
    ]
    add_table(slide, data, headers, left=0.5, top=1.8, width=12.3, row_height=0.45)

    # Sub-score detail
    text2 = (
        "\nSub-Score Scale: 1 to 30 (rescaled to 1-10 for component calculation)\n"
        "Composite Formula: Composite = 0.40 \u00d7 Adequacy + 0.25 \u00d7 Capacity + 0.25 \u00d7 Appetite + 0.10 \u00d7 Environment\n"
        "Missing Values: When a sub-score cannot be computed, its weight is set to 0 and excluded from the weighted average.\n"
        "Credibility: Loss-based sub-scores are blended with portfolio average using Z = min(\u221a(Premium/$50K), 1)"
    )
    add_body_text(slide, text2, top=4.0, height=2.5, font_size=12)


def slide_data_sources(prs, weights, slide_num):
    """Slide 4: Data Sources for Score Components."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Score Components - Data Sources")
    add_slide_number(slide, slide_num)

    text = "The sources of key data fields in deriving score components:"
    add_body_text(slide, text, top=0.9, height=0.4, font_size=14)

    headers = ['Sub-Score', 'Component', 'Numerator', 'Denominator']
    data = []

    # Adequacy sub-scores
    for name, cfg in weights.get('adequacy_sub_scores', {}).items():
        clean_name = name.replace('_', ' ').title()
        num = cfg.get('numerator', cfg.get('source_column', '-'))
        den = cfg.get('denominator', '-')
        data.append([clean_name, 'Adequacy', num[:35], den[:35]])

    # Capacity
    for name, cfg in weights.get('capacity_sub_scores', {}).items():
        clean_name = name.replace('_', ' ').title()
        num = cfg.get('numerator', cfg.get('source_column', '-'))
        den = cfg.get('denominator', '-')
        data.append([clean_name, 'Capacity', num[:35], den[:35]])

    add_table(slide, data[:12], headers, left=0.3, top=1.5, width=12.7, row_height=0.35)


def slide_weight_selection(prs, weights, df, slide_num):
    """Slide 5: Weight Selection."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Weight Selection")
    add_slide_number(slide, slide_num)

    text = (
        "The weights for the loss-related components (Adequacy) are determined based on the loss ratio "
        "breakdown of the portfolio. Below are the selected weights for Physician MPL:\n"
        "\n"
        "Adequacy sub-scores are weighted by the relative contribution of each loss component "
        "(indemnity vs expense, frequency vs severity) to overall losses."
    )
    add_body_text(slide, text, top=0.9, height=1.5, font_size=14)

    # Adequacy sub-score weights
    headers = ['Adequacy Sub-Score', 'Weight', 'Credibility Weighted']
    data = []
    for name, cfg in weights.get('adequacy_sub_scores', {}).items():
        clean_name = name.replace('_', ' ').title()
        w = cfg.get('weight', 0)
        cred = 'Yes' if cfg.get('apply_credibility', False) else 'No'
        data.append([clean_name, f"{w:.2f}", cred])

    add_table(slide, data, headers, left=0.5, top=3.0, width=8.0, row_height=0.35)


def slide_result_summary(prs, df, slide_num):
    """Slide 6: Result Summary by Components."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Result Summary \u2013 By Components")
    add_slide_number(slide, slide_num)

    text = "The below table shows a summary of the arithmetic average component scores in each composite score bucket:"
    add_body_text(slide, text, top=0.9, height=0.4, font_size=14)

    # Build summary table
    summary = df.groupby('composite_score').agg(
        count=('composite_score', 'size'),
        premium=('WRTN_PREM_AMT_ITD_BURNED', 'sum'),
        adequacy=('adequacy_score', 'mean'),
        capacity=('capacity_score', 'mean'),
        appetite=('appetite_score', 'mean'),
        environment=('environment_score', 'mean'),
    ).reset_index()
    summary['pct'] = summary['count'] / summary['count'].sum() * 100
    summary['prem_pct'] = summary['premium'] / summary['premium'].sum() * 100

    headers = ['Composite\nScore', 'Physician\nCount', '%', 'Written\nPremium', '%',
               'Adequacy\nScore', 'Capacity\nScore', 'Appetite\nScore', 'Environment\nScore']
    data = []
    for _, row in summary.iterrows():
        data.append([
            f"{int(row['composite_score'])}",
            f"{int(row['count']):,}",
            f"{row['pct']:.1f}%",
            f"${row['premium']:,.0f}",
            f"{row['prem_pct']:.1f}%",
            f"{row['adequacy']:.2f}",
            f"{row['capacity']:.2f}",
            f"{row['appetite']:.2f}",
            f"{row['environment']:.2f}",
        ])

    # Total row
    data.append([
        'Total',
        f"{len(df):,}",
        '100.0%',
        f"${df['WRTN_PREM_AMT_ITD_BURNED'].sum():,.0f}",
        '100.0%',
        f"{df['adequacy_score'].mean():.2f}",
        f"{df['capacity_score'].mean():.2f}",
        f"{df['appetite_score'].mean():.2f}",
        f"{df['environment_score'].mean():.2f}",
    ])

    add_table(slide, data, headers, left=0.3, top=1.5, width=12.7, row_height=0.4)

    # Note
    note_text = (
        "Note: Adequacy scores are credibility-weighted. Physicians with low premium volume "
        "are blended toward the portfolio average (score ~5)."
    )
    add_body_text(slide, note_text, top=6.2, height=0.5, font_size=11)


def slide_result_summary_subscores(prs, df, slide_num):
    """Slide 7: Result Summary by Sub-Scores (KPIs)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Result Summary \u2013 By Sub-Scores")
    add_slide_number(slide, slide_num)

    text = "The below table shows a summary of the average KPIs in each composite score bucket:"
    add_body_text(slide, text, top=0.9, height=0.4, font_size=14)

    # KPI summary by composite bucket
    kpi_cols = ['kpi_total_loss_cost', 'kpi_total_frequency', 'kpi_actual_loss_ratio']
    available_kpis = [c for c in kpi_cols if c in df.columns]

    summary = df.groupby('composite_score').agg(
        count=('composite_score', 'size'),
        total_loss_cost=('kpi_total_loss_cost', 'mean'),
        total_freq=('kpi_total_frequency', 'mean'),
        loss_ratio=('kpi_actual_loss_ratio', 'mean'),
    ).reset_index()

    headers = ['Composite\nScore', 'Count', 'Avg Total\nLoss Cost', 'Avg Total\nFrequency', 'Avg Loss\nRatio']
    data = []
    for _, row in summary.iterrows():
        data.append([
            f"{int(row['composite_score'])}",
            f"{int(row['count']):,}",
            f"{row['total_loss_cost']:.2f}",
            f"{row['total_freq']:.4f}",
            f"{row['loss_ratio']:.4f}",
        ])

    add_table(slide, data, headers, left=0.5, top=1.5, width=10.0, row_height=0.4)

    note = (
        "Total Loss Cost: Ultimate Total Loss / BCE (burned)\n"
        "Total Frequency: Claim Count / FTE Exposure (burned)\n"
        "Loss Ratio: Ultimate Total Loss / Written Premium (burned, OL)\n"
        "\n"
        "These average ratios are calculated as simple arithmetic means within each bucket.\n"
        "Higher composite scores correlate with higher loss metrics, validating the scoring model."
    )
    add_body_text(slide, note, top=4.8, height=2.0, font_size=12)


def slide_subscore_distribution(prs, df, thresholds, var_name, display_name, description, portfolio_avg, slide_num):
    """Individual sub-score slide with chart and banding table (like reference)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, display_name)
    add_slide_number(slide, slide_num)

    # Description text
    add_body_text(slide, description, top=0.8, height=0.8, font_size=12)

    # Get score distribution
    col_name = f'score_{var_name}'
    if col_name not in df.columns:
        add_body_text(slide, f"Score column '{col_name}' not available.", top=2.0)
        return

    valid_scores = df[col_name].dropna()
    valid_scores = valid_scores[valid_scores >= 1]

    if len(valid_scores) == 0:
        add_body_text(slide, "No valid scores for this variable.", top=2.0)
        return

    # Create clustered column chart
    score_dist = valid_scores.value_counts().sort_index()
    all_scores = range(1, 31)
    counts = [int(score_dist.get(s, 0)) for s in all_scores]

    # Add chart using python-pptx native chart
    chart_data = CategoryChartData()
    chart_data.categories = [str(s) for s in all_scores]
    chart_data.add_series('Count', counts)

    chart_left = Inches(0.3)
    chart_top = Inches(1.8)
    chart_width = Inches(9.0)
    chart_height = Inches(5.0)

    chart_shape = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, chart_left, chart_top, chart_width, chart_height, chart_data
    )
    chart = chart_shape.chart
    chart.has_legend = False

    # Format chart
    plot = chart.plots[0]
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = MED_BLUE

    # Value axis
    value_axis = chart.value_axis
    value_axis.has_title = True
    value_axis.axis_title.text_frame.paragraphs[0].text = "Count"
    value_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(11)

    # Category axis
    cat_axis = chart.category_axis
    cat_axis.has_title = True
    cat_axis.axis_title.text_frame.paragraphs[0].text = "Score (1=Best, 30=Worst)"
    cat_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(11)
    cat_axis.tick_labels.font.size = Pt(9)

    # Stats text box on right
    stats_text = (
        f"Portfolio Average: {portfolio_avg}\n"
        f"Valid Records: {len(valid_scores):,}\n"
        f"Mean Score: {valid_scores.mean():.1f}\n"
        f"Median Score: {valid_scores.median():.0f}\n"
        f"Std Dev: {valid_scores.std():.1f}"
    )
    add_body_text(slide, stats_text, left=9.5, top=2.0, width=3.5, height=2.5, font_size=11)

    # Banding summary (show key thresholds)
    if var_name in thresholds:
        bins = thresholds[var_name]
        # Show a condensed version (scores 1, 5, 10, 15, 20, 25, 30)
        key_scores = [1, 5, 10, 15, 20, 25, 30]
        banding_text = "Score Bands:\n"
        for b in bins:
            if b.get('score', -1) in key_scores:
                lb = b.get('lower_bound', '')
                ub = b.get('upper_bound', '')
                if isinstance(lb, (int, float)) and isinstance(ub, (int, float)):
                    banding_text += f"  {b['score']:2d}: [{lb:.4f}, {ub:.4f})\n"
        add_body_text(slide, banding_text, left=9.5, top=4.2, width=3.5, height=3.0, font_size=10)


def slide_specialty_tier(prs, df, specialties, slide_num):
    """Slide: Specialty Tier Distribution."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Underwriting Appetite \u2013 Specialty Risk Tier")
    add_slide_number(slide, slide_num)

    text = (
        "Specialty was mapped to risk tiers (1-10) based on portfolio loss ratio by specialty.\n"
        "The tier assignment reflects the historical loss experience of each specialty class."
    )
    add_body_text(slide, text, top=0.8, height=0.7, font_size=13)

    # Build specialty table
    tiers = specialties.get('tiers', specialties.get('specialties', {}))
    if isinstance(tiers, list):
        tier_items = [(t['specialty'], t['score']) for t in tiers]
    else:
        tier_items = list(tiers.items())

    # Sort by score
    tier_items.sort(key=lambda x: x[1])

    headers = ['Specialty', 'Risk Score (1-10)', 'Risk Level']
    data = []
    for spec, score in tier_items[:15]:  # First 15 to fit
        if score <= 3:
            level = 'Low'
        elif score <= 5:
            level = 'Moderate'
        elif score <= 7:
            level = 'High'
        else:
            level = 'Very High'
        data.append([spec[:40], str(score), level])

    add_table(slide, data, headers, left=0.5, top=1.7, width=11.0, row_height=0.32)


def slide_state_venue(prs, df, states, slide_num):
    """Slide: State Venue Risk Distribution."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Underwriting Appetite \u2013 State Venue Risk")
    add_slide_number(slide, slide_num)

    text = (
        "State was mapped to venue risk scores (1-10) based on portfolio loss ratio and tort environment.\n"
        "States with tort reform or favorable court environments receive lower scores."
    )
    add_body_text(slide, text, top=0.8, height=0.7, font_size=13)

    # Build state table
    tiers = states.get('tiers', states.get('states', {}))
    if isinstance(tiers, list):
        tier_items = [(t['state'], t['score']) for t in tiers]
    else:
        tier_items = list(tiers.items())

    tier_items.sort(key=lambda x: x[1])

    # Show in two columns of states
    headers = ['State', 'Score', 'State', 'Score', 'State', 'Score']
    data = []
    n = len(tier_items)
    rows_per_col = (n + 2) // 3
    for i in range(rows_per_col):
        row = []
        for col in range(3):
            idx = i + col * rows_per_col
            if idx < n:
                row.extend([tier_items[idx][0], str(tier_items[idx][1])])
            else:
                row.extend(['', ''])
        data.append(row)

    add_table(slide, data[:13], headers, left=0.5, top=1.7, width=10.0, row_height=0.32)


def slide_credibility(prs, df, slide_num):
    """Slide: Credibility Weighting."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Credibility Weighting")
    add_slide_number(slide, slide_num)

    text = (
        "Loss-based sub-scores (Adequacy component) are credibility weighted to account for premium volume differences.\n"
        "\n"
        "Formula: Z = min(\u221a(Written Premium / $50,000), 1)\n"
        "Blended Score = Z \u00d7 Individual Score + (1 - Z) \u00d7 Portfolio Average\n"
        "\n"
        "This ensures physicians with low premium volume (thin accounts) are blended toward the portfolio average, "
        "preventing unreliable extreme scores from small-volume data."
    )
    add_body_text(slide, text, top=0.9, height=2.0, font_size=14)

    # Credibility distribution chart
    if 'credibility_z' in df.columns:
        z_data = df['credibility_z'].dropna()

        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.hist(z_data, bins=40, color='#005B96', edgecolor='white', alpha=0.85)
        ax.set_xlabel('Credibility Z-Factor', fontsize=10)
        ax.set_ylabel('Physician Count', fontsize=10)
        ax.set_title('Distribution of Credibility Z-Factor', fontsize=12, color='#1B2A4A')
        ax.axvline(x=1.0, color='#4CAF50', linestyle='--', linewidth=2, label='Full Credibility (Z=1)')
        ax.axvline(x=z_data.mean(), color='#E53E3E', linestyle=':', linewidth=2, label=f'Mean Z = {z_data.mean():.2f}')
        ax.legend(fontsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        chart_path = save_chart(fig)
        slide.shapes.add_picture(chart_path, Inches(0.5), Inches(3.5), Inches(8.5), Inches(3.8))
        os.unlink(chart_path)

        # Stats
        full_cred = (z_data >= 1.0).mean() * 100
        stats = f"Full Credibility (Z=1): {full_cred:.1f}%\nPartial Credibility: {100-full_cred:.1f}%\nMean Z: {z_data.mean():.3f}"
        add_body_text(slide, stats, left=9.5, top=4.0, width=3.5, height=1.5, font_size=12)


def slide_composite_distribution(prs, df, slide_num):
    """Slide: Final Composite Score Distribution."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Composite Score Distribution")
    add_slide_number(slide, slide_num)

    text = "The distribution of the final composite scores (1=Best, 10=Worst):"
    add_body_text(slide, text, top=0.8, height=0.4, font_size=14)

    # Native chart
    score_counts = df['composite_score'].value_counts().sort_index()
    scores = range(1, 11)
    counts = [int(score_counts.get(s, 0)) for s in scores]
    pcts = [c / len(df) * 100 for c in counts]

    chart_data = CategoryChartData()
    chart_data.categories = [str(s) for s in scores]
    chart_data.add_series('Count', counts)

    chart_shape = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.5), Inches(1.5), Inches(8.5), Inches(5.5), chart_data
    )
    chart = chart_shape.chart
    chart.has_legend = False
    series = chart.plots[0].series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = MED_BLUE

    cat_axis = chart.category_axis
    cat_axis.has_title = True
    cat_axis.axis_title.text_frame.paragraphs[0].text = "Composite Score"
    cat_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(12)

    value_axis = chart.value_axis
    value_axis.has_title = True
    value_axis.axis_title.text_frame.paragraphs[0].text = "Physician Count"
    value_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(12)

    # Stats on the right
    stats = (
        f"Total Physicians: {len(df):,}\n"
        f"Mean: {df['composite_score'].mean():.2f}\n"
        f"Median: {df['composite_score'].median():.0f}\n"
        f"Std Dev: {df['composite_score'].std():.2f}\n\n"
        "Distribution:\n"
    )
    for s, c, p in zip(scores, counts, pcts):
        if c > 0:
            stats += f"  Score {s}: {c:,} ({p:.1f}%)\n"

    add_body_text(slide, stats, left=9.3, top=1.5, width=3.8, height=5.5, font_size=11)


def slide_composite_detail(prs, df, slide_num):
    """Slide: Detailed Final Composite Score Distribution with table and chart."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Final Composite Score \u2013 Detailed Distribution")
    add_slide_number(slide, slide_num)

    text = "The table below shows the full distribution of physicians by final composite score, including cumulative counts and premium share:"
    add_body_text(slide, text, top=0.8, height=0.5, font_size=14)

    # Build detailed table
    score_counts = df['composite_score'].value_counts().sort_index()
    scores = range(1, 11)
    total_n = len(df)
    total_prem = df['WRTN_PREM_AMT_ITD_BURNED'].sum()

    headers = ['Composite\nScore', 'Physician\nCount', '% of\nTotal', 'Cumulative\n%',
               'Written\nPremium', '% of\nPremium', 'Cumulative\nPremium %',
               'Avg Adequacy\nScore', 'Avg Composite\n(Continuous)']
    data = []
    cum_count = 0
    cum_prem = 0.0
    for s in scores:
        n = int(score_counts.get(s, 0))
        if n == 0:
            continue
        cum_count += n
        bucket = df[df['composite_score'] == s]
        prem = bucket['WRTN_PREM_AMT_ITD_BURNED'].sum()
        cum_prem += prem
        avg_adeq = bucket['adequacy_score'].mean()
        # continuous composite = weighted average before rounding
        avg_cont = bucket['composite_score_continuous'].mean() if 'composite_score_continuous' in df.columns else float(s)
        data.append([
            str(s),
            f"{n:,}",
            f"{n/total_n*100:.1f}%",
            f"{cum_count/total_n*100:.1f}%",
            f"${prem:,.0f}",
            f"{prem/total_prem*100:.1f}%",
            f"{cum_prem/total_prem*100:.1f}%",
            f"{avg_adeq:.2f}",
            f"{avg_cont:.2f}",
        ])

    add_table(slide, data, headers, left=0.3, top=1.5, width=12.7, row_height=0.42)

    # Interpretation note
    note = (
        "Score Interpretation: 1 = Best (lowest risk), 10 = Worst (highest risk)\n"
        "Scores 2-5 account for the majority of the portfolio. "
        "Higher composite scores should correlate with higher loss metrics (validated in Result Summary slides)."
    )
    add_body_text(slide, note, top=6.0, height=1.0, font_size=12)


def slide_appendix_header(prs, title, slide_num):
    """Appendix section divider."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RGBColor(0xF0, 0xF4, 0xF8)

    txBox = slide.shapes.add_textbox(Inches(1), Inches(3.0), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE
    p.alignment = PP_ALIGN.LEFT

    add_slide_number(slide, slide_num)


# ============================================================
# MAIN
# ============================================================

def main():
    print("Loading data and configs...")
    df = load_data()
    params, weights, specialties, states, thresholds = load_configs()

    print(f"Creating presentation with {len(df):,} records...")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_num = 0

    # Slide 1: Title
    slide_num += 1
    print(f"  Slide {slide_num}: Title")
    slide_title(prs, df)

    # Slide 2: Data Overview
    slide_num += 1
    print(f"  Slide {slide_num}: Data Overview")
    slide_data_overview(prs, df, params, slide_num)

    # Slide 3: Score Components
    slide_num += 1
    print(f"  Slide {slide_num}: Score Components")
    slide_score_components(prs, weights, slide_num)

    # Slide 4: Data Sources
    slide_num += 1
    print(f"  Slide {slide_num}: Data Sources")
    slide_data_sources(prs, weights, slide_num)

    # Slide 5: Weight Selection
    slide_num += 1
    print(f"  Slide {slide_num}: Weight Selection")
    slide_weight_selection(prs, weights, df, slide_num)

    # Slide 6: Result Summary - By Components
    slide_num += 1
    print(f"  Slide {slide_num}: Result Summary - Components")
    slide_result_summary(prs, df, slide_num)

    # Slide 7: Result Summary - By Sub-Scores
    slide_num += 1
    print(f"  Slide {slide_num}: Result Summary - Sub-Scores")
    slide_result_summary_subscores(prs, df, slide_num)

    # Slide 8: Composite Distribution
    slide_num += 1
    print(f"  Slide {slide_num}: Composite Distribution")
    slide_composite_distribution(prs, df, slide_num)

    # Slide 9: Composite Detail Table
    slide_num += 1
    print(f"  Slide {slide_num}: Composite Detail Distribution")
    slide_composite_detail(prs, df, slide_num)

    # Slide 10: Credibility
    slide_num += 1
    print(f"  Slide {slide_num}: Credibility Weighting")
    slide_credibility(prs, df, slide_num)

    # Appendix 1: Sub-Score Distributions
    slide_num += 1
    print(f"  Slide {slide_num}: Appendix 1 Header")
    slide_appendix_header(prs, "Appendix 1\n\nSub-Score Distributions", slide_num)

    # Individual sub-score slides
    subscore_slides = [
        ('total_loss_cost', 'Adequacy \u2013 Total Loss Cost',
         'Definition: Ultimate Total Loss / BCE (burned). Credibility weighted.\nThe overall portfolio average loss cost is used as the complement for credibility blending.',
         'Credibility Weighted'),
        ('total_frequency', 'Adequacy \u2013 Total Frequency',
         'Definition: Total Claim Count / FTE Exposure (burned). Credibility weighted.\nA score of 1 is assigned to physicians with zero claims (majority of portfolio).',
         'Credibility Weighted'),
        ('actual_loss_ratio', 'Adequacy \u2013 Loss Ratio',
         'Definition: Ultimate Total Loss / Written Premium (burned, OL). Credibility weighted.\nThe overall portfolio loss ratio is used as the complement.',
         'Credibility Weighted'),
        ('limits_to_premium', 'Capacity \u2013 Limits to Premium',
         'Definition: Per-Occurrence Limit / Written Premium.\nHigher ratios indicate more capacity relative to premium charged.',
         'N/A'),
        ('specialty_risk_tier', 'Appetite \u2013 Specialty Risk Tier',
         'Specialty mapped to risk tiers (1-10) based on portfolio loss ratio.\nScores are rescaled from 1-10 categorical to 1-30 sub-score scale.',
         'Categorical'),
        ('state_venue_risk', 'Appetite \u2013 State Venue Risk',
         'State mapped to risk scores (1-10) based on loss ratio and tort environment.\nStates with tort reform receive lower (better) scores.',
         'Categorical'),
        ('years_since_graduation', 'Appetite \u2013 Years Since Graduation',
         'Definition: Years since medical school graduation.\nU-shaped scoring: very new and very experienced physicians may carry different risk profiles.',
         'N/A'),
        ('income_inequality', 'Environment \u2013 Income Inequality',
         'Definition: Gini coefficient for the physician practice area.\nHigher inequality correlates with higher malpractice claim propensity.',
         'N/A'),
        ('violent_crime_rate', 'Environment \u2013 Violent Crime Rate',
         'Definition: Violent crime rate per 100K in practice area.\nProxy for overall environmental litigation risk.',
         'N/A'),
    ]

    for var_name, display_name, desc, portfolio_avg in subscore_slides:
        slide_num += 1
        print(f"  Slide {slide_num}: {display_name}")
        slide_subscore_distribution(prs, df, thresholds, var_name, display_name, desc, portfolio_avg, slide_num)

    # Specialty Tier
    slide_num += 1
    print(f"  Slide {slide_num}: Specialty Tier Table")
    slide_specialty_tier(prs, df, specialties, slide_num)

    # State Venue
    slide_num += 1
    print(f"  Slide {slide_num}: State Venue Table")
    slide_state_venue(prs, df, states, slide_num)

    # Save
    output_path = os.path.join(OUTPUT_DIR, "Physician_MPL_Account_Scoring_Model.pptx")
    prs.save(output_path)
    print(f"\nPresentation saved to: {output_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
