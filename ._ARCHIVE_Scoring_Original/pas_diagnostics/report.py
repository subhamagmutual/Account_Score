"""Report writers: markdown for humans, CSV/Excel for the actuarial review."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .checks import Finding, sort_findings

_BADGE = {"BLOCKER": "&#9679;&#9679;&#9679;", "HIGH": "&#9679;&#9679;",
          "MEDIUM": "&#9679;", "INFO": "&#8211;"}


def write_csvs(tables: dict[str, pd.DataFrame], outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in tables.items():
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            continue
        p = outdir / f"{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    return written


def write_excel(tables: dict[str, pd.DataFrame], path: Path) -> Path | None:
    """One workbook, one sheet per check. Values only -- no formulas, so there
    is nothing to recalculate and nothing to go stale."""
    frames = {k: v for k, v in tables.items()
              if isinstance(v, pd.DataFrame) and not v.empty}
    if not frames:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        for name, df in frames.items():
            df.to_excel(xl, sheet_name=name[:31], index=False)
    return path


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    if isinstance(v, float):
        return f"{v:,.4g}"
    return str(v)


def _md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_no rows_\n"
    d = df.head(max_rows)
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    rule = "| " + " | ".join("---" for _ in d.columns) + " |"
    body = "\n".join("| " + " | ".join(_fmt(v) for v in row) + " |"
                     for row in d.itertuples(index=False))
    note = ""
    if len(df) > max_rows:
        note = f"\n\n_{len(df) - max_rows} further rows in the CSV._\n"
    return f"{head}\n{rule}\n{body}\n{note}"


def write_markdown(
    findings: list[Finding],
    tables: dict[str, pd.DataFrame],
    meta: dict,
    path: Path,
) -> Path:
    f = sort_findings(findings)
    counts = {s: sum(1 for x in f if x.severity == s)
              for s in ("BLOCKER", "HIGH", "MEDIUM", "INFO")}

    L: list[str] = []
    L.append("# Physician MPL PAS - Diagnostic Report\n")
    L.append(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")

    L.append("## Run provenance\n")
    L.append("Stamp this into every deliverable. Model risk management will ask, "
             "and the answer should be a file path rather than a memory.\n")
    L.append(_md_table(pd.DataFrame([{"key": k, "value": str(v)}
                                     for k, v in meta.items()])))

    L.append("\n## Verdict\n")
    if counts["BLOCKER"]:
        L.append(f"**{counts['BLOCKER']} blocking finding(s).** The score should not "
                 "influence pricing, appear in an underwriter workflow, or be presented "
                 "as validated until these are resolved.\n")
    elif counts["HIGH"]:
        L.append(f"**No blockers, {counts['HIGH']} high-severity finding(s).** Usable "
                 "for internal exploration; not yet defensible in a rate filing or a "
                 "model governance review.\n")
    else:
        L.append("No blocking or high-severity findings.\n")

    L.append(_md_table(pd.DataFrame([
        {"severity": s, "count": counts[s]} for s in
        ("BLOCKER", "HIGH", "MEDIUM", "INFO")])))

    L.append("\n## Findings\n")
    for sev in ("BLOCKER", "HIGH", "MEDIUM", "INFO"):
        group = [x for x in f if x.severity == sev]
        if not group:
            continue
        L.append(f"\n### {sev} ({len(group)})  {_BADGE[sev]}\n")
        for x in group:
            L.append(f"- **{x.check} / {x.subject}** - {x.message}\n")

    section_titles = {
        "schema": "Schema resolution",
        "data_quality": "Data quality",
        "adequacy_reality": "Is Adequacy measuring loss experience?",
        "circularity": "Circularity: bands cut on the target",
        "variable_signal": "Per-variable signal",
        "discrimination": "Band discrimination",
        "effective_weights": "Nominal vs realised weights",
        "vif": "Redundancy (VIF)",
        "lift_summary": "Composite lift",
        "stability": "Score stability (PSI)",
    }
    L.append("\n## Detail\n")
    for key, title in section_titles.items():
        if key in tables and isinstance(tables[key], pd.DataFrame) and not tables[key].empty:
            L.append(f"\n### {title}\n")
            L.append(_md_table(tables[key]))

    L.append("\n## How to read this\n")
    L.append(
        "- **Gini** below zero means the score orders loss backwards. Below ~0.10 means "
        "it carries no usable ordering. Read it comparatively, not against an absolute "
        "benchmark.\n"
        "- **Spearman** in the per-variable table is the rank correlation between score "
        "band and that band's loss ratio. It is the question an underwriter will ask "
        "first: does a 7 really lose more than a 3?\n"
        "- **Circularity** findings invalidate lift, they do not merely weaken it. A "
        "tier cut on loss ratio will always appear predictive of loss ratio.\n"
        "- **Realised weights** are what the book actually experienced. Where they "
        "diverge from nominal, the deck describes a model nobody was scored by.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(L))
    return path
