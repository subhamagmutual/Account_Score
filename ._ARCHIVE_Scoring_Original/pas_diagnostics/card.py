"""
The Physician PAS card: the mockup on slide 9, rendered from real data.

Self-contained HTML with inline CSS -- no build step, no CDN, no framework. It
can be opened from a network share, pasted into a Confluence page, embedded in
an Appian frame, or printed for a renewal file. That matters more than elegance
for something an underwriter has to reach in the middle of a quote.

Design choices that are not cosmetic:

  * Every driver shows its RAW value beside its score. A score of 10 is an
    assertion; "Loss-Free Years: -99 (unknown)" is a fact the underwriter can
    act on. Showing only the score hides exactly the errors the card should
    surface.
  * Caveats render as visible warnings, not footnotes. A driver resting on a
    sentinel or on a tier cut from loss ratio says so, on the card, in the
    workflow, where the decision is made.
  * The arithmetic is shown: anchor 4.5, plus the signed contributions, equals
    the score. An underwriter who can reproduce the number will trust it; one
    who cannot will override it.
  * No recommendation text. The deck's mockup asserts "Competitive pricing
    appropriate", which the model has not earned. The card presents evidence
    and leaves the decision with the underwriter.
"""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd

from .reasons import ANCHOR, attribute, effective_weights, _quality_flag
from .schema import ColumnMap

_CSS = """
:root{--ink:#1a1d21;--muted:#6b7280;--rule:#e3e6ea;--bg:#fff;
--good:#1b7f5a;--bad:#b3261e;--warn:#8a5a00;--warnbg:#fff8e6}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:#f6f7f9;color:var(--ink);
font:14px/1.5 Arial,Helvetica,sans-serif}
.card{max-width:860px;margin:0 auto 28px;background:var(--bg);
border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.head{display:flex;justify-content:space-between;align-items:flex-start;
gap:20px;padding:20px 24px;border-bottom:1px solid var(--rule)}
.who{font-size:19px;font-weight:700;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px}
.badge{text-align:center;min-width:104px;padding:12px 14px;border-radius:8px;
background:#f2f4f7;border:1px solid var(--rule)}
.badge .n{font-size:34px;font-weight:700;line-height:1}
.badge .l{font-size:11px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);margin-top:4px}
.comps{display:flex;gap:0;border-bottom:1px solid var(--rule)}
.comp{flex:1;padding:12px 16px;border-right:1px solid var(--rule)}
.comp:last-child{border-right:0}
.comp .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
color:var(--muted)}
.comp .v{font-size:20px;font-weight:600}
.comp .w{font-size:11px;color:var(--muted)}
.sec{padding:18px 24px;border-bottom:1px solid var(--rule)}
.sec:last-child{border-bottom:0}
h3{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--muted);margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:11px;
text-transform:uppercase;letter-spacing:.04em;padding:0 8px 6px 0;
border-bottom:1px solid var(--rule)}
td{padding:7px 8px 7px 0;border-bottom:1px solid #f1f3f5;vertical-align:top}
td.num,th.num{text-align:right}
.up{color:var(--bad);font-weight:600}
.down{color:var(--good);font-weight:600}
.cav{display:block;margin-top:3px;font-size:11.5px;color:var(--warn);
background:var(--warnbg);border-left:2px solid var(--warn);
padding:3px 7px;border-radius:0 3px 3px 0}
.math{font-size:12.5px;color:var(--muted);padding:10px 24px;background:#fafbfc}
.math b{color:var(--ink)}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px 20px;font-size:13px}
.facts div span{display:block;color:var(--muted);font-size:11px;
text-transform:uppercase;letter-spacing:.04em}
.foot{font-size:11.5px;color:var(--muted);max-width:860px;margin:0 auto;
padding:0 4px 20px}
"""


def _label(score: float) -> str:
    if not np.isfinite(score):
        return "not scored"
    if score <= 3:
        return "favourable"
    if score <= 5:
        return "near average"
    if score <= 7:
        return "elevated"
    return "adverse"


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "&mdash;"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    if isinstance(v, (float, np.floating)):
        return f"{v:,.4g}"
    return html.escape(str(v))


