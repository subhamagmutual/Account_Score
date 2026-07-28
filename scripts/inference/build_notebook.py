"""Emit PAS_Pipeline.ipynb. Run: python build_notebook.py"""

import json
from pathlib import Path

cells = []


def md(src):
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": src.strip("\n").split("\n")})


def code(src):
    lines = src.strip("\n").split("\n")
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": lines})


md(r"""
# Physician MPL PAS — diagnostic pipeline

Everything is driven by the **PARAMETERS** cell below. Change values there, re-run,
never edit the modules to tune a threshold.

## How to work through this

Run cells top to bottom the first time. After that:

1. **Step 1 is not optional.** The column names in `schema.py` are transcribed from
   `Physician_MPL_Account_Score_Design_v2.xlsx`, not read off the pipeline output.
   Expect misses on a first run. If the map is wrong, every metric below is
   confidently wrong.
2. **Step 2 answers the question that decides what's worth building.** If ~90% of
   physicians sit in bands 4–5, the score can't differentiate the book and a triage
   queue has nothing to sort.
3. Steps 3–4 run the checks and let you drill into any one of them.
4. Step 5 is the underwriter-facing output.

## Debugging

Every step leaves its intermediate frame in a variable, so you can inspect it
directly. `res.tables` holds every table by name. If you edit a module, run the
**hot reload** cell rather than restarting the kernel.
""")

md("## Setup")

code(r"""
# --- PARAMETERS -------------------------------------------------------------
# The only cell you should normally need to edit.

PARAMS = dict(
    # --- Data -------------------------------------------------------------
    input_path = r"C:\Box\Box\BOX Subhashree Singh\Business\PAS\physician_scores_20260429_141959.csv",
    output_dir = r"reports/2026-07",
    nrows      = 50_000,   # None for the whole file. Keep small while iterating.

    # --- Target -----------------------------------------------------------
    # 'loss_ratio' divides by on-levelled premium -- what specialty and state
    #   tiers were cut on, which is why those tiers are circular against it.
    # 'loss_cost' divides by BCE exposure and is rate-independent. Use it to
    #   sanity-check any lift claim, and to re-tier.
    target_basis = "loss_ratio",

    # --- Out-of-time split ------------------------------------------------
    train_years = (2017, 2018, 2019, 2020, 2021),
    test_years  = (2022, 2023, 2024),

    # --- Check thresholds -------------------------------------------------
    min_exposure_share = 0.005,   # ignore bands holding less exposure than this
    n_permutations     = 2000,    # monotonicity significance draws
    p_value_threshold  = 0.05,    # above this: "no evidence of ordering"
    tie_threshold      = 0.50,    # flag if this share share one score
    vif_severe         = 10.0,
    present_pct_threshold = 0.80, # flag variables missing on >20% of records

    # --- Reason codes / tooling -------------------------------------------
    reason_top_n     = 3,
    card_limit       = 12,
    triage_top_n     = 250,

    # --- Output -----------------------------------------------------------
    write_csvs = True, write_markdown = True, write_excel = False,
    verbose = True,

    notes = {"analyst": "S. Singh", "purpose": "first validation pass"},
)

# Which variable to drill into in the band-table cell further down.
DRILL_VARIABLE = "total_loss_cost"
""")

code(r"""
import sys, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Make the package importable whether this notebook sits beside pas_diagnostics/
# or one level up from it.
here = Path.cwd()
for cand in (here, here.parent):
    if (cand / "pas_diagnostics" / "__init__.py").exists():
        if str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
        print(f"package root: {cand}")
        break
else:
    raise ImportError(
        "Could not find pas_diagnostics/. Open this notebook from the folder "
        "that contains it, or add that folder to sys.path manually.")

from pas_diagnostics import pipeline, reasons, card, checks, metrics
from pas_diagnostics.config import DiagnosticConfig
from pas_diagnostics.schema import ColumnMap

pd.set_option("display.max_columns", 60)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.4g}")
warnings.filterwarnings("ignore", category=FutureWarning)

cfg = DiagnosticConfig(**PARAMS)
cm  = ColumnMap()
print(f"target basis : {cfg.target_basis}")
print(f"rows to read : {cfg.nrows or 'all'}")
print(f"variables    : {len(cm.variables)}")
""")

