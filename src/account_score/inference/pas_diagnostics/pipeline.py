"""
One code path for the CLI and the notebook.

Before this existed, cli.py orchestrated the checks inline, which meant a notebook
would have had to reimplement that orchestration and the two would drift. Both
now call `run_pipeline`.

Typical notebook use:

    from pas_diagnostics import pipeline
    from pas_diagnostics.config import DiagnosticConfig
    from pas_diagnostics.schema import ColumnMap

    cfg = DiagnosticConfig(input_path="scores.csv", nrows=50_000)
    cm  = ColumnMap()
    df  = pipeline.load_data(cfg)

    pipeline.resolve_schema(df, cm)        # what resolved, what didn't
    pipeline.suggest_column_map(df, cm)    # fuzzy guesses for the misses

    res = pipeline.run_pipeline(cfg, cm, df)
    res.blockers()
    res.table("variable_signal")
"""

from __future__ import annotations

import difflib
import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import checks, report
from .config import DiagnosticConfig
from .schema import ColumnMap


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_data(cfg: DiagnosticConfig, path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path or cfg.input_path or "")
    if not p.exists():
        raise FileNotFoundError(
            f"{p}\nSet cfg.input_path to the scored output "
            "(physician_scores_*.csv).")
    if p.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
        if cfg.nrows:
            df = df.head(cfg.nrows)
    else:
        df = pd.read_csv(p, nrows=cfg.nrows, low_memory=False)
    if cfg.verbose:
        print(f"loaded {p.name}: {len(df):,} rows x {len(df.columns)} columns")
    return df


def hash_file(path: str | Path, limit: int = 64 * 1024 * 1024) -> str:
    h, read = hashlib.sha256(), 0
    with Path(path).open("rb") as fh:
        while read < limit:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            read += len(chunk)
    return h.hexdigest()[:16]


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unavailable"


# ---------------------------------------------------------------------------
# Schema resolution
# ---------------------------------------------------------------------------

def resolve_schema(df: pd.DataFrame, cm: ColumnMap) -> pd.DataFrame:
    """Which expected columns exist? Returns a frame you can eyeball or filter.

    Do this before trusting any metric. The column names in schema.py are
    transcribed from the design workbook, not read off the pipeline output, so
    misses are expected on a first run.
    """
    cols = set(df.columns)
    rows = []
    for label, col in [("composite_score", cm.composite_score),
                       ("target_loss", cm.target_loss),
                       ("exposure_premium", cm.exposure_premium),
                       ("exposure_bce", cm.exposure_bce),
                       ("claim_count", cm.target_claim_count),
                       ("coverage_year", cm.coverage_year),
                       ("credibility_z", cm.credibility_z)]:
        rows.append({"kind": "required", "variable": label, "component": "",
                     "weight": np.nan, "column": col, "found": col in cols,
                     "role": "key"})
    for comp, col in cm.component_scores.items():
        rows.append({"kind": "component", "variable": comp, "component": comp,
                     "weight": cm.component_weights.get(comp, np.nan),
                     "column": col, "found": col in cols, "role": "score"})
    for v in cm.variables:
        rows.append({"kind": "variable", "variable": v.name, "component": v.component,
                     "weight": v.weight, "column": v.raw_col,
                     "found": v.raw_col in cols, "role": "raw"})
        rows.append({"kind": "variable", "variable": v.name, "component": v.component,
                     "weight": v.weight, "column": v.score_col,
                     "found": v.score_col in cols, "role": "score"})
    return pd.DataFrame(rows)


