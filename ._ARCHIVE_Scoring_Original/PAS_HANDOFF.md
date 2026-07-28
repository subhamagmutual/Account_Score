# Physician MPL PAS — session handoff

**Written:** 2026-07-27 · **For:** a subsequent Claude session picking up this project
**Read this first, then the source documents in §9.**

---

## 1. How to use this document

This is a context transfer, not a summary. §4 (findings) is the substance — those
are conclusions reached by reading the actual design artifacts and testing code
against them, and most of them have not yet been confirmed against production data.
**Treat §4 as high-confidence hypotheses with stated evidence, not settled fact.**
§7 lists what is still unanswered.

Terminology trap: **PAS = Physician Account Score.** Not a Policy Administration
System. I initially assumed the latter; reading the deck corrected it.

---

## 2. Situation

**Person:** Subhashree Singh, MagMutual Insurance Company, Underwriting Analytics.
Technical — writes Python, works in Snowflake, comfortable with actuarial concepts.

**Project:** Build a Physician Account Score for Physician Medical Professional
Liability (MPL). A composite 1–10 risk score per physician, 23 variables across four
components, mean-anchored binning. She has already deployed an equivalent framework
for commercial property (NA Property and Italy portfolios) and is adapting it to MPL.

**Status when this session began:** further along than "ideation." A design deck, a
design workbook, and a scored output CSV dated 2026-04-29 already existed. The deck
claims the system is "built and unit-tested" while its own status table says DESIGN.

**Her stated goal:** ideate on how to help her team, and identify what data points
are needed.

**Her explicit priority ranking** (asked and answered mid-session):

1. UW-facing tooling — reason codes, PAS card, triage lists
2. Validation harness — prove the score sorts loss
3. Feature engineering — new internal and external variables
4. Production engineering — repo, config, tests, Snowflake

**Two other answers given:**

- *Will PAS influence price?* → **Not decided yet.**
- *Is NPI populated at physician level in Oasis?* → **Yes, nearly all risks.** This
  unblocks every external data source.

---

## 3. What PAS is, as designed

Composite 1–10 where **1 = best risk, 10 = worst**. Four components:

| Component | Weight | Contents |
|---|---|---|
| Adequacy | 40% | 9 loss-experience variables, credibility-weighted |
| Capacity | 25% | Per-occ limit (20%), aggregate limit (10%), risk count (10%) |
| Appetite | 25% | Specialty tier (25%), state venue (15%), years since grad, RVU ratio, tenure, hospital rating, practice size |
| Environment | 10% | Income inequality, population density, violent crime, % uninsured |

**Mean-anchored binning:** `band_width = portfolio_mean / 4.5`, so the
premium-weighted portfolio mean always lands in band 4–5. Self-calibrating —
recomputed at runtime from current data, no pre-fitting.

**Credibility:** applied to Adequacy sub-scores only, blending toward a complement.
**The formula appears three different ways across three documents** — see §4.5.

**Weight-zeroing:** when a sub-score is missing, its weight is zeroed and
redistributed across available variables.

**Tech stack:** Python 3, pandas, numpy, openpyxl, xlsxwriter. Config in an Excel
workbook (7 sheets) plus two JSON tier files. Data from Snowflake / DHC pipeline.

---

## 4. Findings

Ordered by consequence. Items 4.1–4.4 would each independently prevent the score
from being used for pricing.

### 4.1 Adequacy may not be measuring loss experience at all — BLOCKER

**Evidence.** The design workbook (sheet `6_Data_Diagnostics`) documents
`ULT_ACTUAL_LOSS_RATIO_BURNED` as median 0.98, p5 0.87, p95 1.11, **100% non-null,
0% zeros**. The same workbook notes **93% of records have zero raw claim count**.

Those two facts cannot both describe a physician-level loss ratio. If 93% of
physicians are claim-free, 93% of their loss ratios are zero. A distribution tightly
centred on 0.98 is a **burn factor or on-level factor**, not loss over premium. The
sub-score sheet confirms the formula is `BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED /
BCE_ST` — *both sides are exposure columns*.

`ULT_Total_FREQUENCY_PER_FTE` has the same signature: median 0.955, no zeros. A real
MPL frequency of 0.955 claims per FTE would be roughly twenty times reality.

