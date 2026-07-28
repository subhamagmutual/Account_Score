"""
Adversarial tests. The point is to break things, not to confirm the happy path.

Real data will hit every one of these: a variable that is entirely null, a
coverage year with three records, a filtered frame with a non-contiguous index,
a specialty with one policy in it. Run with:

    python test_edges.py
"""

from __future__ import annotations

import sys
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pas_diagnostics import card, checks, metrics, pipeline, reasons, report
from pas_diagnostics.config import DiagnosticConfig
from pas_diagnostics.schema import ColumnMap

PASS, FAIL = [], []


def check(name):
    def deco(fn):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                fn()
            PASS.append(name)
        except Exception as e:
            FAIL.append((name, f"{type(e).__name__}: {e}",
                         traceback.format_exc(limit=4)))
        return fn
    return deco


def tiny_frame(n=400, seed=1) -> pd.DataFrame:
    """Minimal but structurally valid scored output."""
    rng = np.random.default_rng(seed)
    cm = ColumnMap()
    d = pd.DataFrame(index=range(n))
    d[cm.policy_id] = [f"P{i:04d}" for i in range(n)]
    d[cm.risk_id] = rng.integers(1, 200, n)
    d[cm.npi] = rng.integers(10**9, 2 * 10**9, n)
    d[cm.coverage_year] = rng.choice([2017, 2018, 2019, 2022, 2023], n)
    d[cm.exposure_premium] = rng.lognormal(9, 1, n).round(0)
    d[cm.exposure_bce] = rng.lognormal(0.5, 0.6, n).round(3)
    d[cm.target_claim_count] = rng.poisson(0.08, n)
    d[cm.target_loss] = d[cm.target_claim_count] * rng.lognormal(11, 1.2, n)
    d[cm.credibility_z] = rng.uniform(0.2, 1.0, n).round(3)
    d["OL_RISK_SPECIALTY_DESC"] = rng.choice(["A", "B", "C", "D"], n)
    d["ST"] = rng.choice(["GA", "FL", "NC"], n)
    for v in cm.variables:
        d[v.raw_col] = rng.uniform(0, 10, n).round(3)
        d[v.score_col] = rng.integers(1, 11, n).astype(float)
    for comp, col in cm.component_scores.items():
        d[col] = rng.uniform(1, 10, n).round(2)
    d[cm.composite_score] = rng.integers(1, 11, n).astype(float)
    return d


BASE = DiagnosticConfig(verbose=False)


# ---------------------------------------------------------------------------

@check("empty frame after exposure filter raises a clear error")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d[cm.exposure_premium] = 0.0          # everything filtered out
    try:
        pipeline.run_pipeline(BASE, cm, d)
    except ValueError as e:
        assert "no rows" in str(e).lower() or "empty" in str(e).lower(), \
            f"error message unhelpful: {e}"
        return
    raise AssertionError("expected a ValueError, got a completed run")


@check("all-NaN variable does not crash any check")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d["SCORE_RVU_RATIO"] = np.nan
    d["RVU_WORK_TOTAL_RATIO_SPEC_OL"] = np.nan
    res = pipeline.run_pipeline(BASE, cm, d)
    assert "variable_signal" in res.tables


@check("entirely missing component does not crash")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    for v in cm.by_component("environment"):
        d[v.score_col] = np.nan
    res = pipeline.run_pipeline(BASE, cm, d)
    ew = reasons.effective_weights(d, cm)
    tot = ew.sum(axis=1)
    assert np.allclose(tot[tot > 0], 1.0, atol=1e-9), \
        f"weights should renormalise to 1, got {tot.unique()[:5]}"


@check("non-contiguous index survives reason codes and cards")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d = d[d[cm.coverage_year] != 2018]          # gaps in the index
    rc = reasons.reason_codes(d, cm, top_n=3)
    assert not rc.empty
    assert set(rc["record"]).issubset(set(d.index))
    card.render(d, cm, Path("/tmp/t_idx.html"), limit=5)