def _money(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "&mdash;"
    return f"${f:,.0f}" if np.isfinite(f) else "&mdash;"


_PRETTY = {
    "total_loss_cost": "Total loss cost", "indemnity_loss_cost": "Indemnity loss cost",
    "expense_loss_cost": "Expense loss cost", "total_frequency": "Total frequency",
    "indemnity_frequency": "Indemnity frequency", "total_severity": "Total severity",
    "actual_loss_ratio": "Actual loss ratio", "loss_free_years": "Loss-free years",
    "limits_to_premium": "Limits to premium", "premium_volume": "Premium volume",
    "excess_primary": "Excess / primary", "per_occ_limit": "Per-occurrence limit",
    "aggregate_limit": "Aggregate limit", "risk_count": "Risk count",
    "specialty_tier": "Specialty tier", "state_venue": "State venue",
    "years_since_grad": "Years since graduation", "rvu_ratio": "Work RVU ratio",
    "tenure": "Tenure with MAG", "hospital_rating": "Hospital rating",
    "practice_size": "Practice size", "physician_age": "Physician age",
    "income_inequality": "County income inequality", "pop_density": "Population density",
    "violent_crime": "Violent crime rate", "pct_uninsured": "Percent uninsured",
}


def render_card(row: pd.Series, cm: ColumnMap, contrib: pd.Series,
                ew: pd.Series, caveats: dict[str, str], top_n: int = 4) -> str:
    composite = pd.to_numeric(pd.Series([row.get(cm.composite_score)]),
                              errors="coerce").iloc[0]

    name = _fmt(row.get(cm.npi) or row.get(cm.risk_id) or "unidentified")
    spec = _fmt(row.get("OL_RISK_SPECIALTY_DESC"))
    st = _fmt(row.get("ST"))
    pol = _fmt(row.get(cm.policy_id))
    yr = _fmt(row.get(cm.coverage_year))

    parts = ["<div class='card'>",
             "<div class='head'><div>",
             f"<p class='who'>NPI {name}</p>",
             f"<div class='sub'>{spec} &nbsp;&middot;&nbsp; {st} "
             f"&nbsp;&middot;&nbsp; policy {pol} &nbsp;&middot;&nbsp; CY {yr}</div>",
             "</div>",
             f"<div class='badge'><div class='n'>{_fmt(composite)}</div>",
             f"<div class='l'>{_label(composite)}</div></div></div>"]

    # Component strip
    parts.append("<div class='comps'>")
    for comp, w in cm.component_weights.items():
        col = cm.component_scores.get(comp, "")
        val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
        realised = sum(float(ew.get(v.name, 0.0)) for v in cm.by_component(comp))
        parts.append(
            f"<div class='comp'><div class='k'>{comp}</div>"
            f"<div class='v'>{_fmt(val)}</div>"
            f"<div class='w'>{realised:.0%} of this score "
            f"(nominal {w:.0%})</div></div>")
    parts.append("</div>")

    # Drivers
    c = contrib.dropna().sort_values()
    up = c[c > 0.01].tail(top_n).iloc[::-1]
    down = c[c < -0.01].head(top_n)

    for title, series, cls in (("Pushing the score up", up, "up"),
                               ("Pulling the score down", down, "down")):
        if series.empty:
            continue
        parts.append(f"<div class='sec'><h3>{title}</h3><table>"
                     "<tr><th>Driver</th><th>Value</th><th class='num'>Score</th>"
                     "<th class='num'>Weight</th><th class='num'>Points</th></tr>")
        for var, pts in series.items():
            v = next((x for x in cm.variables if x.name == var), None)
            raw = row.get(v.raw_col) if v and v.raw_col in row.index else None
            sc = pd.to_numeric(pd.Series([row.get(v.score_col)]),
                               errors="coerce").iloc[0] if v else np.nan
            cav = caveats.get(var, "")
            cav_html = f"<span class='cav'>{html.escape(cav)}</span>" if cav else ""
            parts.append(
                f"<tr><td>{_PRETTY.get(var, var)}{cav_html}</td>"
                f"<td>{_fmt(raw)}</td><td class='num'>{_fmt(sc)}</td>"
                f"<td class='num'>{float(ew.get(var, 0)):.0%}</td>"
                f"<td class='num {cls}'>{pts:+.2f}</td></tr>")
        parts.append("</table></div>")

    # Policy facts
    facts = [("Written premium", _money(row.get(cm.exposure_premium))),
             ("Per-occurrence limit", _fmt(row.get("TOP_PER_M"))),
             ("Aggregate limit", _fmt(row.get("TOP_AGG_M"))),
             ("Credibility Z", _fmt(row.get(cm.credibility_z))),
             ("Reported claims", _fmt(row.get(cm.target_claim_count))),
             ("Reported loss", _money(row.get(cm.target_loss)))]
    parts.append("<div class='sec'><h3>Policy</h3><div class='facts'>")
    for k, v in facts:
        parts.append(f"<div><span>{k}</span>{v}</div>")
    parts.append("</div></div>")

    total = float(c.sum())
    parts.append(
        f"<div class='math'>Anchor <b>{ANCHOR}</b> "
        f"{'+' if total >= 0 else '&minus;'} <b>{abs(total):.2f}</b> "
        f"of weighted driver deviation = <b>{ANCHOR + total:.2f}</b>, "
        f"rounded to <b>{_fmt(composite)}</b>. "
        "Every driver above is a share of that deviation; they sum exactly.</div>")
    parts.append("</div>")
    return "".join(parts)


def render(df: pd.DataFrame, cm: ColumnMap, path: Path,
           limit: int = 25, top_n: int = 4) -> Path:
    """Render up to `limit` cards into one standalone HTML file."""
    d = df.head(limit).copy()
    contrib = attribute(d, cm)
    ew = effective_weights(d, cm)
    caveat_cols = {v.name: _quality_flag(d, cm, v.name) for v in cm.variables
                   if v.name in contrib.columns}

    body = []
    for i in d.index:
        cav = {k: (s.loc[i] if i in s.index else "") for k, s in caveat_cols.items()}
        cav = {k: v for k, v in cav.items() if v}
        body.append(render_card(d.loc[i], cm, contrib.loc[i], ew.loc[i], cav, top_n))

    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>Physician PAS cards</title><style>{_CSS}</style></head><body>"
           + "".join(body)
           + "<p class='foot'>PAS is a decision aid. It has not been validated as "
             "a predictor of loss, and its specialty and state tiers are derived "
             "from portfolio loss ratio, which reflects rate adequacy as well as "
             "risk. Drivers flagged above rest on unknown or redistributed data. "
             "Underwriting judgment governs.</p>"
           "</body></html>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc)
    return path