**Consequence.** Adequacy is 40% of the composite. If it is built from burn factors,
the composite carries almost no physician-specific loss signal — and the executive
deck describes these columns to leadership as "Total losses / written premium" and
"Claim count / FTE exposure," which would be materially wrong.

**Verify by:** running `check_adequacy_is_experience` (already implemented) against
the production file, or simply checking the zero-share of each Adequacy driver.

### 4.2 Specialty and state tiers were cut on the outcome — BLOCKER

**Evidence.** Design workbook sheets `3_Specialty_Risk_Tiers` and
`4_State_Venue_Risk` explicitly tier by **portfolio loss ratio**. Specialty is 25% of
Appetite, state 15%.

**Two consequences, the second worse than the first.**

1. Validating the score against loss ratio is circular. Lift is guaranteed and
   meaningless.
2. Loss ratio is loss ÷ premium, and premium already contains the class plan's
   specialty and territory factors. **A specialty at LR 1.52 is one you are
   underpricing, not necessarily a risky one.** Raise its rate and its tier improves
   with zero change in underlying risk. The variable measures MagMutual's own pricing
   error and labels it physician risk.

This also explains the state tiers: Georgia is 31% of the book, so Georgia's loss
ratio (0.98) is approximately the portfolio mean, landing it at tier 7 while North
Carolina sits at tier 1.

**Fix.** Re-tier on **loss cost per exposure** (`ULT_Total_LOSS_COST_PER_BCE`, which
already exists), because it is rate-independent.

### 4.3 Sentinel values are scored as the worst risk — BLOCKER

`CV_LOSS_FREE_YEARS` uses **−99 for unknown**. The documented binning maps
"0 or negative" to **score 10** — the worst band. The workbook's own note says
"Negative values (−99) should be treated as missing/worst."

Missing data is therefore priced as your worst risk. Confirmed reproducible: in the
synthetic fixture, 2,340 sentinel records all received score 10.

**Fix.** Convert sentinels to NaN before binning so weight-zeroing handles them.

### 4.4 The composite may be unable to differentiate the book

**Evidence.** Scoring 60,000 synthetic physicians through the documented weights put
**89% in bands 4–5**, with 2 records above 7 and a standard deviation of 0.68.

This is structural, not an artifact of synthetic data: averaging ~23 variables each
anchored at 4.5 collapses the composite's variance toward the anchor — the central
limit theorem working against the design.

**Consequence.** The deck's stated business outcome "set portfolio targets (e.g.
<20% in scores 8–10)" cannot bind if nobody reaches 8. A triage queue sorted on score
has nothing to sort. Reason codes and the PAS card become decoration on something
that does not discriminate.

**This is the cheapest high-value check available and has NOT yet been run on real
data.** Two minutes:

```python
df["PAS_COMPOSITE_SCORE"].value_counts().sort_index()
df["PAS_COMPOSITE_SCORE"].std()
```

**If ~90% sit in bands 4–5, this reorders the whole project** — it means fewer,
stronger variables, or targets expressed in percentiles rather than absolute bands.
Ask for this early.

### 4.5 The credibility formula is inconsistent across three documents

| Source | Formula | Full credibility at |
|---|---|---|
| May 2026 deck | `Z = MIN(Premium / 50000, 1)` | $50,000 |
| Design workbook sheet 1 | `Z = MIN(SQRT(prem / X), 1)` | unstated |
| Design workbook sheet 5 + subscores CSV | `Z = MIN(SQRT(premium / 10000), 1)` | ~$10,000 (portfolio mean) |

The last gives the **median physician Z = 0.84** — 84% weight on the own experience
of someone with roughly 0.07 claims a year. That is very aggressive.

**Also:** the credibility complement is **5** while the mean anchor is **4.5**. A
physician with zero credibility therefore lands at 5, i.e. slightly *worse* than
"average," purely for having thin data.

**Recommendation.** Estimate the full-credibility constant empirically
(Bühlmann-Straub, `Z = n/(n+k)`, separate `k` for frequency and severity — severity is
far more credibility-hungry), and make the complement the **specialty × state class
mean** rather than a flat portfolio value.

### 4.6 Credibility blending breaks reason-code attribution

Discovered by the reconciliation function on its first run: max residual **1.39**
where rounding alone should keep it under 0.5.