def suggest_column_map(df: pd.DataFrame, cm: ColumnMap,
                       cutoff: float = 0.55, n: int = 3) -> pd.DataFrame:
    """Fuzzy-match unresolved expected columns against what's actually present.

    This is the highest-friction step in a first run, so it's worth automating.
    Suggestions are string similarity only -- they have no idea what the columns
    *mean*. Read every one before accepting it. A plausible-looking match to the
    wrong column produces confidently wrong diagnostics.
    """
    present = list(df.columns)
    upper = {c.upper(): c for c in present}
    rows = []

    def _suggest(expected: str) -> list[str]:
        hits = difflib.get_close_matches(expected.upper(), list(upper), n=n,
                                         cutoff=cutoff)
        out = [upper[h] for h in hits]
        # Token overlap catches renames that edit distance misses, e.g.
        # SCORE_TOTAL_LOSS_COST vs PAS_TOTAL_LOSS_COST_SCORE.
        toks = {t for t in expected.upper().replace("-", "_").split("_") if len(t) > 2}
        if toks:
            scored = []
            for c in present:
                ct = {t for t in c.upper().replace("-", "_").split("_") if len(t) > 2}
                if ct:
                    j = len(toks & ct) / len(toks | ct)
                    if j >= 0.4:
                        scored.append((j, c))
            for _, c in sorted(scored, reverse=True)[:n]:
                if c not in out:
                    out.append(c)
        return out[:n]

    for v in cm.variables:
        for role, col in (("raw", v.raw_col), ("score", v.score_col)):
            if col in df.columns:
                continue
            s = _suggest(col)
            rows.append({"variable": v.name, "role": role, "expected": col,
                         "weight": v.weight, "component": v.component,
                         "suggestion_1": s[0] if len(s) > 0 else None,
                         "suggestion_2": s[1] if len(s) > 1 else None,
                         "suggestion_3": s[2] if len(s) > 2 else None})

    for label, col in [("composite_score", cm.composite_score),
                       ("target_loss", cm.target_loss),
                       ("exposure_premium", cm.exposure_premium),
                       ("claim_count", cm.target_claim_count),
                       ("coverage_year", cm.coverage_year)]:
        if col not in df.columns:
            s = _suggest(col)
            rows.append({"variable": label, "role": "key", "expected": col,
                         "weight": np.nan, "component": "required",
                         "suggestion_1": s[0] if len(s) > 0 else None,
                         "suggestion_2": s[1] if len(s) > 1 else None,
                         "suggestion_3": s[2] if len(s) > 2 else None})
    return pd.DataFrame(rows)


