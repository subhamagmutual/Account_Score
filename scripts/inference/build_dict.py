"""Generate PAS_Input_Data_Dictionary.xlsx"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

F = "Arial"
HDR = PatternFill("solid", fgColor="1F3864")
HF = Font(name=F, sz=10, bold=True, color="FFFFFF")
B = Font(name=F, sz=10)
BB = Font(name=F, sz=10, bold=True)
T = Font(name=F, sz=14, bold=True, color="1F3864")
S = Font(name=F, sz=10, italic=True, color="595959")
H2 = Font(name=F, sz=11, bold=True)
REQ = PatternFill("solid", fgColor="FCE4E4")     # mandatory
NICE = PatternFill("solid", fgColor="E2EFDA")    # recommended addition
WARN = PatternFill("solid", fgColor="FFF2CC")    # needs a decision
thin = Side(style="thin", color="D9D9D9")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)

wb = Workbook()


def sheet(name, title, sub=None):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = T
    ws.row_dimensions[1].height = 22
    if sub:
        ws["A2"] = sub
        ws["A2"].font = S
        ws.merge_cells("A2:H2")
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[2].height = 30
    ws.sheet_view.showGridLines = False
    return ws


def head(ws, row, cols):
    for i, c in enumerate(cols, 1):
        x = ws.cell(row=row, column=i, value=c)
        x.font, x.fill, x.border = HF, HDR, BOX
        x.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def body(ws, r0, rows, widths, wrap=(), fill=None, h=44):
    for r, vals in enumerate(rows, r0):
        for c, v in enumerate(vals, 1):
            x = ws.cell(row=r, column=c, value=v)
            x.font, x.border = B, BOX
            x.alignment = Alignment(vertical="top", wrap_text=(c in wrap))
            if fill:
                f = fill(vals)
                if f:
                    x.fill = f
        ws.row_dimensions[r].height = h
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def tbl(ws, name, r0, r1, c1):
    t = Table(displayName=name, ref=f"A{r0}:{get_column_letter(c1)}{r1}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
    ws.add_table(t)


def para(ws, row, text, font=B, width="A:H", height=None):
    ws.cell(row=row, column=1, value=text).font = font
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    if height:
        ws.row_dimensions[row].height = height


# ===========================================================================
# 1. SPEC SUMMARY
# ===========================================================================
ws = sheet("Spec Summary", "PAS input file — specification",
           "What the harness expects, and four decisions that need making before "
           "the next production run.")

r = 4
para(ws, r, "1. GRAIN — needs confirming before anything else", H2); r += 1
para(ws, r,
     "The code assumes ONE ROW PER PHYSICIAN PER COVERAGE YEAR, uniquely keyed by "
     "(NPI or RISK_CISID) x COVERAGE_YEAR, with POLICY_NUMBER_TRIMMED as the "
     "policy the physician sat on that year.", BB, height=32); r += 1
para(ws, r,
     "The design workbook's own record counts do not clearly support that. Summing "
     "its state tier sheet gives ~169,700 rows across 2017-2024, i.e. ~21,200 per "
     "year. The deck states 40,000+ insured physicians, which at physician-year "
     "grain would be ~320,000 rows. The file is roughly half that.",
     height=44); r += 1
para(ws, r,
     "Two readings are consistent with the evidence. (a) Grain IS physician-year, "
     "with ~21,200 individuals in force per year and ~40,000 unique across eight "
     "years — plausible, since median tenure with MAG is 7 years. (b) Grain is "
     "policy-year, with RISK_COUNT (median 14, max 566) physicians per row — in "
     "which case it is not physician-level scoring at all, and AGE_IMPUTED or "
     "RVU_RATIO cannot be meaningful on a row covering 14 people.",
     height=58); r += 1
para(ws, r, "Run this to settle it in 30 seconds:", BB); r += 1
ws.cell(row=r, column=1,
        value='df.groupby(["RISK_CISID","COVERAGE_YEAR"]).size().value_counts().head()'
        ).font = Font(name="Consolas", sz=9)
ws.merge_cells(f"A{r}:H{r}"); r += 1
para(ws, r,
     "All 1s means physician-year grain and you are fine. Anything else means "
     "duplicates, and every premium-weighted mean in the model is wrong because "
     "the same physician is counted more than once.", height=32); r += 2

para(ws, r, "MIXED GRAIN INSIDE A SINGLE ROW — a real design issue", H2); r += 1
para(ws, r,
     "Premium (WRTN_PREM_AMT_ITD_BURNED, median $7,181) looks allocated to the "
     "individual. But TOP_PER_M, TOP_AGG_M and RISK_COUNT are POLICY attributes "
     "denormalised onto every physician's row. The whole Capacity component — 25% "
     "of the composite — is therefore a property of the physician's GROUP, not of "
     "the physician. Every doctor on a 200-physician policy receives an identical "
     "Capacity score, and a high RISK_COUNT pushes all of them toward 'worse' for "
     "an aggregation exposure none of them individually creates. Decide whether "
     "that belongs in an individual score or in a separate group-level score.",
     height=74); r += 2

para(ws, r, "2. HOW MUCH HISTORY", H2); r += 1
head(ws, r, ["Purpose", "Minimum", "Recommended", "Why"])
hist_start = r + 1
hist = [
    ("Experience features (loss cost, frequency, loss-free years)",
     "5 years", "10 years, recency-weighted",
     "MPL frequency is ~0.07 claims per physician-year. Five years gives a median "
     "physician 0.35 expected claims — nowhere near credible. More history is the "
     "only way to get signal from individual experience."),
    ("Class/tier calibration (specialty, state)",
     "5 years", "10+ years",
     "Rare high-severity specialties need volume. Neurosurgery has ~2,100 records "
     "across eight years in this book."),
    ("Out-of-time validation",
     "6 years", "10 years so the test window can be mature",
     "CRITICAL: do not validate on green years. 2023-24 losses are badly "
     "under-developed, so testing on them biases toward 'no signal' — losses "
     "simply have not emerged yet. Either use developed/ultimate losses (the "
     "workbook already applies CapeCod development) or lag the test window to "
     "years at least 3-4 years mature."),
    ("Severity trend and tort-change effects",
     "8 years", "15 years",
     "Georgia SB 68/69 took effect April 2025. A tier fitted on 2017-24 predates "
     "it entirely."),
]
body(ws, hist_start, hist, [40, 14, 34, 70], wrap=(1, 3, 4), h=62)
tbl(ws, "History", r, hist_start + len(hist) - 1, 4)
r = hist_start + len(hist) + 1
para(ws, r,
     "Also required: report date AND accident date on every claim. These are "
     "claims-made policies, so report-year and accident-year views differ "
     "materially and the score must be built on a consistent basis.",
     height=32); r += 2

para(ws, r, "3. MAGMUTUAL DATA OR ALL US PHYSICIANS? — both, for different jobs", H2); r += 1
head(ws, r, ["Dataset", "Population", "Grain", "Why it must be this population"])
pop_start = r + 1
pop = [
    ("Scored population\n(the input file)", "MagMutual Physician MPL insureds only",
     "physician x coverage year",
     "You can only score who you insure or quote. This is what the harness reads."),
    ("Reference universe\n(peer benchmarks)",
     "All active US physicians in your appetite states and specialties — roughly "
     "1.1M MDs/DOs nationally, or ~150-250k if scoped to your footprint",
     "physician (NPI), refreshed annually",
     "THIS IS THE ONE MOST LIKELY TO BE WRONG TODAY. RVU_WORK_TOTAL_RATIO_SPEC_OL "
     "divides a physician's work RVUs by 'their specialty average'. If that average "
     "is computed on MagMutual's book, it is your own selection bias, not a peer "
     "norm — and it shifts every year as your mix changes. Compute it on national "
     "CMS data. Same for practice-size percentiles."),
    ("Credibility complement",
     "Industry or national specialty x state expected loss cost",
     "specialty x state x year",
     "The current complement is a flat portfolio score of 5. A neurosurgeon in "
     "Philadelphia and a dermatologist in Macon should not both regress toward the "
     "same value."),
    ("Prospect / submission data",
     "Any physician you might quote, insured or not",
     "physician (NPI)",
     "To score new business you need external attributes on physicians you have "
     "never covered. This is why NPI coverage across the whole universe matters, "
     "not just your book."),
]
body(ws, pop_start, pop, [22, 34, 22, 76], wrap=(2, 3, 4), h=88,
     fill=lambda v: WARN if "MOST LIKELY TO BE WRONG" in v[3] else None)
tbl(ws, "Populations", r, pop_start + len(pop) - 1, 4)
r = pop_start + len(pop) + 1
para(ws, r,
     "Hospital data: you need CMS attributes for every hospital your insureds are "
     "affiliated with, not only those with a MagMutual relationship. Hospital "
     "Rating is currently null on 59% of records, and 'no affiliation captured' is "
     "being conflated with 'office-based practice'. Those are different risks.",
     height=44); r += 2

para(ws, r, "4. ATTRIBUTES — see the other sheets", H2); r += 1
para(ws, r,
     "Required Columns: 7 keys the harness cannot run without.  "
     "Scored Variables: the 26 the model currently uses.  "
     "Recommended Additions: 18 gaps, ranked by value.  "
     "External Reference Data: NPI-joinable sources.  "
     "Validation Rules: gates to run at ingest.", height=32)

# ===========================================================================
# 2. REQUIRED COLUMNS
# ===========================================================================
ws = sheet("Required Columns", "Required columns",
           "The harness raises a BLOCKER or refuses to run without these. Names are "
           "configurable via column_map.json — what matters is that the CONTENT "
           "exists.")
head(ws, 4, ["Column (default name)", "Role", "Type", "Nullable",
             "Definition", "Source", "Validation"])
req = [
    ("RISK_CISID", "Physician key", "int/str", "No",
     "Stable identifier for the individual physician across years.",
     "Oasis / magstage.dm_policy_pv (risk_cisid)",
     "Unique with COVERAGE_YEAR. No nulls."),
    ("NPI", "External join key", "10-digit str", "No",
     "National Provider Identifier. The spine for every external source.",
     "Oasis; validate against NPPES",
     "10 digits, Luhn check, present on >99% of rows. You confirmed near-complete "
     "coverage — this unblocks all external enrichment."),
    ("COVERAGE_YEAR", "Time key", "int", "No",
     "Policy or coverage year the row describes.",
     "Derived from policy effective date",
     "Contiguous range. Flag any year with <1% of total rows as immature."),
    ("POLICY_NUMBER_TRIMMED", "Policy key", "str", "No",
     "Policy the physician sat on that year.",
     "magstage.dm_policy_pv (policy_number_trimmed)",
     "Not null. Many physicians to one policy is expected."),
    ("AMT_GROSS_RPTD_TOTAL_TRENDED", "TARGET numerator", "float", "No (0 allowed)",
     "Gross reported losses, indemnity + expense, trended and developed. Must be "
     "ACTUAL losses.",
     "DHC / Snowflake claims pipeline",
     "Zero for ~93% of rows. If it is rarely zero, it is not actual loss — the "
     "adequacy_reality check exists for exactly this."),
    ("WRTN_PREM_AMT_ITD_BURNED_CLASS_OL", "Exposure denominator (loss_ratio)",
     "float", "No",
     "Written premium, burned, class on-levelled.",
     "magstage.dm_policy_pv (wrtn_prem_amt_itd) + on-levelling",
     "> 0. Rows at or below zero are dropped."),
    ("BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED", "Exposure denominator (loss_cost)",
     "float", "No",
     "BCE-state exposure, trended, developed, ILF-capped. Rate-INDEPENDENT.",
     "Actuarial exposure build",
     "> 0. Required to run --target loss_cost, which is how you test whether lift "
     "survives without the circular tiers."),
    ("CNT_GROSS_RPTD_TOTAL_GT_0", "Claim count", "int", "No (0 allowed)",
     "Count of claims with gross reported total above zero.",
     "magstage.claims_data_mart",
     "~93% zeros expected. Drives the burn-factor detection."),
    ("PAS_COMPOSITE_SCORE", "Model output", "float 1-10", "No",
     "The composite score being validated.",
     "PAS scoring pipeline",
     "Between 1 and 10. Check dispersion — if 90% sit in bands 4-5 the score "
     "cannot differentiate the book."),
    ("CREDIBILITY_Z", "Credibility factor", "float 0-1", "Yes",
     "Credibility weight applied to Adequacy sub-scores.",
     "PAS scoring pipeline",
     "0 to 1. Needed to reconcile reason codes when sub-scores are persisted "
     "PRE-blend."),
]
body(ws, 5, req, [34, 26, 12, 12, 46, 34, 52], wrap=(5, 6, 7), h=62,
     fill=lambda v: REQ)
tbl(ws, "ReqCols", 4, 4 + len(req), 7)
para(ws, 4 + len(req) + 2,
     "Also expected: PAS_ADEQUACY_SCORE, PAS_CAPACITY_SCORE, PAS_APPETITE_SCORE, "
     "PAS_ENVIRONMENT_SCORE. Absent, component-level diagnostics are skipped but "
     "the run continues.", S)

# ===========================================================================
# 3. SCORED VARIABLES
# ===========================================================================
ws = sheet("Scored Variables", "The 26 scored variables",
           "Each needs a raw driver column AND its 1-10 score column. The deck "
           "describes 23; the design workbook's composite formula uses a different "
           "set including Premium Volume, Excess/Primary and Physician Age. Both "
           "are listed so the harness can report which actually exist.")
head(ws, 4, ["Variable", "Component", "Weight", "Raw column", "Score column",
             "Grain of the raw value", "Known issue"])
sv = [
    ("total_loss_cost", "Adequacy", 0.20, "ULT_Total_LOSS_COST_PER_BCE",
     "SCORE_TOTAL_LOSS_COST", "physician-year", ""),
    ("indemnity_loss_cost", "Adequacy", 0.10, "ULT_Indemnity_LOSS_COST_PER_BCE",
     "SCORE_INDEMNITY_LOSS_COST", "physician-year",
     "Shares a denominator with total_loss_cost — expect high VIF."),
    ("expense_loss_cost", "Adequacy", 0.05, "ULT_Expense_LOSS_COST_PER_BCE",
     "SCORE_EXPENSE_LOSS_COST", "physician-year", "Same denominator again."),
    ("total_frequency", "Adequacy", 0.10, "ULT_Total_FREQUENCY_PER_FTE",
     "SCORE_TOTAL_FREQUENCY", "physician-year",
     "Documented median 0.955 with no zeros, while 93% of physicians are "
     "claim-free. Not a frequency. Confirm what this column holds."),
    ("indemnity_frequency", "Adequacy", 0.05, "ULT_Indemnity_FREQUENCY_PER_FTE",
     "SCORE_INDEMNITY_FREQUENCY", "physician-year", "As above."),
    ("total_severity", "Adequacy", 0.05, "ULT_Total_SEVERITY",
     "SCORE_TOTAL_SEVERITY", "physician-year",
     "Only defined where claims exist, so null for ~93%."),
    ("actual_loss_ratio", "Adequacy", 0.10, "ULT_ACTUAL_LOSS_RATIO_BURNED",
     "SCORE_ACTUAL_LOSS_RATIO", "physician-year",
     "Documented as BCE_ST_..._BURNED / BCE_ST — both sides are EXPOSURE columns, "
     "so this is a burn factor, not loss over premium."),
    ("loss_free_years", "Adequacy", 0.10, "CV_LOSS_FREE_YEARS",
     "SCORE_LOSS_FREE_YEARS", "physician",
     "-99 sentinel for unknown, and the documented bins map '0 or negative' to 10. "
     "Missing data is scored as your worst risk."),
    ("limits_to_premium", "Adequacy", 0.10, "LIMITS_TO_PREMIUM_RATIO",
     "SCORE_LIMITS_TO_PREMIUM", "MIXED — policy limit / physician premium",
     "Numerator is policy-level, denominator physician-level."),
    ("premium_volume", "Adequacy", 0.10, "WRTN_PREM_AMT_ITD_BURNED",
     "SCORE_PREMIUM_VOLUME", "physician-year",
     "Scores SIZE as QUALITY — bigger accounts score better by construction. Also "
     "duplicates the premium-based credibility Z."),
    ("excess_primary", "Adequacy", 0.05, "ATT_PER_M", "SCORE_EXCESS_PRIMARY",
     "policy", "97% primary, so 3% of the book carries this variable."),
    ("per_occ_limit", "Capacity", 0.20, "TOP_PER_M", "SCORE_PER_OCC_LIMIT",
     "POLICY",
     "77% of policies sit at exactly $1M. Cannot differentiate three-quarters of "
     "the book, on the largest single Capacity weight."),
    ("aggregate_limit", "Capacity", 0.10, "TOP_AGG_M", "SCORE_AGGREGATE_LIMIT",
     "POLICY", "Heavily concentrated at $3M."),
    ("risk_count", "Capacity", 0.10, "RISK_COUNT", "SCORE_RISK_COUNT",
     "POLICY",
     "Group aggregation exposure charged to each individual physician."),
    ("specialty_tier", "Appetite", 0.25, "OL_RISK_SPECIALTY_DESC",
     "SCORE_SPECIALTY_TIER", "physician-year",
     "TIER CUT ON PORTFOLIO LOSS RATIO. Measures your rate adequacy, not risk. "
     "Re-tier on loss cost per exposure."),
    ("state_venue", "Appetite", 0.15, "ST", "SCORE_STATE_VENUE",
     "physician-year",
     "Same circularity. Also state-level only — no county or venue granularity — "
     "and predates Georgia SB 68/69."),
    ("years_since_grad", "Appetite", 0.10, "YEARS_SINCE_GRAD_IMPUTED",
     "SCORE_YEARS_SINCE_GRAD", "physician",
     "Range -5 to 96. Imputed. Hand-crafted U-shape needs empirical support."),
    ("rvu_ratio", "Appetite", 0.10, "RVU_WORK_TOTAL_RATIO_SPEC_OL",
     "SCORE_RVU_RATIO", "physician-year",
     "24% null. 'Specialty average' must come from NATIONAL CMS data, not "
     "MagMutual's book, or it is your own selection bias."),
    ("tenure", "Appetite", 0.05, "CV_YEARS_WITH_MAG", "SCORE_TENURE",
     "physician", ""),
    ("hospital_rating", "Appetite", 0.05, "HOSP_HOSPITALCOMPARE_OVERALLRATING",
     "SCORE_HOSPITAL_RATING", "hospital",
     "59% null. Five star values spread over ten bands. PSI-90 and the HCAHPS "
     "doctor-communication item are closer to malpractice causation."),
    ("practice_size", "Appetite", 0.05, "WITH_WHOM_LOCATION_DISTINCT_NPI",
     "SCORE_PRACTICE_SIZE", "practice location", "14% null."),
    ("physician_age", "Appetite", 0.07, "AGE_IMPUTED", "SCORE_PHYSICIAN_AGE",
     "physician",
     "r~0.95 with years_since_grad. Range 22-123. Workbook flags the "
     "double-count itself."),
    ("income_inequality", "Environment", 0.05, "INCOME_RATIO",
     "SCORE_INCOME_INEQUALITY", "county",
     "Socioeconomic proxy. If PAS ever touches price, this is a "
     "disparate-impact question."),
    ("pop_density", "Environment", 0.05, "POP_DENSITY_SQ_MILES",
     "SCORE_POP_DENSITY", "county", "As above."),
    ("violent_crime", "Environment", 0.03, "VIOLENT_CRIME_RATE_PER_100K",
     "SCORE_VIOLENT_CRIME", "county",
     "Carried over from the Property PAS. Not an MPL driver — venue litigiousness "
     "is."),
    ("pct_uninsured", "Environment", 0.02, "PCT_UNINSURED",
     "SCORE_PCT_UNINSURED", "county", "As above."),
]
body(ws, 5, sv, [24, 13, 8, 38, 32, 30, 62], wrap=(6, 7), h=54,
     fill=lambda v: (WARN if ("POLICY" in v[5] or "MIXED" in v[5]
                              or "CUT ON PORTFOLIO" in v[6]) else None))
tbl(ws, "ScoredVars", 4, 4 + len(sv), 7)
tot = 4 + len(sv) + 1
ws.cell(row=tot, column=1, value="Sum of weights").font = BB
ws.cell(row=tot, column=3, value=f"=SUM(C5:C{4 + len(sv)})").font = BB
ws.cell(row=tot, column=4,
        value="Exceeds 1.00 because deck-only and workbook-only members are both "
              "listed. Weights are normalised within each component at runtime."
        ).font = S

# ===========================================================================
# 4. RECOMMENDED ADDITIONS
# ===========================================================================
ws = sheet("Recommended Adds", "Recommended additions",
           "Ranked by expected value. Items 1-4 are internal, cost nothing to "
           "obtain, and are absent from the current 23.")
head(ws, 4, ["#", "Attribute", "Grain", "Why it matters", "Source"])
adds = [
    (1, "Risk-management hotline call count and topic",
     "physician-year",
     "Your PARS analogue and probably the single best variable available to you. "
     "Thirty years of Vanderbilt research shows unsolicited patient complaints "
     "predict future claims INDEPENDENT of clinical volume, with ~3% of clinicians "
     "driving a disproportionate share. No competitor can buy this.",
     "MagMutual risk-management / hotline system"),
    (2, "Claim allegation and injury code",
     "claim",
     "'Failure to diagnose' is the #1 category and your own deck cites it, yet no "
     "allegation feature exists. Diagnosis vs procedure vs medication vs consent "
     "vs communication behave very differently.",
     "magstage.claims_data_mart (injury code)"),
    (3, "APP supervision count (NPs/PAs supervised)",
     "physician-year",
     "Major vicarious-liability exposure, entirely absent from the model.",
     "Underwriting application / roster"),
    (4, "Suit-filed flag, county of filing, disposition",
     "claim",
     "Enables a real venue feature at county level and separates claims that "
     "became suits from those that did not.",
     "Claims system"),
    (5, "High-risk procedure indicators",
     "physician-year",
     "OB deliveries and C-section rate, spine, bariatric, cosmetic, interventional. "
     "Specialty tier at 25% is doing work that procedure mix should do. Megan's "
     "sheet flags exactly this: one radiology code cannot separate surgical from "
     "non-surgical.",
     "HCPCS mix from CMS; internal application"),
    (6, "Application credentialing answers",
     "physician-year",
     "Prior discipline, privilege restrictions, prior claims, substance issues. "
     "Already collected, never scored.",
     "Underwriting application"),
    (7, "Board certification status and lapse",
     "physician",
     "Standard credentialing signal, absent here.",
     "ABMS / NPPES"),
    (8, "Prior carrier and prior-carrier loss runs",
     "physician",
     "The only loss experience available for new business, which is where "
     "Adequacy is otherwise empty.",
     "Submission documents"),
    (9, "Recency-weighted prior claim count",
     "physician-year",
     "NEJM/Studdert 2016 showed prior paid claims strongly predict recurrence. "
     "Loss-free years is a crude proxy — a decayed count is far stronger.",
     "Derived from claims"),
    (10, "County / ZIP of practice location",
     "physician-year",
     "State-level venue is too coarse. Fulton County is not Georgia.",
     "Oasis address"),
    (11, "Tort-law feature table with effective dates",
     "state x date",
     "Caps and whether struck down, certificate of merit, pre-suit panels, statute "
     "of repose, joint and several, collateral source, PCF. Georgia SB 68/69 took "
     "effect April 2025 and a 2017-24 fit misses it entirely.",
     "Build and maintain internally"),
    (12, "Plaintiff-bar density",
     "county-year",
     "A direct litigiousness measure, far better than violent crime rate.",
     "Census County Business Patterns, NAICS 5411"),
    (13, "Incident and near-miss reports",
     "physician-year",
     "Precedes claims. Earliest available signal.",
     "Risk-management system"),
    (14, "Part-time / FTE status, locum, telemedicine, multi-state",
     "physician-year",
     "Exposure normalisation and distinct risk profiles.",
     "Policy administration"),
    (15, "Retro date, claims-made year, tail/DDR issued",
     "policy",
     "Latent exposure. Retro date appears in the candidate list but not the "
     "final 23.",
     "Policy administration"),
    (16, "Coverage gaps and carrier-switching frequency",
     "physician",
     "Churn signal, cheap to derive.",
     "Derived from policy history"),
    (17, "Rate adequacy — bound premium vs actuarial indication",
     "physician-year",
     "In your own candidate list as High priority, then dropped. The honest way to "
     "measure pricing adequacy without the loss-ratio circularity.",
     "Pricing tool / data_share.psl_model_summary"),
    (18, "Risk-management CME and survey participation",
     "physician-year",
     "A mitigating factor. Also gives underwriters something actionable to "
     "recommend.",
     "Risk-management system"),
]
body(ws, 5, adds, [5, 34, 18, 74, 32], wrap=(2, 4, 5), h=62,
     fill=lambda v: NICE if v[0] <= 4 else None)
tbl(ws, "Adds", 4, 4 + len(adds), 5)

# ===========================================================================
# 5. EXTERNAL DATA
# ===========================================================================
ws = sheet("External Data", "External reference data, joinable on NPI",
           "You confirmed NPI is populated on nearly all risks, so all of this is "
           "reachable. Pull for the NATIONAL universe in your appetite footprint, "
           "not only your insureds — peer benchmarks computed on your own book are "
           "selection bias.")
head(ws, 4, ["Source", "Cost", "Grain", "Key fields", "Use in PAS", "Join key"])
ext = [
    ("CMS Medicare Physician & Other Practitioners — by Provider", "Free",
     "NPI x year",
     "Total services, unique beneficiaries, allowed and standardised payments, "
     "beneficiary mean age, MEAN HCC RISK SCORE, chronic-condition prevalence",
     "Patient acuity and true volume. Lets you compute frequency per encounter "
     "instead of per FTE — a much better denominator. Also the correct source for "
     "the national specialty RVU average.",
     "NPI"),
    ("CMS same dataset — by Provider and Service", "Free", "NPI x HCPCS x year",
     "Procedure-level volumes",
     "Procedure risk mix. Fills the surgical vs non-surgical gap Megan flagged.",
     "NPI"),
    ("CMS Open Payments", "Free", "NPI x year",
     "Industry general, research and ownership payments",
     "Published association with higher PARS complaint scores — framed as two "
     "expressions of the same physician phenotype.", "NPI"),
    ("CMS Care Compare — Doctors and Clinicians", "Free", "NPI",
     "Specialty, graduation year, medical school, group and hospital affiliation, "
     "MIPS scores",
     "Fills AGE/YEARS_SINCE_GRAD rather than imputing, and gives the affiliation "
     "graph.", "NPI"),
    ("CMS Hospital Compare / Care Compare", "Free", "CCN (hospital)",
     "Star rating, PSI-90 patient safety composite, HCAHPS communication, HAI, "
     "readmissions, mortality",
     "PSI-90 and the HCAHPS doctor-communication item are closer to malpractice "
     "causation than the overall star rating currently used.",
     "CCN via affiliation"),
    ("CMS Part D Prescriber", "Free", "NPI x year",
     "Opioid and benzodiazepine prescribing rates, antibiotic patterns",
     "Documented liability exposure, absent from the model.", "NPI"),
    ("NPPES / NPI Registry", "Free", "NPI",
     "All taxonomy codes, enumeration date, practice locations, deactivations",
     "Validates NPI, gives sub-specialty detail beyond one specialty code.", "NPI"),
    ("Census ACS + County Business Patterns", "Free", "County",
     "Income, inequality, uninsured rate, density; NAICS 5411 legal-services "
     "establishments per capita",
     "Replaces violent crime rate with plaintiff-bar density — an actual "
     "litigiousness measure.", "County FIPS"),
    ("HRSA HPSA / RUCA", "Free", "County / tract",
     "Shortage designations, rurality, provider-to-population ratios",
     "Access strain drives volume and handoff risk.", "County FIPS"),
    ("OIG LEIE exclusions", "Free", "NPI / name",
     "Medicare/Medicaid exclusion actions", "Hard adverse-action signal.", "NPI"),
    ("NPDB Public Use File", "Free",
     "STATE ONLY — de-identified",
     "Malpractice payments, adverse actions, by state",
     "BENCHMARKING ONLY. Federal law forbids using it alone or combined with other "
     "data to identify a practitioner. Never a physician-level feature. Whether "
     "MagMutual qualifies as an authorised querier for identified data is a legal "
     "question — 'health plans' are listed, an MPL carrier arguably is not.", "n/a"),
    ("Court-docket monitoring (UniCourt, Trellis, Docket Alarm)", "Paid",
     "Case",
     "New MPL filings naming your insureds",
     "Highest operational value per dollar: you learn about suits before the "
     "insured reports them. Useful independent of the score.", "Name / NPI match"),
    ("Litigation analytics (Westlaw, Lex Machina)", "Paid", "County / case",
     "Verdict history, time to disposition",
     "County venue index. You already have CoCounsel connected.", "County"),
    ("Definitive Healthcare / IQVIA", "Paid", "NPI",
     "All-payer procedure volumes, full affiliation graph",
     "Medicare-only volume badly understates surgeons and paediatricians.", "NPI"),
    ("Continuous monitoring (Verisys, ProviderTrust)", "Paid", "NPI",
     "State board disciplinary actions, license status, sanctions",
     "State board discipline is a documented predictor and is absent today.", "NPI"),
]
body(ws, 5, ext, [40, 8, 20, 44, 66, 18], wrap=(4, 5, 6), h=68,
     fill=lambda v: WARN if "BENCHMARKING ONLY" in v[4] else None)
tbl(ws, "Ext", 4, 4 + len(ext), 6)

# ===========================================================================
# 6. VALIDATION RULES
# ===========================================================================
ws = sheet("Validation Rules", "Ingest validation rules",
           "Run these before scoring, not after. Each maps to a check in the "
           "harness.")
head(ws, 4, ["#", "Rule", "Threshold", "If it fails", "Harness check"])
val = [
    (1, "Grain is unique on (RISK_CISID, COVERAGE_YEAR)", "100% of rows",
     "Every premium-weighted mean is wrong — physicians counted more than once.",
     "manual; add to ingest"),
    (2, "NPI present and 10 digits", ">99%",
     "External enrichment silently drops those rows.", "check_schema"),
    (3, "Claim count is zero for the great majority", "~93% zeros",
     "If not, the loss columns are not actual losses.",
     "check_adequacy_is_experience"),
    (4, "Every loss-experience variable is zero-inflated to a similar degree",
     "zero share >20%",
     "The variable is a burn or on-level factor, not experience.",
     "check_adequacy_is_experience"),
    (5, "Sentinel values converted to NaN before binning", "zero sentinels scored",
     "Unknown data is scored as your worst risk.", "check_data_quality"),
    (6, "Exposure strictly positive", "100% after filter",
     "Rows are silently dropped; if all are, the run aborts.", "prepare()"),
    (7, "AGE within 24-85, YEARS_SINCE_GRAD within 0-60", ">99.5%",
     "Age 123 and -5 years since graduation are in the current data.",
     "check_data_quality"),
    (8, "Composite score within 1-10 and reasonably dispersed",
     "std dev >1.0; bands 4-5 under 60%",
     "The score cannot differentiate the book; portfolio band targets cannot bind.",
     "reasons.dispersion"),
    (9, "Attribution reconciles to the published composite", "residual <0.5",
     "Reason codes describe a different model than the one that scored the "
     "physician.", "reasons.reconciliation"),
    (10, "No variable derived from the target", "zero circular variables",
     "Lift is invalid, not merely weak.", "check_circularity"),
    (11, "Coverage years contiguous and maturity documented", "manual review",
     "Validating on green years biases toward finding no signal.",
     "check_composite_lift"),
    (12, "Distributions within tolerance of the design workbook", "within 25%",
     "Either the data moved or the documentation is stale. Reconcile before any "
     "UW review.", "check_data_quality"),
]
body(ws, 5, val, [5, 52, 26, 62, 26], wrap=(2, 4), h=48)
tbl(ws, "Rules", 4, 4 + len(val), 5)

del wb["Sheet"]
out = Path("/mnt/user-data/outputs/PAS_Input_Data_Dictionary.xlsx")
wb.save(out)
print(f"wrote {out}")
print("sheets:", wb.sheetnames)