If Adequacy sub-scores are blended as `Z·s + (1−Z)·5` before aggregation, their
effective anchor is pulled toward 5 rather than 4.5. Reason codes computed on **raw**
sub-scores cannot reconcile against a composite built from **blended** sub-scores.

**Open question for the user (§7):** does the scored output persist pre- or
post-credibility sub-scores?

### 4.7 Mixed grain inside a single row

Premium (`WRTN_PREM_AMT_ITD_BURNED`, median $7,181) appears allocated to the
individual physician. But `TOP_PER_M`, `TOP_AGG_M` and `RISK_COUNT` (median 14, max
566) are **policy** attributes denormalised onto every physician's row.

**The entire Capacity component — 25% of the composite — is a property of the
physician's group, not the physician.** Every doctor on a 200-physician policy
receives an identical Capacity score, and high `RISK_COUNT` pushes all of them toward
"worse" for an aggregation exposure none of them individually creates.

Needs a design decision: individual score, or a separate group-level score.

### 4.8 The grain itself is unconfirmed

Summing the design workbook's state tier sheet gives **~169,700 rows** across
2017–2024, i.e. ~21,200/year. The deck states **40,000+ insured physicians**, which at
physician-year grain implies ~320,000 rows. The file is roughly **0.53×** that.

Two readings fit the evidence:

- **(a)** Grain *is* physician-year, ~21,200 in force per year, ~40,000 unique across
  eight years. Plausible — median tenure with MAG is 7 years.
- **(b)** Grain is policy-year with `RISK_COUNT` physicians per row. But then
  `AGE_IMPUTED` and `RVU_RATIO` cannot be meaningful on a row covering 14 people.

Reading (a) is more likely, but it has not been confirmed. One-line check:

```python
df.groupby(["RISK_CISID","COVERAGE_YEAR"]).size().value_counts().head()
```

All 1s → physician-year grain. Anything else → duplicates, and every
premium-weighted mean in the model is wrong.

### 4.9 Circularity between the score and new business

Adequacy is built entirely from the physician's own loss experience. For a new
business submission Adequacy is empty, weight-zeroing fires, and **40% of the weight
silently redistributes** to Capacity/Appetite/Environment — while the output is still
labelled 1–10 on the same scale. A submission score and a renewal score are different
models wearing the same label.

**Recommendation.** Publish two scores: a prospective score (Appetite + Capacity +
Environment) and an experience score, side by side. This also makes the deck's goal of
"target new business with favorable score profiles" actually executable.

### 4.10 Variables that cannot discriminate

- **Per-occurrence limit** (20% of Capacity): 77% of policies sit at exactly $1M, and
  $1M maps to bands 3, 4 **and** 5. Three-quarters of the book is tied.
- **Hospital rating** (5% of Appetite): five distinct star values spread across ten
  bands, **59% null**. "No affiliation captured" is being conflated with
  "office-based practice" — different risks.
- **Aggregate limit:** heavily concentrated at $3M.

### 4.11 Redundancy

Total / indemnity / expense loss cost and actual loss ratio share a numerator or
denominator by construction, and carry 45% of Adequacy between them. Effectively a
~12-variable model presented as 23.

`AGE_IMPUTED` and `YEARS_SINCE_GRAD_IMPUTED` correlate at **r ≈ 0.95** — the workbook
flags this itself (sheet `7_Design_Decisions`) and recommends dropping one. Both are
still present in the workbook's composite formula.

### 4.12 Premium volume scores size as quality

`SCORE_PREMIUM_VOLUME` gives band 1 (best) to premium ≥ $30,000. Large accounts score
better by construction. It also duplicates the premium-based credibility Z, so premium
is double-counted. It is in the workbook's Adequacy formula but absent from the deck's
list of 9.

### 4.13 The deck and the design workbook describe different models

The workbook's Step 3 Adequacy formula uses **Premium Volume** and **Excess/Primary**,
which the deck omits, and *excludes* Indemnity Loss Cost, Expense Loss Cost, Indemnity
Frequency, Total Severity and Total Loss Cost, which the deck includes. The workbook's
Appetite includes **Physician Age** at 7%, which the deck drops.

Also inconsistent: Environment is described as "a small additive adjustment, ±0.5
points" in Step 6 but as 10% of a weighted average in Step 7. Those are different maths.