code(r"""
# --- HOT RELOAD -------------------------------------------------------------
# Run after editing any module in pas_diagnostics/. Faster than restarting.
import importlib
for m in ("config", "schema", "metrics", "checks", "reasons", "card",
          "report", "pipeline"):
    importlib.reload(importlib.import_module(f"pas_diagnostics.{m}"))
from pas_diagnostics import pipeline, reasons, card, checks, metrics
from pas_diagnostics.config import DiagnosticConfig
from pas_diagnostics.schema import ColumnMap
cfg = DiagnosticConfig(**PARAMS)
print("reloaded")
""")

md(r"""
---
## Step 1 — Resolve the schema

**Do this before trusting any number below.** `found=False` rows need fixing.
""")

code(r"""
df = pipeline.load_data(cfg)
df.head(3)
""")

code(r"""
resolution = pipeline.resolve_schema(df, cm)
missing = resolution[~resolution["found"]]

print(f"{len(missing)} of {len(resolution)} expected columns NOT found\n")
if len(missing):
    display(missing[["kind", "variable", "role", "weight", "column"]])
else:
    print("All expected columns resolved. Proceed to Step 2.")
""")

code(r"""
# Fuzzy suggestions for anything missing. String similarity only -- these have no
# idea what the columns MEAN. Read every one before accepting it; a plausible
# match to the wrong column produces confidently wrong diagnostics.
if len(missing):
    suggestions = pipeline.suggest_column_map(df, cm)
    display(suggestions[["variable", "role", "expected", "weight",
                         "suggestion_1", "suggestion_2", "suggestion_3"]])
else:
    print("nothing to suggest")
""")

code(r"""
# --- COLUMN OVERRIDES ------------------------------------------------------
# Fill in from the suggestions above, then re-run the resolution cell.
# Leave empty if everything resolved.

OVERRIDES = {
    # "total_loss_cost": {"score_col": "PAS_TOTAL_LOSS_COST_SCORE"},
    # "hospital_rating": {"raw_col": "HOSP_STAR_RATING"},
    # "_keys": {"composite_score": "PAS_SCORE", "coverage_year": "POL_YEAR"},
}

if OVERRIDES:
    cm = pipeline.apply_overrides(cm, OVERRIDES)
    resolution = pipeline.resolve_schema(df, cm)
    missing = resolution[~resolution["found"]]
    print(f"after overrides: {len(missing)} still missing")
    if len(missing):
        display(missing[["variable", "role", "column"]])
    # Persist so the CLI and any scheduled run use the same map.
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    cm.dump(Path(cfg.output_dir) / "column_map.json")
    print(f"saved -> {Path(cfg.output_dir) / 'column_map.json'}")
else:
    print("no overrides applied")
""")

md(r"""
---
## Step 2 — Can the composite actually differentiate the book?

Averaging ~23 variables each anchored at 4.5 pulls the composite's variance toward
the anchor. If almost nobody reaches 8–10, then a portfolio target like *"under 20%
in bands 8–10"* cannot bind, and ranking a work queue on score is meaningless.

This is the cheapest high-value check here. Run it before building anything on top
of the score.
""")

code(r"""
dispersion_tbl, dispersion_notes = reasons.dispersion(df, cm)
display(dispersion_tbl)
for n in dispersion_notes:
    print(" -", n)

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.bar(dispersion_tbl["score"], dispersion_tbl["share"] * 100,
       color="#4a6fa5", edgecolor="white")
ax.axvline(cfg.anchor, color="#b3261e", ls="--", lw=1,
           label=f"anchor {cfg.anchor}")
ax.set_xlabel("PAS composite score"); ax.set_ylabel("% of records")
ax.set_title("Composite score distribution"); ax.set_xticks(range(1, 11))
ax.legend(); ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.show()
""")

md(r"""
---
## Step 3 — Run the checks

`res` holds everything: `res.tables` (dict of frames), `res.findings`, `res.meta`.
Nothing is written to disk until Step 6.
""")

code(r"""
res = pipeline.run_pipeline(cfg, cm, df)
""")

code(r"""
findings = res.findings_df()
print(res.counts().to_string(), "\n")
print("available tables:")
print("  " + "\n  ".join(sorted(k for k in res.tables if not k.startswith("bands_"))))
print(f"\n  + {sum(k.startswith('bands_') for k in res.tables)} per-variable band tables")
""")

code(r"""
# Blockers first. These are the ones that stop PAS influencing price or appearing
# in an underwriter workflow.
display(res.blockers()[["check", "subject", "message"]])
""")

code(r"""
# Filter findings however you like.
SEVERITY = ["BLOCKER", "HIGH"]     # or ["MEDIUM"], ["INFO"], etc.
CHECK    = None                     # e.g. "signal", "circularity", "redundancy"

f = findings[findings["severity"].isin(SEVERITY)]
if CHECK:
    f = f[f["check"] == CHECK]
display(f[["severity", "check", "subject", "message"]].reset_index(drop=True))
""")