def apply_overrides(cm: ColumnMap, overrides: dict[str, dict[str, str]]) -> ColumnMap:
    """Patch a ColumnMap in place from a nested dict.

        apply_overrides(cm, {
            "total_loss_cost": {"score_col": "PAS_TOTAL_LOSS_COST_SCORE"},
            "_keys": {"composite_score": "PAS_SCORE", "coverage_year": "POL_YEAR"},
        })
    """
    for key, val in overrides.get("_keys", {}).items():
        if not hasattr(cm, key):
            raise AttributeError(f"ColumnMap has no attribute {key!r}")
        setattr(cm, key, val)
    by_name = {v.name: v for v in cm.variables}
    for name, fields in overrides.items():
        if name == "_keys":
            continue
        if name not in by_name:
            raise KeyError(f"unknown variable {name!r}; "
                           f"expected one of {sorted(by_name)}")
        for f, val in fields.items():
            if f not in {"raw_col", "score_col", "weight", "component",
                         "higher_is_worse", "target_derived", "categorical"}:
                raise AttributeError(f"cannot override {f!r}")
            setattr(by_name[name], f, val)
    return cm


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    findings: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    config: DiagnosticConfig | None = None
    column_map: ColumnMap | None = None
    target_col: str = ""
    exposure_col: str = ""

    def table(self, name: str) -> pd.DataFrame:
        if name not in self.tables:
            raise KeyError(f"no table {name!r}. Available: {sorted(self.tables)}")
        return self.tables[name]

    def findings_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"severity": f.severity, "check": f.check,
             "subject": f.subject, "message": f.message}
            for f in checks.sort_findings(self.findings)])

    def blockers(self) -> pd.DataFrame:
        d = self.findings_df()
        return d[d["severity"] == "BLOCKER"].reset_index(drop=True) if not d.empty else d

    def counts(self) -> pd.Series:
        d = self.findings_df()
        if d.empty:
            return pd.Series(dtype=int)
        order = ["BLOCKER", "HIGH", "MEDIUM", "INFO"]
        return (d["severity"].value_counts()
                .reindex(order).dropna().astype(int))

    def bands(self, variable: str) -> pd.DataFrame:
        return self.table(f"bands_{variable}")

    def write(self, outdir: str | Path | None = None) -> dict[str, Path]:
        cfg = self.config or DiagnosticConfig()
        out = Path(outdir or cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        if cfg.write_csvs:
            report.write_csvs(self.tables, out / "tables")
            written["tables"] = out / "tables"
        if cfg.write_markdown:
            written["markdown"] = report.write_markdown(
                self.findings, self.tables, self.meta, out / "DIAGNOSTIC_REPORT.md")
        if cfg.write_excel:
            xl = report.write_excel(self.tables, out / "pas_diagnostics.xlsx")
            if xl:
                written["excel"] = xl
        cfg.dump(out / "run_config.json")
        written["config"] = out / "run_config.json"
        return written


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

def prepare(cfg: DiagnosticConfig, cm: ColumnMap,
            df: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    """Resolve the target, coerce numerics, drop unusable exposure."""
    exposure_col = (cm.exposure_premium if cfg.target_basis == "loss_ratio"
                    else cm.exposure_bce)
    target_col = cm.target_loss
    for col, label in ((target_col, "target_loss"), (exposure_col, "exposure")):
        if col not in df.columns:
            raise KeyError(
                f"{label} column {col!r} not in data. Run resolve_schema() and "
                "suggest_column_map(), then apply_overrides().")

    d = df.copy()
    d[target_col] = pd.to_numeric(d[target_col], errors="coerce").fillna(0.0)
    d[exposure_col] = pd.to_numeric(d[exposure_col], errors="coerce")
    if cfg.drop_nonpositive_exposure:
        before = len(d)
        d = d[d[exposure_col] > 0].copy()
        if cfg.verbose and len(d) < before:
            print(f"dropped {before - len(d):,} rows with non-positive exposure "
                  f"({exposure_col})")

    if d.empty:
        raise ValueError(
            f"No rows remain: the frame is empty after filtering on "
            f"{exposure_col} > 0 (started with {len(df):,} rows). Either the "
            f"exposure column is wrong -- check resolve_schema() -- or every "
            f"value is zero, null, or non-numeric. Set "
            f"cfg.drop_nonpositive_exposure=False to inspect the raw data.")
    return d, target_col, exposure_col


def run_pipeline(cfg: DiagnosticConfig, cm: ColumnMap | None = None,
                 df: pd.DataFrame | None = None) -> PipelineResult:
    """Run every check. Returns a PipelineResult; writing is a separate step."""
    cm = cm or ColumnMap.load(cfg.column_map_path)
    if df is None:
        df = load_data(cfg)

    # Thresholds live on the config; checks reads them from module state so that
    # every check sees one consistent set without threading cfg through a dozen
    # signatures.
    checks.set_config(cfg)

    d, target_col, exposure_col = prepare(cfg, cm, df)
    count_col = cm.target_claim_count if cm.target_claim_count in d.columns else None

    tables: dict[str, pd.DataFrame] = {}
    findings: list = []

    def step(label, fn, *a, **kw):
        if cfg.verbose:
            print(f"  {label}")
        return fn(*a, **kw)

    if cfg.verbose:
        print("running checks")

    t, f = step("schema", checks.check_schema, d, cm)
    tables["schema"] = t; findings += f

    t, f = step("data quality", checks.check_data_quality, d, cm)
    tables["data_quality"] = t; findings += f

    t, f = step("adequacy reality", checks.check_adequacy_is_experience, d, cm)
    tables["adequacy_reality"] = t; findings += f

    t, f = step("circularity", checks.check_circularity, d, cm,
                d[target_col], d[exposure_col])
    tables["circularity"] = t; findings += f

    sig, band_tables, f = step("variable signal", checks.check_variable_signal,
                               d, cm, target_col, exposure_col, count_col,
                               cfg.min_exposure_share)
    tables["variable_signal"] = sig; findings += f
    for name, bt in band_tables.items():
        tables[f"bands_{name}"] = bt

    t, f = step("discrimination", checks.check_discrimination, d, cm,
                cfg.tie_threshold)
    tables["discrimination"] = t; findings += f

    t, f = step("effective weights", checks.check_effective_weights, d, cm)
    tables["effective_weights"] = t; findings += f

    vif, corr, f = step("redundancy", checks.check_redundancy, d, cm)
    tables["vif"] = vif
    tables["score_correlation"] = corr.reset_index().rename(columns={"index": "score"})
    findings += f

    lift, f = step("composite lift", checks.check_composite_lift, d, cm,
                   target_col, exposure_col, cfg.train_years, cfg.test_years,
                   count_col)
    findings += f
    for k, v in lift.items():
        tables["lift_summary" if k == "summary" else f"lift_{k}"] = v

    t, f = step("stability", checks.check_stability, d, cm)
    tables["stability"] = t; findings += f

    meta = {
        "input_file": str(cfg.input_path),
        "input_sha256_prefix": (hash_file(cfg.input_path)
                                if cfg.input_path and Path(cfg.input_path).exists()
                                else "n/a"),
        "rows_scored": f"{len(d):,}",
        "rows_loaded": f"{len(df):,}",
        "target_numerator": target_col,
        "target_denominator": exposure_col,
        "target_basis": cfg.target_basis,
        "train_years": list(cfg.train_years) if cfg.train_years else "not split",
        "test_years": list(cfg.test_years) if cfg.test_years else "not split",
        "column_map": cfg.column_map_path or "package defaults",
        "min_exposure_share": cfg.min_exposure_share,
        "n_permutations": cfg.n_permutations,
        "git_sha": git_sha(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        **{f"note_{k}": v for k, v in cfg.notes.items()},
    }

    res = PipelineResult(tables=tables, findings=findings, meta=meta, config=cfg,
                         column_map=cm, target_col=target_col,
                         exposure_col=exposure_col)
    if cfg.verbose:
        print()
        print(res.counts().to_string() or "no findings")
    return res