**Someone needs to establish which model actually ran.**

### 4.14 Environment is Property PAS residue

Violent crime rate and population density are GL/property variables. For MPL the driver
is **venue litigiousness**. Better county-level substitutes:

- Plaintiff-bar density — Census County Business Patterns, NAICS 5411 per capita
- County MPL verdict history
- A structured **tort-law feature table with effective dates**: noneconomic caps and
  whether struck down, certificate of merit, pre-suit screening panels, statute of
  repose, joint and several liability, collateral source, PCF participation

**Georgia is the live case.** SB 68 and SB 69 were signed 21 April 2025, restricting
"anchoring" of noneconomic damages and phantom damages; SB 69's litigation-funding
registration provisions took effect 1 January 2026. A state tier fitted on 2017–2024
predates all of it, in MagMutual's largest state.

### 4.15 Self-calibration has an unbudgeted operational cost

Because `band_width = portfolio_mean / 4.5`, a physician's score changes when *other*
physicians' data changes. An underwriter will ask about that in week one, and audit
will ask to reproduce a score from six months ago.

**Needs:** band widths logged per run, plus a "frozen bands" mode so scores hold steady
within a rating cycle.

### 4.16 Regulatory exposure if PAS ever touches price

Income inequality, percent uninsured, population density and violent crime rate are
geographic socioeconomic proxies that can correlate with protected classes. Under the
NAIC AI model bulletin regime this is a **disparate-impact question**.

The user answered "not decided yet" on pricing. The recommendation given: do the
circularity fix (§4.2) now regardless, because it is worth doing on methodology grounds
alone and it keeps the pricing option open at no cost. If the answer later becomes
"filed rating factor," re-tiering under a filing deadline with an unexamined
disparate-impact question is a bad position.

### 4.17 Green-year validation problem

**This corrects advice given earlier in the session.** A train 2017–21 / test 2022–24
split was initially suggested. That is wrong if reported rather than ultimate losses are
used: 2023–24 losses are badly under-developed, so testing on them **biases toward
finding no signal** because losses have not emerged yet.

Either use the developed losses (the workbook already applies CapeCod development) or lag
the test window to years at least 3–4 years mature.

### 4.18 RVU peer benchmark is probably computed on the wrong population

`RVU_WORK_TOTAL_RATIO_SPEC_OL` divides a physician's work RVUs by "their specialty
average." If that average is computed on MagMutual's book, it is MagMutual's own
selection bias rather than a peer norm — and it shifts every year as the mix changes.

**Compute it from national CMS data.** Same for practice-size percentiles. 24% of records
are null on this variable.

### 4.19 Missing variables with the strongest evidence base

The single best available variable is almost certainly one MagMutual already owns and is
not using: **risk-management hotline call volume and topic per physician.**

Thirty years of Vanderbilt CPPA research (Hickson, Cooper, et al.) shows unsolicited
patient complaints predict future malpractice claims **independent of clinical volume**,
with roughly 3% of clinicians driving a disproportionate share. The PARS index is an
established predictor of claims, worse outcomes, and physician well-being concerns. No
competitor can buy MagMutual's hotline data.

Also absent and cheap:

- **Claim allegation / injury code.** "Failure to diagnose" is the #1 category and the
  deck cites it, yet no allegation feature exists.
- **APP supervision count** (NPs/PAs supervised) — major vicarious liability exposure.
- **Suit-filed flag, county of filing, disposition.**
- **Recency-weighted prior claim count.** NEJM/Studdert 2016 showed prior paid claims
  strongly predict recurrence; loss-free years is a crude proxy.
- **Rate adequacy — bound premium vs actuarial indication.** In the user's own candidate
  variable list marked *High* priority, then dropped. It is the honest way to measure
  pricing adequacy without the loss-ratio circularity.

### 4.20 NPDB caution

The NPDB **Public Use File is de-identified to state level**, and its data use agreement
forbids using it alone or combined with other data to identify a practitioner. It is a
state-severity benchmarking tool only, **never a physician-level feature**.

Whether MagMutual qualifies as an authorised querier for identified data is a legal
question — "health plans" are listed among authorised queriers; an MPL carrier arguably
is not one. This should be answered by counsel rather than assumed.