md(r"""
---
## Step 4 — Drill into individual checks
""")

code(r"""
# Is Adequacy measuring loss experience, or a burn / on-level factor?
# 93% of physicians are claim-free, so genuine loss-experience variables must be
# near-degenerate at zero. A variable that is never zero and tightly spread is
# measuring something else.
display(res.table("adequacy_reality"))
""")

code(r"""
# Circularity: bands cut on the outcome. Specialty and state tiers were cut on
# portfolio loss ratio, so validating them against loss ratio is circular -- and
# loss ratio reflects rate adequacy, not just risk.
display(res.table("circularity"))
""")

code(r"""
# Per-variable signal, worst first.
# spearman = rank correlation between score band and that band's loss ratio.
# p_value  = permutation test. Above p_value_threshold means "no evidence of
#            ordering", in EITHER direction. ~26 variables are tested, so expect
#            roughly one false positive at 0.05 -- treat a lone hit as a lead.
sig = res.table("variable_signal")
display(sig[["variable", "component", "weight", "target_derived", "bands_used",
             "spearman", "p_value", "violations", "somers_d", "gini"]])
""")

code(r"""
# Band table for one variable. Change DRILL_VARIABLE at the top and re-run.
bands = res.bands(DRILL_VARIABLE)
display(bands)

fig, ax1 = plt.subplots(figsize=(8, 3.4))
ax1.bar(bands["score"], bands["exposure_share"] * 100, color="#c9d6e8",
        edgecolor="white", label="% of exposure")
ax1.set_ylabel("% of exposure"); ax1.set_xlabel("score band")
ax2 = ax1.twinx()
ax2.plot(bands["score"], bands["loss_ratio"], color="#b3261e", marker="o",
         lw=1.8, label="loss ratio")
ax2.set_ylabel("loss ratio")
ax1.set_title(f"{DRILL_VARIABLE} — does loss rise with the score?")
ax1.set_xticks(bands["score"].astype(int))
ax1.spines[["top"]].set_visible(False); ax2.spines[["top"]].set_visible(False)
fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.88), frameon=False)
plt.tight_layout(); plt.show()
""")

code(r"""
# Discrimination: can the bands separate the book, or is most of it tied?
# 77% of policies sit at exactly $1M per-occurrence.
display(res.table("discrimination"))
""")

code(r"""
# Nominal vs realised weight. Where these diverge, the deck describes a
# weighting nobody was actually scored by.
ew = res.table("effective_weights")
display(ew.sort_values("drift", key=abs, ascending=False))
""")

code(r"""
# Redundancy. Total / indemnity / expense loss cost and loss ratio share a
# numerator or denominator by construction, so they should light up here.
display(res.table("vif"))

corr = res.table("score_correlation").set_index("score")
fig, ax = plt.subplots(figsize=(9, 7.5))
im = ax.imshow(corr.to_numpy(dtype=float), cmap="RdBu_r", vmin=-1, vmax=1)
labels = [c.replace("SCORE_", "") for c in corr.columns]
ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=90, fontsize=7)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=7)
ax.set_title("Rank correlation between sub-scores")
fig.colorbar(im, fraction=0.046); plt.tight_layout(); plt.show()
""")

code(r"""
# Composite lift, in-sample and out-of-time.
# Discount the 'all' row: specialty and state tiers were cut on the target, so
# part of that Gini is circular.
if "lift_summary" in res.tables:
    display(res.table("lift_summary"))

for split in ("all", "train", "test"):
    key = f"lift_lorenz_{split}"
    if key in res.tables:
        lz = res.table(key)
        plt.plot(lz["cum_exposure"], lz["cum_loss"], label=split, lw=1.8)
plt.plot([0, 1], [0, 1], "k--", lw=0.8, label="no discrimination")
plt.xlabel("cumulative exposure (ordered by score)")
plt.ylabel("cumulative loss"); plt.title("Lorenz curve — composite")
plt.legend(frameon=False); plt.gca().spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.show()
""")

code(r"""
# PSI year over year. Band widths are recomputed from the portfolio mean on every
# run, so part of any shift may be recalibration rather than real movement.
# Log band widths per run to tell them apart.
display(res.table("stability") if "stability" in res.tables else "not computed")
""")

