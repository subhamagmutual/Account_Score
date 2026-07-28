"""
Reason codes: why is this physician a 7?

The decomposition here is *exact*, not approximate. Because the composite is a
weighted average of sub-scores, and every sub-score is anchored so that 4.5
means "portfolio average", the distance from average decomposes cleanly:

    composite - 4.5  ==  sum_i [ effective_weight_i * (score_i - 4.5) ]

Every term is a real number of score points that a named variable pushed the
physician above or below average, and the terms sum to the score. That is worth
more here than SHAP or any permutation-importance scheme: an underwriter can be
shown the arithmetic, and an auditor can reproduce it in Excel.

`effective_weight_i` is the realised weight after weight-zeroing, not the
nominal weight from the deck. Those differ for most physicians -- Hospital
Rating is missing on 59% of records -- so attributing with nominal weights would
produce reason codes that do not add up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import ColumnMap, GENERIC_SENTINELS, SENTINELS

from .config import DiagnosticConfig

# Default anchor. Override per run by passing anchor= to the functions below,
# or by reading it off your DiagnosticConfig.
ANCHOR = DiagnosticConfig().anchor


def effective_weights(df: pd.DataFrame, cm: ColumnMap) -> pd.DataFrame:
    """Realised weight of every variable in the composite, per record.

    Returns a frame of the same length as `df`, one column per variable,
    each row summing to 1.0 across the variables that were actually available.
    """
    out = pd.DataFrame(index=df.index, dtype=float)
    comp_avail = {}

    for comp, comp_w in cm.component_weights.items():
        vs = [v for v in cm.by_component(comp) if v.score_col in df.columns]
        if not vs:
            continue
        w = np.array([v.weight for v in vs], float)
        A = np.column_stack([
            pd.to_numeric(df[v.score_col], errors="coerce").notna().to_numpy()
            for v in vs
        ]).astype(float)
        denom = A @ w
        comp_avail[comp] = denom > 0
        with np.errstate(divide="ignore", invalid="ignore"):
            within = np.where(denom[:, None] > 0, A * w / denom[:, None], 0.0)
        for i, v in enumerate(vs):
            out[v.name] = within[:, i] * comp_w

    # Renormalise across components, since a component can be wholly absent
    # (new business has no Adequacy at all).
    comp_w_avail = np.zeros(len(df))
    for comp, cw in cm.component_weights.items():
        if comp in comp_avail:
            comp_w_avail += np.where(comp_avail[comp], cw, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(comp_w_avail > 0, 1.0 / comp_w_avail, 0.0)
    return out.mul(scale, axis=0)


def attribute(df: pd.DataFrame, cm: ColumnMap) -> pd.DataFrame:
    """Signed score-point contribution of every variable, per record."""
    ew = effective_weights(df, cm)
    contrib = pd.DataFrame(index=df.index, dtype=float)
    for v in cm.variables:
        if v.name not in ew.columns:
            continue
        s = pd.to_numeric(df[v.score_col], errors="coerce")
        contrib[v.name] = ew[v.name] * (s - ANCHOR).fillna(0.0)
    return contrib


def _quality_flag(df: pd.DataFrame, cm: ColumnMap, var_name: str) -> pd.Series:
    """Per-record caveat on a variable: sentinel, missing, or clean.

    This is the reason the card is worth building before the model is fixed.
    A physician whose top adverse driver is 'Loss-Free Years: 10/10' when the
    underlying value is -99 (unknown) is a bug that an underwriter will spot in
    week one -- but only if the card shows them the raw value beside the score.
    Reason codes make the model falsifiable by the people who use it.
    """
    v = next((x for x in cm.variables if x.name == var_name), None)
    if v is None or v.raw_col not in df.columns:
        return pd.Series("", index=df.index)
    raw = df[v.raw_col]
    num = pd.to_numeric(raw, errors="coerce")
    sent = SENTINELS.get(v.raw_col, GENERIC_SENTINELS)
    flag = pd.Series("", index=df.index, dtype=object)
    flag[num.isin(sent)] = "SENTINEL - value unknown, do not rely on this driver"
    flag[raw.isna()] = "MISSING - weight redistributed to other variables"
    if v.target_derived:
        flag[flag == ""] = "TIER CUT ON LOSS RATIO - reflects rate adequacy, not risk"
    return flag


def reason_codes(
    df: pd.DataFrame, cm: ColumnMap, top_n: int = 3
) -> pd.DataFrame:
    """Long-format reason codes: top N drivers up and down, per record.

    Columns: record index, direction, rank, variable, score, raw value,
    effective weight, contribution in score points, and a data-quality caveat.
    """
    contrib = attribute(df, cm)
    ew = effective_weights(df, cm)
    if contrib.empty:
        return pd.DataFrame()

    C = contrib.to_numpy(float)
    names = np.array(contrib.columns)
    order = np.argsort(C, axis=1)          # ascending: most favourable first
    rows = []

    label = {v.name: v for v in cm.variables}
    raw_cache = {v.name: df[v.raw_col] if v.raw_col in df.columns else None
                 for v in cm.variables}
    score_cache = {v.name: pd.to_numeric(df[v.score_col], errors="coerce")
                   if v.score_col in df.columns else None
                   for v in cm.variables}
    flag_cache = {n: _quality_flag(df, cm, n) for n in contrib.columns}

    idx = df.index.to_numpy()
    for direction, take in (("increases_score", order[:, ::-1][:, :top_n]),
                            ("decreases_score", order[:, :top_n])):
        for rank in range(take.shape[1]):
            cols = take[:, rank]
            var = names[cols]
            val = C[np.arange(len(C)), cols]
            rows.append(pd.DataFrame({
                "record": idx,
                "direction": direction,
                "rank": rank + 1,
                "variable": var,
                "component": [label[v].component for v in var],
                "contribution_points": np.round(val, 4),
                "score": [score_cache[v].to_numpy()[i] if score_cache[v] is not None
                          else np.nan for i, v in enumerate(var)],
                "raw_value": [raw_cache[v].to_numpy()[i] if raw_cache[v] is not None
                              else None for i, v in enumerate(var)],
                "effective_weight": [round(float(ew[v].to_numpy()[i]), 4)
                                     for i, v in enumerate(var)],
                "caveat": [flag_cache[v].to_numpy()[i] for i, v in enumerate(var)],
            }))

    out = pd.concat(rows, ignore_index=True)
    # Drop drivers that moved the score by essentially nothing -- listing a
    # 0.001-point "reason" erodes confidence in the ones that matter.
    return out[out["contribution_points"].abs() >= 0.01].sort_values(
        ["record", "direction", "rank"]).reset_index(drop=True)


def reconciliation(df: pd.DataFrame, cm: ColumnMap) -> pd.DataFrame:
    """Prove the attribution is exact.

    Ship this alongside the reason codes. If 4.5 + sum(contributions) does not
    equal the composite, the reason codes are describing a different model than
    the one that produced the score, and no underwriter should trust them.
    """
    contrib = attribute(df, cm)
    rebuilt = ANCHOR + contrib.sum(axis=1)
    actual = pd.to_numeric(df[cm.composite_score], errors="coerce")
    resid = (rebuilt - actual).abs()
    return pd.DataFrame({
        "records": [len(df)],
        "max_abs_residual": [float(resid.max())],
        "mean_abs_residual": [float(resid.mean())],
        "pct_within_0.5": [float((resid <= 0.5).mean() * 100)],
        "note": ["Residual is expected to be non-zero where the pipeline rounds "
                 "the composite to an integer; it should be under 0.5. A larger "
                 "residual means the published weights do not reproduce the "
                 "published score."],
    })


def triage(
    df: pd.DataFrame, cm: ColumnMap, exposure_col: str,
    top_n: int = 250, min_premium: float = 0.0,
) -> pd.DataFrame:
    """Renewal review queue, ranked by score x premium at risk.

    Score alone is the wrong sort order for a work queue: a band-9 physician
    paying $1,200 matters less than a band-6 paying $180,000. Ranking on
    premium-weighted deviation from average puts the underwriter's time where
    the dollars are.
    """
    d = df.copy()
    sc = pd.to_numeric(d[cm.composite_score], errors="coerce")
    prem = pd.to_numeric(d[exposure_col], errors="coerce")
    d["_score"] = sc
    d["_premium"] = prem
    d["premium_at_risk"] = (sc - ANCHOR).clip(lower=0) * prem

    contrib = attribute(d, cm)
    d["top_driver"] = contrib.idxmax(axis=1)
    d["top_driver_points"] = contrib.max(axis=1).round(3)

    keep = [c for c in [cm.policy_id, cm.risk_id, cm.npi, cm.coverage_year,
                        "OL_RISK_SPECIALTY_DESC", "ST"] if c in d.columns]
    out = d.loc[
        (d["_premium"] >= min_premium) & d["_score"].notna(),
        keep + ["_score", "_premium", "premium_at_risk",
                "top_driver", "top_driver_points"]
    ].rename(columns={"_score": "pas_score", "_premium": "written_premium"})

    return out.sort_values("premium_at_risk", ascending=False).head(top_n).reset_index(drop=True)


def dispersion(df: pd.DataFrame, cm: ColumnMap) -> tuple[pd.DataFrame, list[str]]:
    """Can the composite actually populate the high bands?

    Averaging ~23 variables that are each anchored at 4.5 produces a composite
    whose variance collapses toward the anchor -- the central limit theorem
    working against you. If almost nobody scores 8-10, then portfolio targets
    of the form "under 20% in bands 8-10" are unreachable by construction, and
    a triage queue sorted on score has nothing to sort.

    Check this before building any UW workflow on top of the score.
    """
    sc = pd.to_numeric(df[cm.composite_score], errors="coerce").dropna()
    if sc.empty:
        return pd.DataFrame(), ["composite score column is empty"]

    tab = (sc.value_counts(normalize=True).sort_index()
           .rename("share").reset_index())
    tab.columns = ["score", "share"]
    tab["records"] = sc.value_counts().sort_index().to_numpy()
    tab["cumulative"] = tab["share"].cumsum()

    notes = []
    high = float(sc.ge(8).mean())
    low = float(sc.le(3).mean())
    mid = float(sc.between(4, 5).mean())
    notes.append(f"std dev {sc.std():.2f}; bands 4-5 hold {mid:.0%} of the book")
    if high < 0.01:
        notes.append(
            f"only {high:.2%} of physicians score 8 or above. A portfolio target "
            "expressed as a cap on bands 8-10 cannot bind. Either widen the "
            "composite (fewer, stronger variables) or state targets in "
            "percentiles rather than absolute bands.")
    if mid > 0.70:
        notes.append(
            f"{mid:.0%} of the book sits in just two bands, so the score cannot "
            "differentiate most physicians. This is a structural consequence of "
            "averaging many mean-anchored variables, not a data problem.")
    if low < 0.01:
        notes.append(f"only {low:.2%} score 3 or below; the favourable tail is "
                     "equally compressed.")
    return tab, notes