@check("duplicate index does not crash card rendering")
def _():
    d = tiny_frame(200)
    cm = ColumnMap()
    d = pd.concat([d, d])                      # duplicate index labels
    card.render(d, cm, Path("/tmp/t_dup.html"), limit=6)
    reasons.reason_codes(d, cm, top_n=2)


@check("constant target yields NaN not a crash")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d[cm.target_loss] = 0.0                    # zero loss everywhere
    res = pipeline.run_pipeline(BASE, cm, d)
    sig = res.table("variable_signal")
    assert sig["gini"].isna().all() or (sig["gini"].abs() < 1e-9).all()


@check("single-value score column reports zero usable bands")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d["SCORE_PER_OCC_LIMIT"] = 4.0             # every record identical
    res = pipeline.run_pipeline(BASE, cm, d)
    disc = res.table("discrimination")
    row = disc[disc["variable"] == "per_occ_limit"].iloc[0]
    assert row["largest_band_share"] == 1.0
    assert abs(row["effective_bands"] - 1.0) < 1e-9


@check("out-of-time split with too few records is handled")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    cfg = BASE.replace(train_years=(2017,), test_years=(1999,))
    res = pipeline.run_pipeline(cfg, cm, d)
    msgs = " ".join(res.findings_df()["message"])
    assert "insufficient" in msgs.lower() or "no out-of-time" in msgs.lower()


@check("missing composite score is a blocker, not a crash")
def _():
    d = tiny_frame()
    cm = ColumnMap()
    d = d.drop(columns=[cm.composite_score])
    res = pipeline.run_pipeline(BASE, cm, d)
    assert not res.blockers().empty


@check("missing target column raises KeyError with guidance")
def _():
    d = tiny_frame().drop(columns=[ColumnMap().target_loss])
    try:
        pipeline.run_pipeline(BASE, ColumnMap(), d)
    except KeyError as e:
        assert "resolve_schema" in str(e), f"unhelpful message: {e}"
        return
    raise AssertionError("expected KeyError")


@check("monotonicity on a constant series returns NaN quietly")
def _():
    b = pd.DataFrame({"score": [1, 2, 3, 4, 5],
                      "loss_ratio": [0.5] * 5,
                      "exposure_share": [0.2] * 5})
    out = metrics.monotonicity(b, n_permutations=50)
    assert np.isnan(out["spearman"]), out


@check("gini with zero total loss returns NaN")
def _():
    g = metrics.gini([0, 0, 0, 0], [1, 1, 1, 1], [1, 2, 3, 4])
    assert np.isnan(g), g


@check("gini sign is correct for a known ordering")
def _():
    # score ascending with loss ascending -> positive
    good = metrics.gini([1, 2, 3, 40], [1, 1, 1, 1], [1, 2, 3, 4])
    bad = metrics.gini([40, 3, 2, 1], [1, 1, 1, 1], [1, 2, 3, 4])
    assert good > 0 > bad, (good, bad)


@check("weighted_quantile matches numpy on equal weights")
def _():
    x = np.arange(1, 101, dtype=float)
    w = np.ones_like(x)
    for q in (0.05, 0.5, 0.95):
        a = metrics.weighted_quantile(x, w, q)
        b = np.quantile(x, q)
        assert abs(a - b) < 1.0, (q, a, b)


@check("vif handles a perfectly collinear pair")
def _():
    d = pd.DataFrame({"a": np.arange(200.0)})
    d["b"] = d["a"] * 2.0
    d["c"] = np.random.default_rng(0).normal(size=200)
    out = metrics.variance_inflation(d, ["a", "b", "c"])
    assert np.isinf(out["vif"].max()) or out["vif"].max() > 1e6, out


@check("psi on identical distributions is ~0")
def _():
    s = pd.Series(np.random.default_rng(0).normal(size=5000))
    assert abs(metrics.population_stability_index(s, s)) < 1e-6