md(r"""
---
## Step 5 — Underwriter-facing output

### Reconcile first

The attribution is exact by construction:

$$\text{composite} - \text{anchor} = \sum_i w_i^{\text{realised}} \times (\text{score}_i - \text{anchor})$$

If the residual exceeds 0.5, the reason codes describe a different model than the
one that produced the score, and no underwriter should see them.

A known cause: if Adequacy sub-scores are blended as $Z \cdot s + (1-Z) \cdot 5$
before aggregation, their effective anchor is pulled toward 5 rather than 4.5, and
attribution on raw sub-scores cannot reconcile. Check whether the pipeline persists
pre- or post-credibility sub-scores.
""")

code(r"""
display(reasons.reconciliation(df, cm))
""")

code(r"""
# Reason codes for whichever physicians you want to look at.
rc = reasons.reason_codes(df.head(2000), cm, top_n=cfg.reason_top_n)

RECORD = rc["record"].iloc[0]      # change to inspect a different physician
one = rc[rc["record"] == RECORD]
display(one[["direction", "rank", "variable", "component", "score", "raw_value",
             "effective_weight", "contribution_points", "caveat"]])
""")

code(r"""
# Which drivers most often explain a high score, across the book?
top_up = (rc[rc["direction"] == "increases_score"]
          .groupby("variable")
          .agg(times_top_driver=("rank", lambda s: (s == 1).sum()),
               mean_points=("contribution_points", "mean"))
          .sort_values("times_top_driver", ascending=False))
display(top_up)
""")

code(r"""
# Renewal review queue. Ranked on premium at risk, not raw score -- a band-9
# physician paying $1,200 matters less than a band-6 paying $180,000.
tq = reasons.triage(df, cm, cm.exposure_premium, top_n=cfg.triage_top_n)
display(tq.head(25))
""")

code(r"""
# Render PAS cards inline. Every driver shows its RAW value beside its score, and
# data-quality caveats render as visible warnings -- that is how an underwriter
# catches a score of 10 resting on a -99 sentinel.
from IPython.display import HTML, display as _d

out = Path(cfg.output_dir) / "pas_cards.html"
card.render(df.sort_values(cm.composite_score, ascending=False), cm, out,
            limit=cfg.card_limit, top_n=cfg.card_top_drivers)
print(f"wrote {out}")
_d(HTML(out.read_text()))
""")

md(r"""
---
## Step 6 — Export
""")

code(r"""
written = res.write()
for k, v in written.items():
    print(f"{k:<9}: {v}")

# run_config.json plus the data hash in res.meta make any run reproducible.
# Model risk management will ask; the answer should be a file path.
display(pd.DataFrame([{"key": k, "value": str(v)} for k, v in res.meta.items()]))
""")

md(r"""
---
## Threshold sweeps

`cfg.replace()` returns a copy with overrides, so you can test how sensitive a
finding is to the threshold that produced it. If a conclusion flips on a small
change, say so when you present it.
""")

code(r"""
# Example: how many variables show "no evidence of ordering" at different
# p-value thresholds?
rows = []
for p in (0.01, 0.05, 0.10, 0.20):
    r = pipeline.run_pipeline(cfg.replace(p_value_threshold=p, verbose=False), cm, df)
    c = r.counts()
    rows.append({"p_threshold": p,
                 "BLOCKER": int(c.get("BLOCKER", 0)),
                 "HIGH": int(c.get("HIGH", 0)),
                 "MEDIUM": int(c.get("MEDIUM", 0))})
display(pd.DataFrame(rows))
""")

code(r"""
# Example: does the composite still sort loss when the target is rate-independent?
# This matters because specialty and state tiers were cut on loss ratio. If lift
# collapses on loss_cost, the apparent signal was largely circular.
for basis in ("loss_ratio", "loss_cost"):
    try:
        r = pipeline.run_pipeline(cfg.replace(target_basis=basis, verbose=False),
                                  cm, df)
        g = r.table("lift_summary")
        print(f"\n--- target_basis = {basis} ---")
        display(g)
    except KeyError as e:
        print(f"{basis}: {e}")
""")

nb = {"cells": cells,
      "metadata": {
          "kernelspec": {"display_name": "Python 3", "language": "python",
                         "name": "python3"},
          "language_info": {"name": "python", "version": "3.10"}},
      "nbformat": 4, "nbformat_minor": 5}

out = Path(__file__).resolve().parent / "PAS_Pipeline.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(f"wrote {out}  ({len(cells)} cells: "
      f"{sum(c['cell_type'] == 'code' for c in cells)} code, "
      f"{sum(c['cell_type'] == 'markdown' for c in cells)} markdown)")
