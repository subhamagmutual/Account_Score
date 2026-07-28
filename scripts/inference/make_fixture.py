"""
Build a synthetic scored dataset that reproduces the pathologies documented in
Physician_MPL_Account_Score_Design_v2.xlsx, so the harness can be verified
before it is ever pointed at real data.

Each block is labelled with the pathology it plants and the check that should
catch it. If a check stops firing here, the check is broken.
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(20260727)
N = 60_000

df = pd.DataFrame(index=range(N))
df["POLICY_NUMBER_TRIMMED"] = [f"P{i//7:06d}" for i in range(N)]
df["RISK_CISID"] = rng.integers(1, 45_000, N)
df["COVERAGE_YEAR"] = rng.choice(range(2017, 2025), N)

# --- Ground truth: 93% claim-free, heavy-tailed severity -------------------
specialties = [
    "FP/GP-no surgery", "Internal Medicine-no surgery", "Psychiatry (including child)",
    "Obstetrics and gynecology--surgery", "Neurosurgery", "Radiology-major invasive",
    "Orthopedic Surgery-NO Spinal Surgery", "Emergency Medicine-no major surgery",
    "Anesthesiology", "Dermatology-including minor surgery", "Urology-surgery",
    "Cardiovascular Disease-minor surgery", "General Surgery (N.O.C.)",
]
true_relativity = dict(zip(specialties,
                           [0.55, 0.62, 0.40, 1.45, 2.30, 1.90,
                            1.05, 1.25, 0.85, 0.45, 1.30, 1.20, 1.35]))
df["OL_RISK_SPECIALTY_DESC"] = rng.choice(specialties, N)

states = ["GA", "FL", "NC", "SC", "AL", "VA", "KY", "TN", "IL", "NJ", "NM", "MD"]
state_true = dict(zip(states,
                      [1.20, 0.95, 0.70, 1.05, 0.90, 0.85, 0.95, 0.90,
                       1.45, 1.55, 1.60, 1.40]))
df["ST"] = rng.choice(states, N, p=[.31, .24, .11, .09, .06, .05,
                                    .04, .03, .02, .02, .015, .015])

rel = (df["OL_RISK_SPECIALTY_DESC"].map(true_relativity)
       * df["ST"].map(state_true)).to_numpy()

df["BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED"] = np.round(
    rng.lognormal(0.4, 0.7, N) * 2.0, 3)
df["WRTN_PREM_AMT_ITD_BURNED"] = np.round(
    rng.lognormal(8.8, 1.0, N), 0)
df["WRTN_PREM_AMT_ITD_BURNED_CLASS_OL"] = np.round(
    df["WRTN_PREM_AMT_ITD_BURNED"] * rng.uniform(0.95, 1.10, N), 0)

lam = 0.075 * rel * (df["BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED"] / 2.0)
df["CNT_GROSS_RPTD_TOTAL_GT_0"] = rng.poisson(lam)
sev = rng.lognormal(11.6, 1.5, N)
df["AMT_GROSS_RPTD_TOTAL_TRENDED"] = np.round(
    df["CNT_GROSS_RPTD_TOTAL_GT_0"] * sev, 0)
df["AMT_GROSS_RPTD_IND_TRENDED"] = np.round(
    df["AMT_GROSS_RPTD_TOTAL_TRENDED"] * rng.uniform(0.5, 0.8, N), 0)

print(f"claim-free share: {(df['CNT_GROSS_RPTD_TOTAL_GT_0'] == 0).mean():.1%}")

# === PATHOLOGY 1 ===========================================================
# "Burned Loss Ratio" and "Claim Frequency" are burn/on-level factors, not
# loss experience: 100% non-null, 0% zero, tightly centred near 1.0, while 93%
# of physicians are claim-free.
# Expected catch: check_adequacy_is_experience -> BLOCKER
df["ULT_ACTUAL_LOSS_RATIO_BURNED"] = np.round(rng.normal(0.98, 0.075, N), 4)
df["ULT_Total_FREQUENCY_PER_FTE"] = np.round(
    np.clip(rng.beta(9, 0.6, N), 0.05, 1.15), 4)
df["ULT_Indemnity_FREQUENCY_PER_FTE"] = np.round(
    df["ULT_Total_FREQUENCY_PER_FTE"] * rng.uniform(0.9, 1.0, N), 4)

# === PATHOLOGY 2 ===========================================================
# Four Adequacy drivers share a numerator or denominator by construction.
# Expected catch: check_redundancy -> HIGH (VIF > 10)
base_lc = df["AMT_GROSS_RPTD_TOTAL_TRENDED"] / df["BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED"]
df["ULT_Total_LOSS_COST_PER_BCE"] = np.round(base_lc, 4)
df["ULT_Indemnity_LOSS_COST_PER_BCE"] = np.round(base_lc * 0.65, 4)
df["ULT_Expense_LOSS_COST_PER_BCE"] = np.round(base_lc * 0.35, 4)
df["ULT_Total_SEVERITY"] = np.where(
    df["CNT_GROSS_RPTD_TOTAL_GT_0"] > 0,
    df["AMT_GROSS_RPTD_TOTAL_TRENDED"] / df["CNT_GROSS_RPTD_TOTAL_GT_0"].clip(lower=1),
    np.nan)

# === PATHOLOGY 3 ===========================================================
# CV_LOSS_FREE_YEARS carries a -99 sentinel, and the documented binning maps
# "0 or negative" to score 10. Unknown data is scored as the worst risk.
# Expected catch: check_data_quality -> BLOCKER (sentinel_scored)
lfy = rng.integers(0, 35, N).astype(float)
lfy[rng.random(N) < 0.04] = -99.0
df["CV_LOSS_FREE_YEARS"] = lfy

# === PATHOLOGY 4 ===========================================================
# 77% of policies sit at exactly $1M per-occurrence, and $1M maps to bands
# 3, 4 AND 5 -- three-quarters of the book is tied on a 20%-weight variable.
# Expected catch: check_discrimination -> HIGH
limits = rng.choice([0.25, 0.5, 1.0, 1.2, 2.0, 3.0, 5.0], N,
                    p=[.02, .04, .77, .03, .08, .05, .01])
df["TOP_PER_M"] = limits
df["TOP_AGG_M"] = np.where(limits <= 1.0, limits * 3, limits * 2)
df["ATT_PER_M"] = np.where(rng.random(N) < 0.03, rng.choice([0.25, 0.5, 1.0], N), 0.0)
df["LIMITS_TO_PREMIUM_RATIO"] = np.round(
    limits * 1e6 / df["WRTN_PREM_AMT_ITD_BURNED"].clip(lower=1), 2)

# --- Remaining drivers -----------------------------------------------------
df["RISK_COUNT"] = rng.choice([1, 2, 5, 14, 40, 90, 180, 320, 500], N,
                              p=[.14, .12, .18, .18, .15, .1, .07, .04, .02])
df["YEARS_SINCE_GRAD_IMPUTED"] = np.clip(rng.normal(23, 11, N), -5, 96).round(0)
df["AGE_IMPUTED"] = (df["YEARS_SINCE_GRAD_IMPUTED"] + 29
                     + rng.normal(0, 1.2, N)).round(0)   # r ~ 0.95 by design
df["CV_YEARS_WITH_MAG"] = np.clip(rng.geometric(0.12, N), 0, 30)

# 24% missing RVU, 59% missing hospital rating, 14% missing practice size
rvu = rng.lognormal(-0.5, 0.9, N)
rvu[rng.random(N) < 0.24] = np.nan
df["RVU_WORK_TOTAL_RATIO_SPEC_OL"] = np.round(rvu, 3)
hosp = rng.choice([1., 2., 3., 4., 5.], N, p=[.06, .18, .38, .27, .11])
hosp[rng.random(N) < 0.59] = np.nan
df["HOSP_HOSPITALCOMPARE_OVERALLRATING"] = hosp
psz = rng.choice([1, 2, 4, 7, 25, 60, 120, 400], N,
                 p=[.22, .13, .17, .16, .14, .09, .06, .03]).astype(float)
psz[rng.random(N) < 0.14] = np.nan
df["WITH_WHOM_LOCATION_DISTINCT_NPI"] = psz

df["INCOME_RATIO"] = np.round(rng.normal(4.68, 0.75, N), 2)
df["POP_DENSITY_SQ_MILES"] = np.round(rng.lognormal(6.4, 1.1, N), 0)
df["VIOLENT_CRIME_RATE_PER_100K"] = np.round(rng.normal(423, 200, N).clip(20), 0)
df["PCT_UNINSURED"] = np.round(rng.normal(14, 3.6, N).clip(3, 35), 1)


# --- Binning helpers -------------------------------------------------------
def bin_edges(x, edges):
    out = np.full(len(x), np.nan)
    v = pd.to_numeric(x, errors="coerce").to_numpy(float)
    ok = np.isfinite(v)
    out[ok] = np.clip(np.searchsorted(edges, v[ok], side="right") + 1, 1, 10)
    return out


def mean_anchored(x, invert=False):
    """The PAS band_width = portfolio_mean / 4.5 scheme."""
    v = pd.to_numeric(x, errors="coerce").to_numpy(float)
    ok = np.isfinite(v)
    if ok.sum() == 0:
        return np.full(len(v), np.nan)
    bw = np.nanmean(v[ok]) / 4.5
    if bw <= 0:
        return np.full(len(v), np.nan)
    s = np.full(len(v), np.nan)
    s[ok] = np.clip(np.floor(v[ok] / bw) + 1, 1, 10)
    if invert:
        s[ok] = 11 - s[ok]
    return s


df["SCORE_ACTUAL_LOSS_RATIO"] = bin_edges(
    df["ULT_ACTUAL_LOSS_RATIO_BURNED"],
    [.88, .91, .94, .98, 1.02, 1.05, 1.08, 1.11, 1.15])
df["SCORE_TOTAL_FREQUENCY"] = bin_edges(
    df["ULT_Total_FREQUENCY_PER_FTE"],
    [.25, .50, .75, .90, .95, .97, .98, .99, 1.00])
df["SCORE_INDEMNITY_FREQUENCY"] = bin_edges(
    df["ULT_Indemnity_FREQUENCY_PER_FTE"],
    [.25, .50, .75, .90, .95, .97, .98, .99, 1.00])
df["SCORE_TOTAL_LOSS_COST"] = mean_anchored(df["ULT_Total_LOSS_COST_PER_BCE"])
df["SCORE_INDEMNITY_LOSS_COST"] = mean_anchored(df["ULT_Indemnity_LOSS_COST_PER_BCE"])
df["SCORE_EXPENSE_LOSS_COST"] = mean_anchored(df["ULT_Expense_LOSS_COST_PER_BCE"])
df["SCORE_TOTAL_SEVERITY"] = mean_anchored(df["ULT_Total_SEVERITY"])

# PATHOLOGY 3 realised: -99 lands in the "0 or negative" -> 10 bucket.
lfy_score = np.select(
    [df["CV_LOSS_FREE_YEARS"] >= 30, df["CV_LOSS_FREE_YEARS"] >= 25,
     df["CV_LOSS_FREE_YEARS"] >= 20, df["CV_LOSS_FREE_YEARS"] >= 15,
     df["CV_LOSS_FREE_YEARS"] >= 10, df["CV_LOSS_FREE_YEARS"] >= 7,
     df["CV_LOSS_FREE_YEARS"] >= 4, df["CV_LOSS_FREE_YEARS"] >= 2,
     df["CV_LOSS_FREE_YEARS"] >= 1],
    [1, 2, 3, 4, 5, 6, 7, 8, 9], default=10)
df["SCORE_LOSS_FREE_YEARS"] = lfy_score.astype(float)

df["SCORE_LIMITS_TO_PREMIUM"] = bin_edges(
    df["LIMITS_TO_PREMIUM_RATIO"], [30, 50, 80, 130, 200, 400, 800, 2000, 5000])
df["SCORE_PREMIUM_VOLUME"] = bin_edges(
    -df["WRTN_PREM_AMT_ITD_BURNED"],
    [-30000, -22000, -15000, -10000, -5000, -3000, -1500, -800, -400])
df["SCORE_EXCESS_PRIMARY"] = np.where(
    df["ATT_PER_M"] <= 0, 3.0, bin_edges(df["ATT_PER_M"], [0, .25, .5, 1, 2]))

# PATHOLOGY 4 realised: $1M -> band 4, but 0.25/0.5 -> 1/2 and everything
# above -> 7+, so 77% of the book collapses onto a single score.
df["SCORE_PER_OCC_LIMIT"] = np.select(
    [df["TOP_PER_M"] <= .25, df["TOP_PER_M"] <= .5, df["TOP_PER_M"] <= 1.0,
     df["TOP_PER_M"] <= 1.2, df["TOP_PER_M"] <= 2.0, df["TOP_PER_M"] <= 2.65,
     df["TOP_PER_M"] <= 3.0],
    [1, 2, 4, 6, 7, 8, 9], default=10).astype(float)
df["SCORE_AGGREGATE_LIMIT"] = bin_edges(df["TOP_AGG_M"], [.75, 1, 2, 3, 3.5, 5, 7, 9, 10])
df["SCORE_RISK_COUNT"] = bin_edges(df["RISK_COUNT"], [1, 3, 8, 20, 50, 100, 200, 300, 400])

# === PATHOLOGY 5 ===========================================================
# Specialty and state tiers cut on realised LOSS RATIO -- i.e. on the target.
# Expected catch: check_circularity -> BLOCKER
lr = (df["AMT_GROSS_RPTD_TOTAL_TRENDED"]
      / df["WRTN_PREM_AMT_ITD_BURNED_CLASS_OL"].clip(lower=1))
for raw, score_col in [("OL_RISK_SPECIALTY_DESC", "SCORE_SPECIALTY_TIER"),
                       ("ST", "SCORE_STATE_VENUE")]:
    grp = lr.groupby(df[raw]).mean()
    tiers = pd.qcut(grp.rank(method="first"), 10, labels=range(1, 11)).astype(int)
    df[score_col] = df[raw].map(tiers).astype(float)

# U-shaped hand-crafted bands
df["SCORE_YEARS_SINCE_GRAD"] = np.select(
    [df["YEARS_SINCE_GRAD_IMPUTED"].between(20, 30),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(15, 19),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(30, 35),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(12, 14),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(10, 11),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(35, 40),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(7, 9),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(40, 45),
     df["YEARS_SINCE_GRAD_IMPUTED"].between(4, 6)],
    [1, 2, 3, 4, 5, 6, 7, 8, 9], default=10).astype(float)
df["SCORE_PHYSICIAN_AGE"] = np.select(
    [df["AGE_IMPUTED"].between(42, 55), df["AGE_IMPUTED"].between(38, 41),
     df["AGE_IMPUTED"].between(56, 60), df["AGE_IMPUTED"].between(35, 37),
     df["AGE_IMPUTED"].between(61, 65), df["AGE_IMPUTED"].between(33, 34),
     df["AGE_IMPUTED"].between(66, 70), df["AGE_IMPUTED"].between(30, 32),
     df["AGE_IMPUTED"].between(71, 75)],
    [1, 2, 3, 4, 5, 6, 7, 8, 9], default=10).astype(float)

df["SCORE_RVU_RATIO"] = bin_edges(
    df["RVU_WORK_TOTAL_RATIO_SPEC_OL"], [.1, .25, .5, .8, 1.2, 1.6, 2.1, 2.85, 4.0])
df["SCORE_TENURE"] = bin_edges(
    -df["CV_YEARS_WITH_MAG"], [-20, -15, -11, -8, -6, -4, -3, -2, -1])

# PATHOLOGY 6: 5 star values spread across 10 bands, 59% missing.
# Expected catch: check_discrimination (MEDIUM) + check_effective_weights (HIGH)
df["SCORE_HOSPITAL_RATING"] = df["HOSP_HOSPITALCOMPARE_OVERALLRATING"].map(
    {5.0: 1.0, 4.0: 3.0, 3.0: 5.0, 2.0: 7.0, 1.0: 9.0})
df["SCORE_PRACTICE_SIZE"] = np.select(
    [df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(5, 20),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(3, 4),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(21, 40),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"] == 2,
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(41, 80),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"] == 1,
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(81, 150),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(151, 300),
     df["WITH_WHOM_LOCATION_DISTINCT_NPI"].between(301, 600)],
    [1, 2, 3, 4, 5, 6, 7, 8, 9], default=np.nan).astype(float)
df.loc[df["WITH_WHOM_LOCATION_DISTINCT_NPI"].isna(), "SCORE_PRACTICE_SIZE"] = np.nan

df["SCORE_INCOME_INEQUALITY"] = bin_edges(
    df["INCOME_RATIO"], [3.9, 4.1, 4.3, 4.6, 5.0, 5.3, 5.7, 6.0, 6.4])
df["SCORE_POP_DENSITY"] = bin_edges(
    df["POP_DENSITY_SQ_MILES"], [150, 275, 450, 615, 900, 1200, 1600, 2200, 3500])
df["SCORE_VIOLENT_CRIME"] = bin_edges(
    df["VIOLENT_CRIME_RATE_PER_100K"], [125, 200, 300, 420, 530, 620, 730, 810, 870])
df["SCORE_PCT_UNINSURED"] = bin_edges(
    df["PCT_UNINSURED"], [8, 10, 12, 14, 16, 17.5, 19, 20.5, 22])

# --- Composite with weight-zeroing ----------------------------------------
COMPONENTS = {
    "adequacy": ([("SCORE_TOTAL_LOSS_COST", .20), ("SCORE_INDEMNITY_LOSS_COST", .10),
                  ("SCORE_EXPENSE_LOSS_COST", .05), ("SCORE_TOTAL_FREQUENCY", .10),
                  ("SCORE_INDEMNITY_FREQUENCY", .05), ("SCORE_TOTAL_SEVERITY", .05),
                  ("SCORE_ACTUAL_LOSS_RATIO", .10), ("SCORE_LOSS_FREE_YEARS", .10),
                  ("SCORE_LIMITS_TO_PREMIUM", .10), ("SCORE_PREMIUM_VOLUME", .10),
                  ("SCORE_EXCESS_PRIMARY", .05)], .40),
    "capacity": ([("SCORE_PER_OCC_LIMIT", .20), ("SCORE_AGGREGATE_LIMIT", .10),
                  ("SCORE_RISK_COUNT", .10)], .25),
    "appetite": ([("SCORE_SPECIALTY_TIER", .25), ("SCORE_STATE_VENUE", .15),
                  ("SCORE_YEARS_SINCE_GRAD", .10), ("SCORE_RVU_RATIO", .10),
                  ("SCORE_TENURE", .05), ("SCORE_HOSPITAL_RATING", .05),
                  ("SCORE_PRACTICE_SIZE", .05), ("SCORE_PHYSICIAN_AGE", .07)], .25),
    "environment": ([("SCORE_INCOME_INEQUALITY", .05), ("SCORE_POP_DENSITY", .05),
                     ("SCORE_VIOLENT_CRIME", .03), ("SCORE_PCT_UNINSURED", .02)], .10),
}

# Credibility: Z = min(sqrt(premium / 10000), 1) per the design workbook,
# which differs from the deck's Z = min(premium / 50000, 1). Both are in play.
Z = np.minimum(np.sqrt(df["WRTN_PREM_AMT_ITD_BURNED"] / 10_000), 1.0)
df["CREDIBILITY_Z"] = Z.round(3)

comp_scores = {}
for comp, (members, _) in COMPONENTS.items():
    num = np.zeros(N)
    den = np.zeros(N)
    for col, w in members:
        s = pd.to_numeric(df[col], errors="coerce").to_numpy(float)
        if comp == "adequacy":
            s = np.where(np.isfinite(s), Z * s + (1 - Z) * 5.0, s)
        ok = np.isfinite(s)
        num += np.where(ok, w * np.nan_to_num(s), 0.0)
        den += np.where(ok, w, 0.0)
    comp_scores[comp] = np.where(den > 0, num / den, np.nan)
    df[f"PAS_{comp.upper()}_SCORE"] = np.round(comp_scores[comp], 3)

num = np.zeros(N); den = np.zeros(N)
for comp, (_, cw) in COMPONENTS.items():
    s = comp_scores[comp]
    ok = np.isfinite(s)
    num += np.where(ok, cw * np.nan_to_num(s), 0.0)
    den += np.where(ok, cw, 0.0)
df["PAS_COMPOSITE_SCORE"] = np.clip(np.round(np.where(den > 0, num / den, np.nan)), 1, 10)

# Write beside this script so the path works on Windows and POSIX alike.
out = Path(__file__).resolve().parent / "fixture_physician_scores.csv"
df.to_csv(out, index=False)
print(f"wrote {out}  {len(df):,} rows x {len(df.columns)} cols")
print(df["PAS_COMPOSITE_SCORE"].value_counts().sort_index().to_string())
