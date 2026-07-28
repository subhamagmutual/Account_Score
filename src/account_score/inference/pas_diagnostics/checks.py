"""
Diagnostic checks for the Physician MPL PAS.

Each check returns a tidy DataFrame plus a list of Findings. A Finding has a
severity so the report can lead with what actually blocks production.

Ordering is deliberate: schema and data quality run first, because everything
downstream is meaningless if the columns are not what the design says they are.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from . import metrics
from .config import DiagnosticConfig
from .schema import (
    ColumnMap,
    DOCUMENTED_SPEC,
    GENERIC_SENTINELS,
    PLAUSIBLE_RANGE,
    SENTINELS,
)

Severity = Literal["BLOCKER", "HIGH", "MEDIUM", "INFO"]

# Thresholds come from DiagnosticConfig. pipeline.run_pipeline() calls
# set_config() before running; a bare import keeps documented defaults so the
# module stays usable standalone.
CFG = DiagnosticConfig()


def set_config(cfg: DiagnosticConfig) -> None:
    """Point every check at one set of thresholds."""
    global CFG
    CFG = cfg


@dataclass
class Finding:
    severity: Severity
    check: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} / {self.subject}: {self.message}"


_ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (_ORDER[f.severity], f.check, f.subject))


# ---------------------------------------------------------------------------
# 1. Schema
# ---------------------------------------------------------------------------

def check_schema(df: pd.DataFrame, cm: ColumnMap) -> tuple[pd.DataFrame, list[Finding]]:
    rows, findings = [], []
    cols = set(df.columns)

    for v in cm.variables:
        raw_ok = v.raw_col in cols
        score_ok = v.score_col in cols
        rows.append({
            "variable": v.name, "component": v.component, "weight": v.weight,
            "raw_col": v.raw_col, "raw_present": raw_ok,
            "score_col": v.score_col, "score_present": score_ok,
        })
        if not score_ok and not raw_ok:
            findings.append(Finding(
                "HIGH", "schema", v.name,
                f"neither raw ({v.raw_col}) nor score ({v.score_col}) column found; "
                "variable cannot be validated"))
        elif not score_ok:
            findings.append(Finding(
                "MEDIUM", "schema", v.name,
                f"raw column present but score column {v.score_col} missing"))

    for label, col in [("composite", cm.composite_score),
                       ("target loss", cm.target_loss),
                       ("exposure premium", cm.exposure_premium)]:
        if col not in cols:
            findings.append(Finding(
                "BLOCKER", "schema", label,
                f"required column {col} not in output; supply --column-map"))

    present = sum(r["score_present"] for r in rows)
    findings.append(Finding(
        "INFO", "schema", "coverage",
        f"{present}/{len(rows)} expected score columns located; "
        f"{len(cols)} columns total in file"))
    return pd.DataFrame(rows), findings


# ---------------------------------------------------------------------------
# 2. Data quality: missing, sentinels, range, spec drift
# ---------------------------------------------------------------------------

def check_data_quality(df: pd.DataFrame, cm: ColumnMap) -> tuple[pd.DataFrame, list[Finding]]:
    rows, findings = [], []

    for v in cm.variables:
        if v.raw_col not in df.columns:
            continue
        s = df[v.raw_col]
        num = pd.to_numeric(s, errors="coerce")
        numeric = num.notna().sum() > 0.5 * s.notna().sum()

        non_null_pct = 100.0 * s.notna().mean()
        zero_pct = 100.0 * (num == 0).mean() if numeric else np.nan

        sent_vals = SENTINELS.get(v.raw_col, GENERIC_SENTINELS)
        sent_mask = num.isin(sent_vals) if numeric else pd.Series(False, index=s.index)
        sent_pct = 100.0 * sent_mask.mean()

        lo, hi = PLAUSIBLE_RANGE.get(v.raw_col, (-np.inf, np.inf))
        oor = int(((num < lo) | (num > hi)).sum()) if numeric else 0

        row = {"variable": v.name, "raw_col": v.raw_col,
               "non_null_pct": round(non_null_pct, 2),
               "zero_pct": round(zero_pct, 2) if numeric else None,
               "sentinel_pct": round(sent_pct, 3),
               "out_of_range_n": oor}
        if numeric:
            row |= {"median": num.median(),
                    "p5": num.quantile(0.05), "p95": num.quantile(0.95)}
        rows.append(row)

        # --- Sentinel scored as a real value -------------------------------
        # CV_LOSS_FREE_YEARS = -99 means "unknown" but the documented bins put
        # "0 or negative" in score 10. Missing data becomes the worst risk.
        if sent_pct > 0 and v.score_col in df.columns:
            sc = pd.to_numeric(df.loc[sent_mask, v.score_col], errors="coerce")
            scored = sc.notna().sum()
            if scored:
                mean_sc = sc.mean()
                sev = "BLOCKER" if mean_sc >= 8 else "HIGH"
                findings.append(Finding(
                    sev, "sentinel_scored", v.name,
                    f"{scored:,} records ({sent_pct:.2f}%) hold a sentinel value "
                    f"{sorted(set(num[sent_mask].unique()))} yet received a score "
                    f"(mean {mean_sc:.2f}). Unknown data is being priced as "
                    f"{'the worst risk in the book' if mean_sc >= 8 else 'a real measurement'}. "
                    "Convert sentinels to NaN before binning so weight-zeroing handles them."))

        if oor:
            findings.append(Finding(
                "MEDIUM", "range", v.name,
                f"{oor:,} values outside plausible range [{lo}, {hi}]"))

        # --- Drift from the documented design ------------------------------
        spec = DOCUMENTED_SPEC.get(v.raw_col)
        if spec and numeric:
            for stat, expected in spec.items():
                actual = {"median": num.median(),
                          "p5": num.quantile(0.05),
                          "p95": num.quantile(0.95),
                          "non_null_pct": non_null_pct,
                          "zero_pct": zero_pct}.get(stat)
                if actual is None or not np.isfinite(actual):
                    continue
                denom = max(abs(expected), 1e-9)
                if abs(actual - expected) / denom > CFG.spec_drift_tolerance:
                    findings.append(Finding(
                        "MEDIUM", "spec_drift", v.name,
                        f"{stat} is {actual:,.4g}, design workbook documents "
                        f"{expected:,.4g} (>{CFG.spec_drift_tolerance:.0%} apart). Either the data moved or "
                        "the design doc is stale -- reconcile before the UW review."))

    return pd.DataFrame(rows), findings


# ---------------------------------------------------------------------------
# 3. Is Adequacy actually measuring loss experience?
# ---------------------------------------------------------------------------

def check_adequacy_is_experience(
    df: pd.DataFrame, cm: ColumnMap
) -> tuple[pd.DataFrame, list[Finding]]:
    """The most important check in this file.

    93% of physician-years have zero claims. Any variable that genuinely
    measures a physician's own loss experience must therefore be zero (or
    undefined) for roughly 93% of records. A variable that is 100% non-null,
    0% zero, and tightly centred near 1.0 is not loss experience -- it is a
    burn factor, an on-level factor, or an actual-to-expected ratio.

    Adequacy is 40% of the composite. If it is built from burn factors, the
    composite contains almost no physician-specific loss signal, and the
    executive deck's description of it is wrong.
    """
    rows, findings = [], []

    claim_col = cm.target_claim_count
    observed_zero_share = np.nan
    if claim_col in df.columns:
        cc = pd.to_numeric(df[claim_col], errors="coerce")
        observed_zero_share = float((cc.fillna(0) <= 0).mean())
        findings.append(Finding(
            "INFO", "adequacy_reality", "claim_free_share",
            f"{observed_zero_share:.1%} of records have zero claims "
            f"({claim_col}). Loss-experience variables should be near-degenerate "
            "at zero for a similar share."))
    else:
        observed_zero_share = CFG.expected_zero_claim_share
        findings.append(Finding(
            "MEDIUM", "adequacy_reality", "claim_free_share",
            f"{claim_col} not found; falling back to the documented "
            f"{CFG.expected_zero_claim_share:.0%} claim-free share."))

    for v in cm.by_component("adequacy"):
        if v.raw_col not in df.columns:
            continue
        num = pd.to_numeric(df[v.raw_col], errors="coerce")
        if num.notna().sum() < 100:
            continue

        zero_share = float((num == 0).mean())
        non_null = float(num.notna().mean())
        med = float(num.median())
        p5, p95 = float(num.quantile(0.05)), float(num.quantile(0.95))
        spread = (p95 - p5) / abs(med) if med else np.inf

        # A loss-experience variable is zero-inflated. A burn factor is not.
        looks_like_burn = (
            zero_share < CFG.burn_factor_max_zero_share
            and non_null > CFG.burn_factor_min_non_null
            and np.isfinite(spread) and spread < CFG.burn_factor_max_spread
        )
        rows.append({
            "variable": v.name, "raw_col": v.raw_col, "weight": v.weight,
            "zero_share": round(zero_share, 4), "non_null": round(non_null, 4),
            "median": med, "p5": p5, "p95": p95,
            "relative_spread": round(spread, 3) if np.isfinite(spread) else None,
            "expected_zero_share": round(observed_zero_share, 4),
            "flag": "NOT_LOSS_EXPERIENCE" if looks_like_burn else "plausible",
        })

        if looks_like_burn:
            findings.append(Finding(
                "BLOCKER", "adequacy_reality", v.name,
                f"only {zero_share:.1%} of records are zero and the distribution is "
                f"tight (median {med:.4g}, p5-p95 {p5:.4g}-{p95:.4g}), yet "
                f"{observed_zero_share:.0%} of physicians are claim-free. This is not "
                f"the physician's loss experience -- it looks like a burn / on-level "
                f"factor. It carries {v.weight:.0%} of the Adequacy component. "
                "Confirm what this column actually contains before anyone prices off it."))

    out = pd.DataFrame(rows)
    if not out.empty:
        flagged = out.loc[out["flag"] == "NOT_LOSS_EXPERIENCE", "weight"].sum()
        total = out["weight"].sum()
        if flagged > 0 and total > 0:
            share = flagged / total
            findings.append(Finding(
                "BLOCKER", "adequacy_reality", "component_total",
                f"{share:.0%} of Adequacy weight sits on variables that do not look "
                f"like loss experience. Adequacy is {cm.component_weights['adequacy']:.0%} "
                f"of the composite, so roughly "
                f"{share * cm.component_weights['adequacy']:.0%} of the score may carry "
                "no physician-specific loss signal at all."))
    return out, findings


# ---------------------------------------------------------------------------
# 4. Circularity: were the bands cut on the target?
# ---------------------------------------------------------------------------

def check_circularity(
    df: pd.DataFrame, cm: ColumnMap, target: pd.Series, exposure: pd.Series
) -> tuple[pd.DataFrame, list[Finding]]:
    """Detect variables whose score was derived from the outcome.

    Specialty Risk Tier and State/Venue Risk were both cut on portfolio LOSS
    RATIO. Two consequences, and the second is worse than the first:

      1. Validating the score against loss ratio is circular. Lift is
         guaranteed and means nothing.

      2. Loss ratio is loss / premium, and premium already reflects the class
         plan's specialty and territory factors. A specialty with LR 1.5 is a
         specialty you are UNDERPRICING, not necessarily a risky one. Raise its
         rate and its tier improves with no change in underlying risk. The
         variable measures your own pricing error.

    The fix is to tier on loss cost per exposure (pure premium), which is
    rate-independent. ULT_Total_LOSS_COST_PER_BCE already exists.
    """
    rows, findings = [], []
    work = pd.DataFrame({"_target": target.to_numpy(float),
                         "_exposure": exposure.to_numpy(float)},
                        index=df.index)

    for v in cm.variables:
        if v.score_col not in df.columns or v.raw_col not in df.columns:
            continue
        d = work.copy()
        d["_score"] = pd.to_numeric(df[v.score_col], errors="coerce")
        d["_level"] = df[v.raw_col]
        d = d[np.isfinite(d["_target"]) & np.isfinite(d["_exposure"])
              & (d["_exposure"] > 0) & d["_score"].notna()]
        if d["_level"].nunique() < 3 or len(d) < 200:
            continue

        # Level-wise loss ratio vs the score assigned to that level.
        g = d.groupby("_level", observed=True).agg(
            loss=("_target", "sum"), exposure=("_exposure", "sum"),
            score=("_score", "median"), records=("_score", "size")).reset_index()
        g = g[g["records"] >= CFG.min_level_records]
        if len(g) < 4:
            continue
        g["loss_ratio"] = g["loss"] / g["exposure"]
        r = metrics.safe_spearman(g["score"], g["loss_ratio"])

        rows.append({"variable": v.name, "levels_tested": len(g),
                     "rank_corr_score_vs_level_LR": round(r, 4),
                     "declared_target_derived": v.target_derived})

        if v.target_derived:
            findings.append(Finding(
                "BLOCKER", "circularity", v.name,
                f"bands were cut on portfolio loss ratio (rank corr {r:.2f} with "
                f"level LR, {len(g)} levels). Carries {v.weight:.0%} of "
                f"{v.component}. Exclude from any lift claim, and re-tier on loss "
                "cost per exposure so the variable measures risk rather than your "
                "own rate adequacy."))
        elif np.isfinite(r) and abs(r) > CFG.circularity_corr_threshold:
            findings.append(Finding(
                "HIGH", "circularity", v.name,
                f"not declared target-derived, but its score tracks level loss ratio "
                f"at rank corr {r:.2f} across {len(g)} levels. Verify the bands were "
                "not fit on the outcome."))

    return pd.DataFrame(rows), findings


# ---------------------------------------------------------------------------
# 5. Per-variable signal: monotonicity, Somers' D, Gini
# ---------------------------------------------------------------------------

def check_variable_signal(
    df: pd.DataFrame, cm: ColumnMap, target_col: str, exposure_col: str,
    count_col: str | None = None, min_exposure_share: float = 0.005,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[Finding]]:
    rows, tables, findings = [], {}, []

    for v in cm.variables:
        if v.score_col not in df.columns:
            continue
        bands = metrics.band_summary(df, v.score_col, target_col, exposure_col, count_col)
        if bands.empty:
            continue
        tables[v.name] = bands

        mono = metrics.monotonicity(bands, "loss_ratio", min_exposure_share,
                                   CFG.n_permutations, CFG.permutation_seed)
        d = metrics.somers_d(df[v.score_col], df[target_col], df[exposure_col])
        g = metrics.gini(df[target_col], df[exposure_col], df[v.score_col])

        rows.append({
            "variable": v.name, "component": v.component, "weight": v.weight,
            "target_derived": v.target_derived,
            "bands_used": mono["n_bands"], "spearman": mono["spearman"],
            "p_value": mono["p_value"], "violations": mono["violations"],
            "worst_violation": mono["worst_violation"],
            "somers_d": d, "gini": g,
        })

        if v.target_derived:
            continue  # lift is circular; already flagged

        rho, pval = mono["spearman"], mono["p_value"]
        nb = mono["n_bands"]
        if not np.isfinite(rho):
            continue

        # Only claim direction when the permutation test supports it. Otherwise
        # the honest finding is "no evidence", which is still actionable: a
        # variable carrying real weight while contributing nothing.
        if np.isfinite(pval) and pval > CFG.p_value_threshold:
            findings.append(Finding(
                "HIGH", "signal", v.name,
                f"no evidence of any ordering of loss (spearman {rho:+.2f}, "
                f"permutation p={pval:.2f} across {nb} bands). Carries "
                f"{v.weight:.0%} of {v.component} while adding noise. With only "
                f"{nb} bands this is what an uninformative variable looks like -- "
                "it is not evidence of inversion either."))
        elif rho < CFG.inversion_threshold:
            findings.append(Finding(
                "BLOCKER", "signal", v.name,
                f"score is INVERTED: loss ratio falls as the score rises "
                f"(spearman {rho:+.2f}, p={pval:.3f}, {nb} bands). Your 10s are "
                f"better risks than your 1s. Check the direction of "
                f"higher_is_worse={v.higher_is_worse}."))
        elif rho < CFG.weak_signal_threshold:
            findings.append(Finding(
                "HIGH", "signal", v.name,
                f"weak ordering of loss (spearman {rho:+.2f}, p={pval:.3f}, "
                f"{mono['violations']} adjacent violations across {nb} bands). "
                f"Carries {v.weight:.0%} of {v.component}."))

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values("spearman", na_position="last").reset_index(drop=True)
    return summary, tables, findings


# ---------------------------------------------------------------------------
# 6. Discrimination: can the bands actually separate the book?
# ---------------------------------------------------------------------------

def check_discrimination(
    df: pd.DataFrame, cm: ColumnMap, tie_threshold: float = 0.50
) -> tuple[pd.DataFrame, list[Finding]]:
    """Find variables where most of the book lands in one or a few bands.

    Two known cases from the design workbook:
      - Per-Occurrence Limit: 77% of policies sit at exactly $1M, and $1M is
        mapped to bands 3, 4 AND 5. Three-quarters of the book is tied, on a
        variable carrying 20% of Capacity.
      - Hospital Rating: 5 distinct star values spread across 10 bands, 59%
        missing. Effectively a 5-level variable at 5% weight.
    """
    rows, findings = [], []
    for v in cm.variables:
        if v.score_col not in df.columns:
            continue
        sc = pd.to_numeric(df[v.score_col], errors="coerce").dropna()
        if sc.empty:
            continue
        shares = sc.value_counts(normalize=True).sort_values(ascending=False)
        top_share = float(shares.iloc[0])
        distinct = int(sc.nunique())
        # Effective number of bands actually in use (inverse Simpson).
        eff = float(1.0 / np.sum(shares.to_numpy() ** 2))
        rows.append({"variable": v.name, "weight": v.weight,
                     "distinct_bands": distinct,
                     "effective_bands": round(eff, 2),
                     "largest_band_share": round(top_share, 4),
                     "largest_band": float(shares.index[0])})

        if top_share >= tie_threshold:
            findings.append(Finding(
                "HIGH", "discrimination", v.name,
                f"{top_share:.0%} of records receive the same score "
                f"({shares.index[0]:.0f}); only {eff:.1f} of 10 bands are effectively "
                f"in use. The variable carries {v.weight:.0%} of {v.component} but "
                "cannot differentiate most of the book."))
        elif eff < CFG.min_effective_bands:
            findings.append(Finding(
                "MEDIUM", "discrimination", v.name,
                f"only {eff:.1f} effective bands in use across {distinct} distinct "
                "scores; binning is coarser in practice than on paper."))
    out = pd.DataFrame(rows)
    if out.empty:
        # No scored records at all -- nothing to rank. Returning an empty frame
        # keeps the caller's .sort_values() from raising KeyError on a missing
        # column that was never created.
        return out, findings
    return out.sort_values("largest_band_share", ascending=False), findings


# ---------------------------------------------------------------------------
# 7. Effective weights after weight-zeroing
# ---------------------------------------------------------------------------

def check_effective_weights(
    df: pd.DataFrame, cm: ColumnMap
) -> tuple[pd.DataFrame, list[Finding]]:
    """Nominal weights are not realised weights.

    When a sub-score is missing its weight is zeroed and redistributed. With
    Hospital Rating 59% missing and RVU 24% missing, the *typical* physician is
    scored on a different weighting than the design states -- and a new-business
    submission has no Adequacy at all, so 40% redistributes silently. The deck
    presents one set of weights; the book experiences another.
    """
    rows, findings = [], []
    for comp, comp_w in cm.component_weights.items():
        vs = [v for v in cm.by_component(comp) if v.score_col in df.columns]
        if not vs:
            continue
        avail = {}
        for v in vs:
            avail[v.name] = pd.to_numeric(df[v.score_col], errors="coerce").notna()
        avail_df = pd.DataFrame(avail)
        w = np.array([v.weight for v in vs], float)
        names = [v.name for v in vs]

        # Row-wise renormalised weight, averaged over the book.
        A = avail_df.to_numpy(float)
        denom = A @ w
        with np.errstate(divide="ignore", invalid="ignore"):
            realised = np.where(denom[:, None] > 0, A * w / denom[:, None], np.nan)
        # A variable absent from every record leaves an all-NaN column, and
        # np.nanmean warns "Mean of empty slice" on it. Compute the mean only
        # over columns that have at least one value.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_realised = np.nanmean(realised, axis=0)
        mean_realised = np.nan_to_num(mean_realised, nan=0.0)

        for name, nominal, real, col in zip(names, w, mean_realised, avail_df.columns):
            present = float(avail_df[col].mean())
            nominal_norm = nominal / w.sum()
            rows.append({
                "component": comp, "variable": name,
                "nominal_weight_in_component": round(nominal_norm, 4),
                "present_pct": round(100 * present, 2),
                "realised_weight_in_component": round(float(real), 4),
                "drift": round(float(real) - nominal_norm, 4),
                "nominal_weight_in_composite": round(nominal_norm * comp_w, 4),
            })
            if present < CFG.present_pct_threshold:
                findings.append(Finding(
                    "HIGH", "effective_weights", name,
                    f"present for only {present:.0%} of records. Nominal "
                    f"{nominal_norm:.0%} of {comp}, realised {real:.0%} on average. "
                    "The remaining weight silently redistributes to whatever else "
                    "happens to be populated."))

        zero_adequacy = None
        if comp == "adequacy":
            zero_adequacy = float((denom == 0).mean())
            if zero_adequacy > 0.01:
                findings.append(Finding(
                    "HIGH", "effective_weights", "adequacy_absent",
                    f"{zero_adequacy:.1%} of records have NO Adequacy sub-score at all. "
                    f"For those, {comp_w:.0%} of the composite redistributes to "
                    "Capacity/Appetite/Environment while still being labelled 1-10 on "
                    "the same scale. Publish a separate prospective score instead."))
    return pd.DataFrame(rows), findings


# ---------------------------------------------------------------------------
# 8. Redundancy
# ---------------------------------------------------------------------------

def check_redundancy(
    df: pd.DataFrame, cm: ColumnMap
) -> tuple[pd.DataFrame, pd.DataFrame, list[Finding]]:
    findings = []
    cols = [v.score_col for v in cm.variables if v.score_col in df.columns]
    vif = metrics.variance_inflation(df, cols)

    num = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = num.corr(method="spearman")

    name_of = {v.score_col: v.name for v in cm.variables}
    vif = vif.assign(variable=vif["variable"].map(name_of).fillna(vif["variable"]))

    for _, r in vif.iterrows():
        if np.isfinite(r["vif"]) and r["vif"] > CFG.vif_severe:
            findings.append(Finding(
                "HIGH", "redundancy", str(r["variable"]),
                f"VIF {r['vif']:.1f} (R^2 {r['r_squared']:.3f} against the other "
                "scores) -- almost entirely explained by its siblings. Its weight is "
                "being double-counted."))
        elif np.isfinite(r["vif"]) and r["vif"] > CFG.vif_moderate:
            findings.append(Finding(
                "MEDIUM", "redundancy", str(r["variable"]),
                f"VIF {r['vif']:.1f}; substantially overlapping with other scores."))

    # Explicit pairwise report for near-duplicates
    seen = set()
    for a in corr.columns:
        for b in corr.columns:
            if a >= b or (a, b) in seen:
                continue
            seen.add((a, b))
            rho = corr.loc[a, b]
            if np.isfinite(rho) and abs(rho) > CFG.pairwise_corr_threshold:
                findings.append(Finding(
                    "MEDIUM", "redundancy", f"{name_of.get(a, a)} ~ {name_of.get(b, b)}",
                    f"rank correlation {rho:+.2f}; these are close to the same "
                    "variable carrying two weights."))
    return vif, corr, findings


# ---------------------------------------------------------------------------
# 9. Composite lift, in-time and out-of-time
# ---------------------------------------------------------------------------

def check_composite_lift(
    df: pd.DataFrame, cm: ColumnMap, target_col: str, exposure_col: str,
    train_years: tuple[int, ...] | None = None,
    test_years: tuple[int, ...] | None = None,
    count_col: str | None = None,
) -> tuple[dict[str, pd.DataFrame], list[Finding]]:
    out, findings = {}, []
    score_col = cm.composite_score
    if score_col not in df.columns:
        findings.append(Finding("BLOCKER", "lift", "composite",
                                f"{score_col} not found; cannot measure lift"))
        return out, findings

    def _eval(d: pd.DataFrame, label: str) -> float:
        bands = metrics.band_summary(d, score_col, target_col, exposure_col, count_col)
        out[f"bands_{label}"] = bands
        out[f"lorenz_{label}"] = metrics.lorenz_curve(
            d[target_col], d[exposure_col], d[score_col])
        g = metrics.gini(d[target_col], d[exposure_col], d[score_col])
        mono = metrics.monotonicity(bands)
        out.setdefault("summary", pd.DataFrame())
        row = pd.DataFrame([{"split": label, "records": len(d),
                             "gini": g, "spearman": mono["spearman"],
                             "violations": mono["violations"]}])
        out["summary"] = pd.concat([out["summary"], row], ignore_index=True)
        return g

    g_all = _eval(df, "all")

    yr = cm.coverage_year
    if yr in df.columns and train_years and test_years:
        years = pd.to_numeric(df[yr], errors="coerce")
        tr = df[years.isin(train_years)]
        te = df[years.isin(test_years)]
        if len(tr) > 500 and len(te) > 500:
            g_tr = _eval(tr, "train")
            g_te = _eval(te, "test")
            if np.isfinite(g_tr) and np.isfinite(g_te) and g_tr > 0:
                decay = 1.0 - g_te / g_tr
                sev = "HIGH" if decay > 0.5 else "INFO"
                findings.append(Finding(
                    sev, "lift", "out_of_time",
                    f"Gini {g_tr:.3f} in-sample ({min(train_years)}-{max(train_years)}) "
                    f"vs {g_te:.3f} out-of-time ({min(test_years)}-{max(test_years)}), "
                    f"a {decay:.0%} decay. "
                    + ("The score does not hold up on unseen years."
                       if decay > 0.5 else "Holds up reasonably.")))
        else:
            findings.append(Finding("MEDIUM", "lift", "out_of_time",
                                    "insufficient records in the requested split"))
    else:
        findings.append(Finding(
            "MEDIUM", "lift", "out_of_time",
            f"no out-of-time split performed (need {yr} plus --train-years/--test-years). "
            "In-sample lift on a score containing target-derived tiers is not evidence."))

    if np.isfinite(g_all):
        if g_all < 0:
            findings.append(Finding(
                "BLOCKER", "lift", "composite",
                f"composite Gini is NEGATIVE ({g_all:.3f}). The score is sorting loss "
                "backwards across the whole book."))
        elif g_all < 0.10:
            findings.append(Finding(
                "BLOCKER", "lift", "composite",
                f"composite Gini {g_all:.3f} -- effectively no ability to sort loss, "
                "even in-sample and even with target-derived tiers included."))
        else:
            findings.append(Finding(
                "INFO", "lift", "composite",
                f"composite Gini {g_all:.3f} in-sample. Discount this: specialty and "
                "state tiers were cut on the target, so part of this is circular."))
    return out, findings


# ---------------------------------------------------------------------------
# 10. Score stability across years
# ---------------------------------------------------------------------------

def check_stability(df: pd.DataFrame, cm: ColumnMap) -> tuple[pd.DataFrame, list[Finding]]:
    rows, findings = [], []
    yr, sc = cm.coverage_year, cm.composite_score
    if yr not in df.columns or sc not in df.columns:
        return pd.DataFrame(), [Finding(
            "INFO", "stability", "psi",
            "coverage year or composite score missing; PSI not computed")]

    years = sorted(pd.to_numeric(df[yr], errors="coerce").dropna().unique())
    if len(years) < 2:
        return pd.DataFrame(), []

    base_year = years[0]
    base = df.loc[pd.to_numeric(df[yr], errors="coerce") == base_year, sc]
    for y in years[1:]:
        cur = df.loc[pd.to_numeric(df[yr], errors="coerce") == y, sc]
        psi = metrics.population_stability_index(base, cur)
        rows.append({"base_year": base_year, "year": y, "psi": psi,
                     "mean_score": pd.to_numeric(cur, errors="coerce").mean()})
        if np.isfinite(psi) and psi > CFG.psi_unstable:
            findings.append(Finding(
                "HIGH", "stability", str(int(y)),
                f"PSI {psi:.3f} vs {int(base_year)} -- the score distribution has "
                "shifted materially. Because band widths are recomputed from the "
                "portfolio mean each run, part of this may be recalibration rather "
                "than real portfolio movement. Log band widths per run to tell "
                "them apart."))
    return pd.DataFrame(rows), findings