@check("attribution reconciles exactly when no credibility blending")
def _():
    cm = ColumnMap()
    d = tiny_frame(600)
    # Rebuild the composite the way the package attributes it.
    ew = reasons.effective_weights(d, cm)
    contrib = pd.DataFrame(index=d.index)
    for v in cm.variables:
        s = pd.to_numeric(d[v.score_col], errors="coerce")
        contrib[v.name] = ew[v.name] * (s - reasons.ANCHOR).fillna(0.0)
    d[cm.composite_score] = reasons.ANCHOR + contrib.sum(axis=1)
    rec = reasons.reconciliation(d, cm)
    assert rec["max_abs_residual"].iloc[0] < 1e-9, rec.to_dict("records")


@check("triage handles an all-NaN contribution row")
def _():
    cm = ColumnMap()
    d = tiny_frame(300)
    for v in cm.variables:                      # wipe every score on row 0
        d.loc[0, v.score_col] = np.nan
    tq = reasons.triage(d, cm, cm.exposure_premium, top_n=20)
    assert isinstance(tq, pd.DataFrame)


@check("dispersion handles an empty composite")
def _():
    cm = ColumnMap()
    d = tiny_frame(100)
    d[cm.composite_score] = np.nan
    tab, notes = reasons.dispersion(d, cm)
    assert tab.empty and notes


@check("config round-trips through JSON")
def _():
    cfg = BASE.replace(train_years=(2017, 2018), test_years=(2022,),
                       notes={"x": "y"}, p_value_threshold=0.01)
    p = Path("/tmp/t_cfg.json")
    cfg.dump(p)
    back = DiagnosticConfig.load(p)
    assert back.train_years == (2017, 2018), back.train_years
    assert back.p_value_threshold == 0.01
    assert back.notes == {"x": "y"}


@check("invalid target_basis is rejected at construction")
def _():
    try:
        DiagnosticConfig(target_basis="nonsense")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


@check("set_config actually changes check behaviour")
def _():
    d = tiny_frame(800)
    cm = ColumnMap()
    lo = pipeline.run_pipeline(BASE.replace(tie_threshold=0.01), cm, d)
    hi = pipeline.run_pipeline(BASE.replace(tie_threshold=0.99), cm, d)
    n_lo = (lo.findings_df()["check"] == "discrimination").sum()
    n_hi = (hi.findings_df()["check"] == "discrimination").sum()
    assert n_lo > n_hi, (n_lo, n_hi)


@check("column map overrides validate unknown names")
def _():
    cm = ColumnMap()
    try:
        pipeline.apply_overrides(cm, {"not_a_variable": {"score_col": "X"}})
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown variable")
    try:
        pipeline.apply_overrides(cm, {"_keys": {"not_an_attr": "X"}})
    except AttributeError:
        return
    raise AssertionError("expected AttributeError for unknown key")


@check("suggest_column_map finds an obvious rename")
def _():
    cm = ColumnMap()
    d = tiny_frame(120).rename(
        columns={"SCORE_TOTAL_LOSS_COST": "PAS_TOTAL_LOSS_COST_SCORE"})
    sug = pipeline.suggest_column_map(d, cm)
    row = sug[sug["expected"] == "SCORE_TOTAL_LOSS_COST"]
    assert not row.empty, "no suggestion row emitted"
    cands = row[["suggestion_1", "suggestion_2", "suggestion_3"]].iloc[0].tolist()
    assert "PAS_TOTAL_LOSS_COST_SCORE" in cands, cands


@check("report writers handle empty and NaN-laden tables")
def _():
    tables = {"a": pd.DataFrame(), "b": pd.DataFrame({"x": [np.nan, 1.0]}),
              "c": None}
    out = Path("/tmp/t_rep")
    report.write_csvs(tables, out)
    report.write_markdown([], tables, {"k": "v"}, out / "R.md")
    assert (out / "R.md").exists()