---

## 5. What was built

A Python package, `pas_diagnostics`, plus a notebook. Delivered as
`physician_mpl_pas.zip`. Verified end to end from a clean directory.

**Dependencies: pandas + numpy only** (openpyxl for the optional Excel output). No
scikit-learn, no statsmodels — deliberate, because corporate Python environments lag on
those and every statistic is a dozen lines of numpy.

```
PAS/
  PAS_Pipeline.ipynb          ENTRY POINT — 38 cells, parameter-driven
  pas_diagnostics/
    config.py     DiagnosticConfig — 31 parameters; 17 threshold sites in checks.py read from it
    schema.py     ColumnMap, Variable, sentinel registry, documented distributions
    metrics.py    Gini, Lorenz, Somers' D, VIF, PSI, band summaries, monotonicity + permutation test
    checks.py     the ten diagnostic checks
    pipeline.py   shared orchestration for CLI and notebook, fuzzy column-map suggester
    reasons.py    exact additive attribution, reason codes, reconciliation, triage, dispersion
    card.py       standalone HTML PAS card
    report.py     markdown / CSV / Excel writers
    cli.py        thin wrapper over pipeline.run_pipeline()
  test_edges.py                32 adversarial tests
  make_fixture.py              60k synthetic rows with six planted pathologies
  build_notebook.py            regenerates the notebook
  PAS_Code_Guide.xlsx          what each file does
  PAS_Input_Data_Dictionary.xlsx  input spec, 6 sheets
```

**The ten checks:** schema · data quality (incl. sentinels that received a score) ·
adequacy-is-experience · circularity · variable signal · discrimination ·
effective weights · redundancy · composite lift · stability.

**Run order:**

```bash
python test_edges.py            # → 32 passed, 0 failed
python make_fixture.py
python -m pas_diagnostics --input fixture_physician_scores.csv --outdir out
                                # → 9 BLOCKER / 27 HIGH / 16 MEDIUM
# then the notebook against real data
```

Those three numbers (9/27/16) are the signature of a working install — the fixture plants
six known pathologies, so matching counts means the checks fire.

### Design decisions worth preserving

**Attribution is exact, not approximate.** Because the composite is a weighted average of
sub-scores anchored at 4.5:

```
composite − 4.5 == Σᵢ effective_weightᵢ × (scoreᵢ − 4.5)
```

Contributions sum to the score, so an underwriter can be shown the arithmetic and an
auditor can rebuild it in Excel. Better than SHAP here. `effective_weight` is the
**realised** weight after weight-zeroing, not the nominal weight — they differ for most
physicians.

**Permutation guard on monotonicity.** The first run flagged seven variables as "INVERTED"
that were pure noise in the fixture. With 5–10 bands, |rho| of 0.9 arises by chance
easily. A harness that cries blocker on noise is ignored by week two. Findings are now
gated on a permutation p-value, and the honest finding above threshold is "no evidence of
ordering" in either direction. **With ~26 variables tested, expect roughly one false
positive at p<0.05** — treat a lone significant result as a lead.

**The card shows raw values beside scores** and renders data-quality caveats as visible
warnings, not footnotes. That is the argument for building UW tooling before the model is
fixed: it makes the model falsifiable by the people who use it. The card deliberately
omits the deck mockup's recommendation line ("Competitive pricing appropriate") — the
model has not earned that.

**Triage ranks on premium-at-risk, not raw score.** A band-9 physician paying $1,200
matters less than a band-6 paying $180,000.

### Defects found and fixed during review

1. `check_discrimination` raised `KeyError: 'largest_band_share'` on an empty book
2. `prepare()` let an empty frame through instead of raising with guidance
3. `np.nanmean` warned "Mean of empty slice" on absent variables
4. scipy `ConstantInputWarning` on every constant series → added `metrics.safe_spearman()`
5. `make_fixture.py` had a hardcoded Linux path that would fail on Windows

Numerics verified, not just non-crashing: Gini returns exactly +0.9 on a perfect ordering
where the worst decile carries all loss (0.9 is the ceiling given that concentration),
−0.9 reversed; Somers' D exactly ±1 monotone/reversed, NaN on flat; attribution reconciles
to <1e-9 absent credibility blending — which confirms the residual in §4.6 comes from the
blending, not the attribution maths.

