"""
Statistics for PAS validation. Deliberately pandas + numpy only.

No scikit-learn, no statsmodels. Corporate Python environments often lag on
those, and every quantity here is a dozen lines of numpy. Nothing should block
this harness from running on a locked-down machine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# np.trapz was removed in numpy 2.0 in favour of np.trapezoid. MagMutual may be
# on either, so bind once at import rather than guessing.
_trapezoid = getattr(np, "trapezoid", None) or np.trapz  # type: ignore[attr-defined]


def _clean(x: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = np.isfinite(x) & np.isfinite(w) & (w > 0)
    return x[m], w[m]


def safe_spearman(a, b) -> float:
    """Spearman rank correlation that returns NaN instead of warning.

    scipy (via pandas) emits ConstantInputWarning when either input is constant,
    which happens routinely on real data: a variable with one populated band, or
    a year with zero reported loss. The correlation genuinely is undefined there,
    so return NaN quietly rather than spraying warnings through a notebook.
    """
    x = pd.Series(a, dtype="float64").reset_index(drop=True)
    y = pd.Series(b, dtype="float64").reset_index(drop=True)
    m = x.notna() & y.notna()
    x, y = x[m], y[m]
    if len(x) < 3 or x.nunique() < 2 or y.nunique() < 2:
        return float("nan")
    return float(x.corr(y, method="spearman"))


def weighted_mean(x, w) -> float:
    x, w = _clean(np.asarray(x, float), np.asarray(w, float))
    if w.sum() == 0:
        return np.nan
    return float(np.sum(x * w) / np.sum(w))


def weighted_quantile(x, w, q: float) -> float:
    """Exposure-weighted quantile. q in [0, 1]."""
    x, w = _clean(np.asarray(x, float), np.asarray(w, float))
    if x.size == 0:
        return np.nan
    order = np.argsort(x)
    x, w = x[order], w[order]
    cw = np.cumsum(w) - 0.5 * w
    cw /= np.sum(w)
    return float(np.interp(q, cw, x))


def gini(actual, exposure, score) -> float:
    """Exposure-weighted Gini of `actual` when ordered by `score`.

    Interpretation for a risk score: 0 = the score carries no information about
    loss; higher = better separation. Sign matters. A negative Gini means the
    score is ordering loss *backwards* -- your 10s are better risks than your
    1s -- which is the single most important thing this harness can tell you.

    Note this is the Gini of the score's ability to sort loss, not the Gini of
    the loss distribution itself. It is bounded by the Gini achievable by a
    perfect ordering, so read it comparatively (variable A vs B, year 1 vs 2),
    not against an absolute benchmark.
    """
    a = np.asarray(actual, float)
    e = np.asarray(exposure, float)
    s = np.asarray(score, float)
    m = np.isfinite(a) & np.isfinite(e) & np.isfinite(s) & (e > 0)
    a, e, s = a[m], e[m], s[m]
    if a.size < 2 or e.sum() == 0 or a.sum() == 0:
        return np.nan

    # Ascending score = ascending predicted risk. Ties broken by actual so the
    # measure is not inflated by arbitrary within-band ordering.
    order = np.lexsort((a, s))
    a, e = a[order], e[order]

    cum_e = np.cumsum(e) / np.sum(e)
    cum_a = np.cumsum(a) / np.sum(a)
    # Trapezoidal area between the Lorenz curve and the diagonal, doubled.
    area = _trapezoid(cum_a, cum_e)
    return float(2.0 * (0.5 - area))


def lorenz_curve(actual, exposure, score, n_points: int = 100) -> pd.DataFrame:
    """Cumulative exposure vs cumulative loss, ordered by score ascending."""
    a = np.asarray(actual, float)
    e = np.asarray(exposure, float)
    s = np.asarray(score, float)
    m = np.isfinite(a) & np.isfinite(e) & np.isfinite(s) & (e > 0)
    a, e, s = a[m], e[m], s[m]
    if a.size == 0:
        return pd.DataFrame(columns=["cum_exposure", "cum_loss"])
    order = np.lexsort((a, s))
    cum_e = np.cumsum(e[order]) / np.sum(e)
    cum_a = np.cumsum(a[order]) / np.sum(a) if a.sum() else np.zeros_like(cum_e)
    idx = np.unique(np.linspace(0, cum_e.size - 1, n_points).astype(int))
    return pd.DataFrame({"cum_exposure": cum_e[idx], "cum_loss": cum_a[idx]})


def somers_d(score, actual, exposure=None, bins: int = 10) -> float:
    """Rank correlation between an ordinal score and a continuous outcome.

    Computed on binned means rather than pairwise, which is O(bins^2) instead
    of O(n^2) -- important at 40k physicians x 8 years. Returns a value in
    [-1, 1]; positive means higher score goes with higher loss.
    """
    s = np.asarray(score, float)
    a = np.asarray(actual, float)
    w = np.ones_like(a) if exposure is None else np.asarray(exposure, float)
    m = np.isfinite(s) & np.isfinite(a) & np.isfinite(w) & (w > 0)
    s, a, w = s[m], a[m], w[m]
    if s.size < 2 or np.unique(s).size < 2:
        return np.nan

    df = pd.DataFrame({"s": s, "a": a, "w": w})
    grp = df.groupby("s", observed=True).apply(
        lambda g: pd.Series({
            "mean": weighted_mean(g["a"], g["w"]),
            "w": g["w"].sum(),
        }),
        include_groups=False,
    ).reset_index()
    grp = grp.dropna()
    if len(grp) < 2:
        return np.nan

    conc = disc = 0.0
    lv = grp.to_numpy()
    for i in range(len(lv)):
        for j in range(i + 1, len(lv)):
            wij = lv[i, 2] * lv[j, 2]
            if lv[j, 1] > lv[i, 1]:
                conc += wij
            elif lv[j, 1] < lv[i, 1]:
                disc += wij
    total = conc + disc
    return float((conc - disc) / total) if total else np.nan


def band_summary(
    df: pd.DataFrame,
    score_col: str,
    loss_col: str,
    exposure_col: str,
    count_col: str | None = None,
) -> pd.DataFrame:
    """Per-band exposure, loss, and loss ratio. The core deployment table.

    An honest deployment table needs the loss ratio column the current design
    omits. Without it a band boundary is just a number.
    """
    cols = [score_col, loss_col, exposure_col] + ([count_col] if count_col else [])
    d = df[[c for c in cols if c in df.columns]].copy()
    d = d[np.isfinite(d[score_col].astype(float))]
    if d.empty:
        return pd.DataFrame()

    agg = {"records": (score_col, "size"),
           "exposure": (exposure_col, "sum"),
           "loss": (loss_col, "sum")}
    if count_col and count_col in d.columns:
        agg["claims"] = (count_col, "sum")

    out = d.groupby(score_col, observed=True).agg(**agg).reset_index()
    out = out.rename(columns={score_col: "score"})
    out["loss_ratio"] = np.where(out["exposure"] > 0,
                                 out["loss"] / out["exposure"], np.nan)
    total_lr = out["loss"].sum() / out["exposure"].sum() if out["exposure"].sum() else np.nan
    out["relativity"] = out["loss_ratio"] / total_lr
    out["exposure_share"] = out["exposure"] / out["exposure"].sum()
    if "claims" in out.columns:
        out["frequency"] = np.where(out["exposure"] > 0,
                                    out["claims"] / out["exposure"], np.nan)
    return out.sort_values("score").reset_index(drop=True)


def monotonicity(bands: pd.DataFrame, value_col: str = "loss_ratio",
                 min_exposure_share: float = 0.005,
                 n_permutations: int = 2000,
                 seed: int = 20260727) -> dict:
    """How well does loss increase across score bands?

    Bands holding less than `min_exposure_share` of exposure are excluded --
    a band with 12 policies will violate monotonicity by noise alone and tells
    you nothing.

    Critically, this also returns a permutation p-value. With only 5-10 bands,
    a band-level rank correlation of +/-0.9 arises by chance more often than
    intuition suggests, so an unguarded harness reports noise as "inverted" and
    loses the reader's trust on its first real run. `p_value` is the share of
    random band orderings achieving a |rho| at least this large; treat anything
    above 0.05 as "no evidence of ordering", in either direction.

    Returns spearman, p_value, violations (adjacent pairs going the wrong way),
    and worst_violation (largest backward step in loss-ratio points).
    """
    empty = {"spearman": np.nan, "p_value": np.nan, "violations": np.nan,
             "n_bands": 0, "worst_violation": np.nan}
    if bands.empty or value_col not in bands.columns:
        return empty

    b = bands[bands["exposure_share"] >= min_exposure_share].dropna(subset=[value_col])
    b = b.sort_values("score")
    if len(b) < 3:
        return empty | {"n_bands": len(b)}

    v = b[value_col].to_numpy(float)
    s = b["score"].to_numpy(float)
    rho = safe_spearman(s, v)

    # Permutation test: how often does a random ordering of these band values
    # produce a correlation at least this extreme?
    rng = np.random.default_rng(seed)
    if np.isfinite(rho):
        ranks = pd.Series(s).rank().to_numpy(float)
        vr = pd.Series(v).rank().to_numpy(float)
        null = np.empty(n_permutations)
        for i in range(n_permutations):
            null[i] = np.corrcoef(ranks, rng.permutation(vr))[0, 1]
        p = float((np.abs(null) >= abs(rho) - 1e-12).mean())
    else:
        p = np.nan

    diffs = np.diff(v)
    return {"spearman": rho, "p_value": p,
            "violations": int((diffs < 0).sum()),
            "n_bands": int(len(b)),
            "worst_violation": float(diffs.min()) if diffs.size else np.nan}


def variance_inflation(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """VIF via numpy least squares. VIF > 5 is redundancy; > 10 is severe.

    Run this on the score columns, not the raw drivers. Four Adequacy
    variables (total / indemnity / expense loss cost, and loss ratio) share a
    numerator or denominator by construction, so they should light up here.
    """
    use = [c for c in cols if c in df.columns]
    X = df[use].apply(pd.to_numeric, errors="coerce").dropna()
    if X.shape[0] < 50 or X.shape[1] < 2:
        return pd.DataFrame(columns=["variable", "vif", "r_squared"])

    rows = []
    Xv = X.to_numpy(float)
    for i, col in enumerate(use):
        y = Xv[:, i]
        others = np.delete(Xv, i, axis=1)
        A = np.column_stack([np.ones(len(others)), others])
        try:
            beta, *_ = np.linalg.lstsq(A, y, rcond=None)
            resid = y - A @ beta
            ss_res = float(np.sum(resid ** 2))
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
            vif = 1.0 / (1.0 - r2) if (r2 is not np.nan and r2 < 0.9999) else np.inf
        except np.linalg.LinAlgError:
            r2, vif = np.nan, np.nan
        rows.append({"variable": col, "vif": vif, "r_squared": r2})
    return pd.DataFrame(rows).sort_values("vif", ascending=False).reset_index(drop=True)


def population_stability_index(base: pd.Series, compare: pd.Series,
                               bins: int = 10) -> float:
    """PSI between two score distributions. >0.10 shifting, >0.25 unstable.

    Use this year over year. Because PAS band widths are recomputed from the
    portfolio mean on every run, the score distribution can move without any
    physician changing -- PSI is how you detect that.
    """
    b = pd.to_numeric(base, errors="coerce").dropna()
    c = pd.to_numeric(compare, errors="coerce").dropna()
    if b.empty or c.empty:
        return np.nan
    edges = np.unique(np.quantile(b, np.linspace(0, 1, bins + 1)))
    if edges.size < 3:
        return np.nan
    bh = np.histogram(b, bins=edges)[0].astype(float)
    ch = np.histogram(c, bins=edges)[0].astype(float)
    bp = np.clip(bh / bh.sum(), 1e-6, None)
    cp = np.clip(ch / ch.sum(), 1e-6, None)
    return float(np.sum((cp - bp) * np.log(cp / bp)))