@check("full pipeline is deterministic across runs")
def _():
    d = tiny_frame(700)
    cm = ColumnMap()
    a = pipeline.run_pipeline(BASE, cm, d).table("variable_signal")
    b = pipeline.run_pipeline(BASE, ColumnMap(), d).table("variable_signal")
    pd.testing.assert_frame_equal(a, b)


@check("gini reaches its ceiling on a perfect ordering")
def _():
    n = 1000
    exp = np.ones(n)
    loss = np.zeros(n); loss[-100:] = 1.0      # worst 10% carry all the loss
    perfect = np.arange(n)
    # Ceiling here is 0.9, not 1.0: with all loss in the worst decile, the best
    # achievable Lorenz curve is bounded by that concentration.
    assert abs(metrics.gini(loss, exp, perfect) - 0.9) < 1e-9
    # The reversed case lands on -0.89999 rather than exactly -0.9. That is
    # O(1/n) trapezoidal discretisation, not an asymmetry in the metric: the
    # first point of the Lorenz curve contributes a half-trapezoid. Tolerance is
    # set accordingly rather than papered over.
    assert abs(metrics.gini(loss, exp, perfect[::-1]) + 0.9) < 1e-3


@check("somers_d is +1 / -1 / nan on monotone, reversed, flat")
def _():
    s = np.repeat(np.arange(1, 11), 100)
    a = np.repeat(np.arange(1, 11), 100) * 1.0
    assert abs(metrics.somers_d(s, a) - 1.0) < 1e-9
    assert abs(metrics.somers_d(s, a[::-1]) + 1.0) < 1e-9
    assert np.isnan(metrics.somers_d(s, np.ones(1000)))


@check("safe_spearman returns nan rather than warning on constant input")
def _():
    assert np.isnan(metrics.safe_spearman([1, 1, 1, 1], [1, 2, 3, 4]))
    assert np.isnan(metrics.safe_spearman([1, 2, 3], [5, 5, 5]))
    assert abs(metrics.safe_spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9


@check("monotonicity p-value is well-behaved at the extremes")
def _():
    strong = pd.DataFrame({"score": range(1, 11),
                           "loss_ratio": np.arange(0.1, 1.1, 0.1),
                           "exposure_share": [0.1] * 10})
    out = metrics.monotonicity(strong, n_permutations=2000)
    assert out["spearman"] > 0.99 and out["p_value"] < 0.01, out
    assert out["violations"] == 0


@check("cli --inspect exits 0 on a resolvable file")
def _():
    import subprocess, tempfile
    d = tiny_frame(300)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "s.csv"
        d.to_csv(f, index=False)
        r = subprocess.run([sys.executable, "-m", "pas_diagnostics",
                            "--input", str(f), "--inspect"],
                           capture_output=True, text=True,
                           cwd=Path(__file__).resolve().parent)
        assert r.returncode == 0, f"exit {r.returncode}\n{r.stdout[-800:]}"


@check("cli exits 3 when blockers are present")
def _():
    import subprocess, tempfile
    d = tiny_frame(400)
    d = d.drop(columns=[ColumnMap().composite_score])   # guarantees a blocker
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "s.csv"
        d.to_csv(f, index=False)
        r = subprocess.run([sys.executable, "-m", "pas_diagnostics",
                            "--input", str(f), "--outdir", td, "--quiet"],
                           capture_output=True, text=True,
                           cwd=Path(__file__).resolve().parent)
        assert r.returncode == 3, f"exit {r.returncode}\n{r.stdout[-800:]}"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed\n")
    for n in PASS:
        print(f"  ok    {n}")
    if FAIL:
        print()
        for n, msg, tb in FAIL:
            print(f"  FAIL  {n}\n        {msg}")
        print("\n" + "=" * 70)
        for n, msg, tb in FAIL:
            print(f"\n### {n}\n{tb}")
    sys.exit(1 if FAIL else 0)