---

## 6. Environment constraints (important for the next session)

- **No local filesystem access.** `C:\...` paths cannot be read or written. The user's
  reference code at `C:\Users\ssingh\Projects\PSL_Modeling\Account_Score_PAS` and
  `C:\Users\ssingh\Personal\Knowledge\riskwatch-pas-na-model-sit` **was never obtained.**
  Ask her to copy it under `C:\Box\Box\...` or upload it.
- **Box connector: read works, `create_folder` is DENIED** (missing scope). `upload_file`
  works but only text formats and only flat into an existing folder. A stray
  `pas_diagnostics__init__.py` from a permission test is sitting in the PAS folder and
  should be deleted; I could not.
- **Do not ask her to upload the scored CSV.** It is 48 MB and contains physician-level
  loss and premium detail for 40,000+ insureds. Claude Code reading it locally is the
  correct handling.
- **Claude Code was recommended** for exactly this reason — local filesystem access, can
  run the harness, read the reference folders, and iterate on the column map.
- She raised **credit cost** and asked about downgrading to Haiku. Told her the model
  selector is hers to use, that switching mid-thread does not shrink this context, and
  that a fresh conversation with just the README plus key findings would save more. Build
  work is fine on Haiku; §4.1, §4.2 and the re-tiering are worth a stronger model.

---

## 7. Open questions — ask these

1. **Pre- or post-credibility sub-scores?** Does the scored output persist Adequacy
   sub-scores before or after the `Z·s + (1−Z)·5` blend? Determines whether reason codes
   can reconcile (§4.6). `CREDIBILITY_Z` is persisted, so either is recoverable.
2. **Composite dispersion on real data.** Value counts and std dev of
   `PAS_COMPOSITE_SCORE`. Two minutes. Reorders the project if ~90% sit in bands 4–5
   (§4.4). **Asked three times, not yet answered.**
3. **Grain confirmation** (§4.8). One `groupby().size().value_counts()`.
4. **Anchor 4.5 vs complement 5** — reconcile, or document why they differ.
5. **Which model actually ran** — the deck's 23 variables or the workbook's composite
   formula (§4.13)?
6. **Will PAS influence price?** Answered "not decided yet." Worth revisiting, because it
   governs how much filing and model-governance rigour to build in.
7. **Does an MPL carrier qualify as an NPDB authorised querier?** Legal question (§4.20).
8. **Does MagMutual run a risk-management hotline, and is call data retrievable per
   physician?** If yes, this is likely the highest-value variable available (§4.19).

---

## 8. Recommended next actions

**Immediate, cheap, high information:**

1. Dispersion check (§4.4) and grain check (§4.8). Minutes each.
2. Zero-share of every Adequacy driver (§4.1). Settles the biggest finding.
3. Run `test_edges.py`, then the fixture, then `--inspect` against the real file to fix
   the column map.

**Then, in her priority order:**

4. **UW tooling.** Reason codes and the card are built. What is missing is the
   reconciliation answer (§7.1) — without it the reason codes may not add up. Get that
   first.
5. **Validation.** Run the full harness. Critically, use `--target loss_cost` as well as
   `loss_ratio`: if lift collapses on the rate-independent basis, the apparent signal was
   largely the circular tiers (§4.2). The notebook's last cell does both.
6. **Fixes worth doing regardless of the pricing decision:** re-tier specialty and state
   on loss cost; convert sentinels to NaN; log band widths per run; split prospective vs
   experience scores.
7. **Feature engineering**, now unblocked by NPI coverage. Start with the internal gaps
   (§4.19) before buying anything — hotline calls, allegation codes, APP supervision,
   suit-filed flag.

**Not built, deliberately deferred:** GLM/Tweedie challenger to test the 40/25/25/10
weights against evidence; point-in-time feature store with as-of joins; frozen-bands mode;
config migration from Excel to version-controlled YAML; external NPI enrichment joins.

---

## 9. Source documents

All in Box under `BOX Subhashree Singh / Business / PAS` (folder id `379322515036`),
which syncs to `C:\Box\Box\BOX Subhashree Singh\Business\PAS`.

