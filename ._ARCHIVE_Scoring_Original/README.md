# Physician MPL PAS — diagnostics & underwriter tooling

Python 3.10+. Depends on **pandas and numpy only** (openpyxl if you want the
Excel workbook). No scikit-learn, no statsmodels — corporate environments lag on
those, and every statistic here is a dozen lines of numpy.

```
pas_diagnostics/
  schema.py    column map, sentinel registry, distributions transcribed from
               Physician_MPL_Account_Score_Design_v2.xlsx
  metrics.py   Gini, Lorenz, Somers' D, VIF, PSI, weighted quantiles,
               monotonicity with a permutation guard
  checks.py    ten diagnostic checks, each returning a table + severity findings
  reasons.py   exact additive score attribution, reason codes, triage, dispersion
  card.py      standalone HTML PAS card
  report.py    markdown + CSV + Excel writers
  cli.py       entry point
make_fixture.py  synthetic data reproducing every documented pathology
```

## Start here

```bash
# 1. Resolve the schema. Computes nothing. Do this before trusting any number.
python -m pas_diagnostics --input physician_scores_20260429_141959.csv --inspect

# 2. If columns don't resolve, dump the map, edit it, pass it back
python -m pas_diagnostics --input F --dump-column-map map.json
python -m pas_diagnostics --input F --column-map map.json --inspect

# 3. Full run with an out-of-time split
python -m pas_diagnostics \
    --input physician_scores_20260429_141959.csv \
    --outdir reports/2026-07 \
    --train-years 2017 2018 2019 2020 2021 \
    --test-years  2022 2023 2024 \
    --excel
```

Exits `3` if any BLOCKER fires, so it can gate a scheduled job.

Use `--nrows 50000` while iterating; the 48 MB file takes a while to parse.

## The checks

| Check | Question it answers |
|---|---|
| `schema` | Are the columns what the design workbook says? |
| `data_quality` | Missing, zero, out-of-range, **sentinels that received a score** |
| `adequacy_reality` | Is Adequacy measuring loss experience, or a burn factor? |
| `circularity` | Were bands cut on the outcome? |
| `variable_signal` | Does each variable order loss? Permutation-guarded |
| `discrimination` | Can the bands separate the book, or is everyone tied? |
| `effective_weights` | Nominal vs realised weight after weight-zeroing |
| `redundancy` | VIF and pairwise rank correlation among scores |
| `composite_lift` | Gini in-sample and out-of-time |
| `stability` | PSI year over year |

`--target loss_ratio` uses on-levelled premium as the denominator (what the
current design tiered on). `--target loss_cost` uses BCE exposure and is
**rate-independent** — the right basis for re-tiering specialty and state.

## Underwriter tooling

```python
from pathlib import Path
import pandas as pd
from pas_diagnostics.schema import ColumnMap
from pas_diagnostics import reasons, card

cm = ColumnMap()
df = pd.read_csv("physician_scores.csv", low_memory=False)

reasons.reconciliation(df, cm)          # run this FIRST — see below
reasons.dispersion(df, cm)              # can the score populate high bands?
reasons.reason_codes(df, cm, top_n=3)   # long-format, one row per driver
reasons.triage(df, cm, cm.exposure_premium, top_n=250)
card.render(df, cm, Path("cards.html"), limit=25)
```

### The attribution is exact, not approximate

The composite is a weighted average of sub-scores anchored so 4.5 means
"portfolio average", so:

```
composite - 4.5  ==  sum_i [ effective_weight_i * (score_i - 4.5) ]
```

Each term is a real number of score points a named variable contributed, and the
terms sum to the score. That beats SHAP here: an underwriter can be shown the
arithmetic and an auditor can rebuild it in Excel. `effective_weight_i` is the
**realised** weight after weight-zeroing, not the nominal weight — those differ
for most physicians, and attributing with nominal weights produces reason codes
that don't add up.

### `reconciliation()` found something on its first run

Against the synthetic fixture it reports max residual **1.39**, with only 88.6%
of records within 0.5. Rounding alone should keep everything under 0.5. The cause
is real and applies to your pipeline:

**Credibility blending breaks the anchor.** If each Adequacy sub-score is blended
as `Z * score + (1 - Z) * 5` before aggregation, then the effective anchor for
those sub-scores is no longer 4.5 — it's pulled toward the complement of 5. Reason
codes computed on the *raw* sub-score cannot reconcile against a composite built
from *blended* sub-scores.

Two things needed from the pipeline to fix it:

1. Does the scored output persist **pre-** or **post-**credibility sub-scores? If
   pre, the attribution has to re-apply the blend, which means `CREDIBILITY_Z`
   must be persisted per record (it is, in the fixture).
2. The Adequacy complement is 5 while the anchor is 4.5. Those should be the same
   number, or the discrepancy documented — a physician with zero credibility
   lands at 5, i.e. slightly worse than "average", purely from having thin data.

Ship `reconciliation()` output beside any reason codes. If the residual is large,
the reason codes describe a different model than the one that produced the score,
and no underwriter should trust them.

### Why build the card before the model is fixed

The card shows every driver's **raw value beside its score**, and renders data
quality caveats as visible warnings rather than footnotes. A physician whose top
adverse driver reads `Loss-free years: -99 (SENTINEL — value unknown)` is a bug an
underwriter will spot in week one. Reason codes make the model falsifiable by the
people who use it. That is the argument for doing UW tooling first.

The card deliberately omits the deck mockup's recommendation line ("Competitive
pricing appropriate"). The model hasn't earned that. It presents evidence.

## Verification

```bash
python make_fixture.py                                    # 60k rows, planted bugs
python -m pas_diagnostics --input fixture_physician_scores.csv --outdir out \
    --train-years 2017 2018 2019 2020 2021 --test-years 2022 2023 2024
```

The fixture plants six pathologies transcribed from the design workbook; the
harness should report 9 blockers including circularity on specialty and state,
`adequacy_reality` on the burn-factor variables, and `sentinel_scored` on
loss-free years. If a check stops firing here, the check is broken.

## Reading the output

- **Gini** below 0 means the score orders loss backwards; below ~0.10 means no
  usable ordering. Read comparatively, not against an absolute benchmark.
- **Spearman** is rank correlation between score band and that band's loss ratio
  — the question an underwriter asks first: does a 7 really lose more than a 3?
- **`p_value`** is a permutation test. With 5–10 bands, |rho| of 0.9 arises by
  chance more often than intuition suggests. Above 0.05, the honest finding is
  "no evidence of ordering", in either direction. **26 variables are tested, so
  expect roughly one false positive at p < 0.05** — treat a lone significant
  result as a lead, not a conclusion.
- **Circularity** findings *invalidate* lift, they don't merely weaken it. A tier
  cut on loss ratio will always look predictive of loss ratio.
- **Realised weights** are what the book actually experienced. Where they diverge
  from nominal, the deck describes a model nobody was scored by.

## Not built yet

Deliberately out of scope until the questions above are answered:

- GLM/Tweedie challenger to test the 40/25/25/10 weights against evidence
- Point-in-time feature store with as-of joins
- Band-width logging and a frozen-bands mode for in-force policies
- Config migration from Excel to version-controlled YAML with schema validation
- External enrichment on NPI (CMS Physician & Other Practitioners, Open Payments,
  PSI-90, Part D prescriber, county venue features)