| Document | Box file id | Why it matters |
|---|---|---|
| `Physician_MPL_PAS__May2026_V01.pptx` | 2223620991651 | The executive deck. The 23 variables, 40/25/25/10 weights, methodology slides, UW card mockup |
| `Physician_MPL_Account_Score_Design_v2.xlsx` | 2213635970014 | **The most important document.** 8 sheets: target dictionary, sub-scores, binning detail, specialty tiers, state tiers, composite formula, **data diagnostics**, design decisions. Most findings in §4 come from here |
| `Candidate_Variables_Physician_MPL_Account_Score.csv` | 2213590138806 | Her original candidate list. Contains several good variables later dropped — rate adequacy, board certification, practice setting, retro date, tort reform, procedure mix, patient acuity |
| `Physician_MPL_Account_Score_SubScores_and_Ranges.csv` | 2213607114587 | Per-variable binning with rationale and data-availability notes. Source of the "93% zero claim count" fact |
| `physician_scores_20260429_141959.csv` | 2213751717122 | The scored output, 48 MB. The file the harness reads |
| `physician_scores_20260429_141959.xlsx` | 2213754225161 | Same, with deployment tables |
| `DRAFT Initial Portfolio and Account Dashboard Metric List.xlsx` | 2214867006474 | From Megan. Real Snowflake table/column mappings — `magstage.dm_policy_pv`, `magstage.claims_data_mart`, `data_share.psl_model_summary`, `data_share.t_trend`. Also flags the specialty-granularity gap |

Related, elsewhere in Box: `Business/Account_Score/` (design files),
`Business/Modeling/data/regression/output/MPL_FQ/` and `MPL_SV/` (frequency and severity
regression configs, `2025_MPL_FQ_FTE_v*` JSON), `Corporate Actuarial/Benchmarks/External
Studies/AM Best MPL Industry Reports/`.

**Ecosystem:** Oasis (policy admin), Snowflake data mart, Salesforce, Image Right,
Qliksense, Tableau, Appian (UW workflow), Confluence/Jira. Connectors available in this
environment include Box, Atlassian Rovo, Slack, Microsoft 365, Figma, Lucid, Docusign,
CoCounsel Legal (Thomson Reuters — potentially useful for county venue/verdict analytics).

---

## 10. External research summary

Established in this session, with sources, so it need not be re-researched:

- **Patient complaints predict claims.** Vanderbilt CPPA / PARS. Hickson et al., *JAMA*
  2002; Studdert et al., *NEJM* 2016 (prior paid claims predict recurrence, small minority
  of physicians drive disproportionate share). PARS index predicts claims **independent of
  clinical volume**; ~3% of clinicians are high-risk; a 2024 orthopaedic study found an 83%
  reduction in claims cost per high-risk clinician after PARS intervention.
- **Industry payments correlate with complaints.** PARS index associates with acceptance of
  industry general payments; framed as two expressions of the same physician phenotype.
- **Severity is rising, frequency is not.** NPDB average physician payment ~$514,000 in
  2025, ~20% above 2022. Verdicts over $10M: 70 (2023), 52 (2024), 60 (2025). Average of the
  top 50 medical malpractice verdicts rose from $32.6M (2022) to ~$50M (2025). Over 60% of
  MPL insurers representing 90% of premium cite social inflation as a material adverse
  deviation risk in NAIC actuarial opinions.
- **Georgia tort reform.** SB 68 / SB 69 signed 21 April 2025 — first major reform since
  2005. Restricts anchoring of noneconomic damages, eliminates phantom damages, allows
  bifurcation, regulates third-party litigation funding (registration effective 1 January
  2026). Most provisions applied retroactively to pending cases.
- **CMS data available by NPI:** Medicare Physician & Other Practitioners by Provider
  (services, unique beneficiaries, allowed/standardised payments, beneficiary mean age,
  **mean HCC risk score**, chronic-condition prevalence); by Provider and Service (HCPCS
  mix); Open Payments; Care Compare Doctors and Clinicians; Hospital Compare (star rating,
  **PSI-90**, HCAHPS); Part D Prescriber (opioid rates); NPPES.
- **NPDB PUF is state-level and de-identified**; DUA forbids combining with other data to
  identify a practitioner.

---

*End of handoff. The two most valuable things a next session can do: get the dispersion
number (§4.4) and the reconciliation answer (§7.1). Both are quick, and both change what is
worth building.*
