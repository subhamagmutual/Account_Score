"""
Column registry for the Physician MPL PAS diagnostics harness.

Defaults are transcribed from Physician_MPL_Account_Score_Design_v2.xlsx
(sheets 1_Updated_SubScores, 2_Binning_Details, 6_Data_Diagnostics).

Nothing here is authoritative -- it is a *hypothesis* about the data that the
audit is designed to falsify. Override via --column-map my_map.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Sentinel values. CV_LOSS_FREE_YEARS uses -99 for "unknown", and the documented
# binning maps "0 or negative" to score 10 (worst). That means missing data is
# scored as the worst possible risk. This registry lets the audit find it.
# ---------------------------------------------------------------------------

SENTINELS: dict[str, tuple[float, ...]] = {
    "CV_LOSS_FREE_YEARS": (-99.0, -999.0),
    "YEARS_SINCE_GRAD_IMPUTED": (-99.0, -999.0),
    "AGE_IMPUTED": (-99.0, -999.0),
    "RVU_WORK_TOTAL_RATIO_SPEC_OL": (-99.0, -999.0),
    "HOSP_HOSPITALCOMPARE_OVERALLRATING": (-99.0, 0.0),
}

GENERIC_SENTINELS: tuple[float, ...] = (-99.0, -999.0, -9999.0)

# Implausible ranges flagged in 6_Data_Diagnostics: AGE_IMPUTED spans 22-123,
# YEARS_SINCE_GRAD_IMPUTED spans -5 to 96.
PLAUSIBLE_RANGE: dict[str, tuple[float, float]] = {
    "AGE_IMPUTED": (24.0, 85.0),
    "YEARS_SINCE_GRAD_IMPUTED": (0.0, 60.0),
    "HOSP_HOSPITALCOMPARE_OVERALLRATING": (1.0, 5.0),
    "RISK_COUNT": (1.0, 5000.0),
    "TOP_PER_M": (0.0, 50.0),
    "TOP_AGG_M": (0.0, 100.0),
    "PCT_UNINSURED": (0.0, 60.0),
}


@dataclass
class Variable:
    """One scored variable: its raw driver column and its 1-10 score column."""

    name: str
    raw_col: str
    score_col: str
    component: str
    weight: float
    higher_is_worse: bool = True
    # True when the score bands were themselves derived from the target
    # (e.g. specialty and state tiers were cut on portfolio loss ratio).
    # These cannot be validated against that target -- see checks.circularity.
    target_derived: bool = False
    categorical: bool = False


@dataclass
class ColumnMap:
    """Everything the harness needs to locate in the scored output."""

    # Identity / partition keys
    policy_id: str = "POLICY_NUMBER_TRIMMED"
    risk_id: str = "RISK_CISID"
    npi: str = "NPI"
    coverage_year: str = "COVERAGE_YEAR"

    # Composite + component scores
    composite_score: str = "PAS_COMPOSITE_SCORE"
    component_scores: dict[str, str] = field(
        default_factory=lambda: {
            "adequacy": "PAS_ADEQUACY_SCORE",
            "capacity": "PAS_CAPACITY_SCORE",
            "appetite": "PAS_APPETITE_SCORE",
            "environment": "PAS_ENVIRONMENT_SCORE",
        }
    )
    credibility_z: str = "CREDIBILITY_Z"

    # --- Target definition -------------------------------------------------
    # These must be ACTUAL losses, never the burned/on-level columns. The
    # design workbook labels BCE_ST_..._BURNED / BCE_ST as "loss ratio", but
    # both sides of that ratio are exposure columns, so it is a burn factor.
    # Using it as a target would validate the model against itself.
    target_loss: str = "AMT_GROSS_RPTD_TOTAL_TRENDED"
    target_indemnity: str = "AMT_GROSS_RPTD_IND_TRENDED"
    target_claim_count: str = "CNT_GROSS_RPTD_TOTAL_GT_0"
    exposure_premium: str = "WRTN_PREM_AMT_ITD_BURNED_CLASS_OL"
    exposure_bce: str = "BCE_ST_GROSS_RPTD_TOTAL_TRENDED_BURNED"

    component_weights: dict[str, float] = field(
        default_factory=lambda: {
            "adequacy": 0.40,
            "capacity": 0.25,
            "appetite": 0.25,
            "environment": 0.10,
        }
    )

    variables: list[Variable] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.variables:
            self.variables = default_variables()

    @classmethod
    def load(cls, path: str | Path | None) -> "ColumnMap":
        if path is None:
            return cls()
        raw = json.loads(Path(path).read_text())
        variables = [Variable(**v) for v in raw.pop("variables", [])] or None
        cm = cls(**raw)
        if variables:
            cm.variables = variables
        return cm

    def dump(self, path: str | Path) -> None:
        payload = asdict(self)
        Path(path).write_text(json.dumps(payload, indent=2))

    def score_cols(self) -> list[str]:
        return [v.score_col for v in self.variables]

    def by_component(self, component: str) -> list[Variable]:
        return [v for v in self.variables if v.component == component]


def default_variables() -> list[Variable]:
    """The 23 variables per the May 2026 deck, with design-workbook raw columns.

    Note the deck and the design workbook disagree on Adequacy membership: the
    workbook's Step 3 composite formula uses Premium Volume and Excess/Primary,
    which the deck omits, and omits Indemnity/Expense Loss Cost and Severity,
    which the deck includes. Both sets are listed here so the audit can report
    which ones actually exist in the output.
    """
    V = Variable
    return [
        # ---- Adequacy (deck: 40% of composite) ----------------------------
        V("total_loss_cost", "ULT_Total_LOSS_COST_PER_BCE",
          "SCORE_TOTAL_LOSS_COST", "adequacy", 0.20),
        V("indemnity_loss_cost", "ULT_Indemnity_LOSS_COST_PER_BCE",
          "SCORE_INDEMNITY_LOSS_COST", "adequacy", 0.10),
        V("expense_loss_cost", "ULT_Expense_LOSS_COST_PER_BCE",
          "SCORE_EXPENSE_LOSS_COST", "adequacy", 0.05),
        V("total_frequency", "ULT_Total_FREQUENCY_PER_FTE",
          "SCORE_TOTAL_FREQUENCY", "adequacy", 0.10),
        V("indemnity_frequency", "ULT_Indemnity_FREQUENCY_PER_FTE",
          "SCORE_INDEMNITY_FREQUENCY", "adequacy", 0.05),
        V("total_severity", "ULT_Total_SEVERITY",
          "SCORE_TOTAL_SEVERITY", "adequacy", 0.05),
        V("actual_loss_ratio", "ULT_ACTUAL_LOSS_RATIO_BURNED",
          "SCORE_ACTUAL_LOSS_RATIO", "adequacy", 0.10),
        V("loss_free_years", "CV_LOSS_FREE_YEARS",
          "SCORE_LOSS_FREE_YEARS", "adequacy", 0.10, higher_is_worse=False),
        V("limits_to_premium", "LIMITS_TO_PREMIUM_RATIO",
          "SCORE_LIMITS_TO_PREMIUM", "adequacy", 0.10),
        # Workbook-only Adequacy members -- present in Step 3, absent from deck
        V("premium_volume", "WRTN_PREM_AMT_ITD_BURNED",
          "SCORE_PREMIUM_VOLUME", "adequacy", 0.10, higher_is_worse=False),
        V("excess_primary", "ATT_PER_M",
          "SCORE_EXCESS_PRIMARY", "adequacy", 0.05, categorical=True),

        # ---- Capacity (25%) ----------------------------------------------
        V("per_occ_limit", "TOP_PER_M",
          "SCORE_PER_OCC_LIMIT", "capacity", 0.20, categorical=True),
        V("aggregate_limit", "TOP_AGG_M",
          "SCORE_AGGREGATE_LIMIT", "capacity", 0.10, categorical=True),
        V("risk_count", "RISK_COUNT",
          "SCORE_RISK_COUNT", "capacity", 0.10),

        # ---- Appetite (25%) ----------------------------------------------
        # Specialty and state tiers were cut on portfolio LOSS RATIO, i.e. on
        # the target. target_derived=True excludes them from lift claims.
        V("specialty_tier", "OL_RISK_SPECIALTY_DESC",
          "SCORE_SPECIALTY_TIER", "appetite", 0.25,
          categorical=True, target_derived=True),
        V("state_venue", "ST",
          "SCORE_STATE_VENUE", "appetite", 0.15,
          categorical=True, target_derived=True),
        V("years_since_grad", "YEARS_SINCE_GRAD_IMPUTED",
          "SCORE_YEARS_SINCE_GRAD", "appetite", 0.10),
        V("rvu_ratio", "RVU_WORK_TOTAL_RATIO_SPEC_OL",
          "SCORE_RVU_RATIO", "appetite", 0.10),
        V("tenure", "CV_YEARS_WITH_MAG",
          "SCORE_TENURE", "appetite", 0.05, higher_is_worse=False),
        V("hospital_rating", "HOSP_HOSPITALCOMPARE_OVERALLRATING",
          "SCORE_HOSPITAL_RATING", "appetite", 0.05,
          higher_is_worse=False, categorical=True),
        V("practice_size", "WITH_WHOM_LOCATION_DISTINCT_NPI",
          "SCORE_PRACTICE_SIZE", "appetite", 0.05),
        # Workbook-only Appetite member, r~0.95 with years_since_grad
        V("physician_age", "AGE_IMPUTED",
          "SCORE_PHYSICIAN_AGE", "appetite", 0.07),

        # ---- Environment (10%) -------------------------------------------
        V("income_inequality", "INCOME_RATIO",
          "SCORE_INCOME_INEQUALITY", "environment", 0.05),
        V("pop_density", "POP_DENSITY_SQ_MILES",
          "SCORE_POP_DENSITY", "environment", 0.05),
        V("violent_crime", "VIOLENT_CRIME_RATE_PER_100K",
          "SCORE_VIOLENT_CRIME", "environment", 0.03),
        V("pct_uninsured", "PCT_UNINSURED",
          "SCORE_PCT_UNINSURED", "environment", 0.02),
    ]


# Distributions documented in 6_Data_Diagnostics. The audit compares the real
# data against these; a mismatch means either the doc or the pipeline is stale.
DOCUMENTED_SPEC: dict[str, dict[str, float]] = {
    "ULT_ACTUAL_LOSS_RATIO_BURNED": {"median": 0.98, "p5": 0.87, "p95": 1.11,
                                     "non_null_pct": 100.0, "zero_pct": 0.0},
    "ULT_Total_FREQUENCY_PER_FTE": {"median": 0.955, "p5": 0.24, "p95": 1.00,
                                    "non_null_pct": 100.0, "zero_pct": 0.0},
    "CV_LOSS_FREE_YEARS": {"median": 9.0, "p5": 2.0, "p95": 32.0,
                           "non_null_pct": 100.0, "zero_pct": 8.0},
    "LIMITS_TO_PREMIUM_RATIO": {"median": 128.0, "p5": 20.0, "p95": 2889.0,
                                "non_null_pct": 100.0},
    "WRTN_PREM_AMT_ITD_BURNED": {"median": 7181.0, "non_null_pct": 100.0},
    "TOP_PER_M": {"non_null_pct": 100.0},
    "RISK_COUNT": {"median": 14.0, "p5": 1.0, "p95": 265.0},
    "YEARS_SINCE_GRAD_IMPUTED": {"median": 23.0, "p5": 4.0, "p95": 44.0},
    "AGE_IMPUTED": {"median": 52.0, "p5": 34.0, "p95": 72.0},
    "RVU_WORK_TOTAL_RATIO_SPEC_OL": {"median": 0.55, "p95": 2.85,
                                     "non_null_pct": 76.0},
    "CV_YEARS_WITH_MAG": {"median": 7.0, "zero_pct": 8.0},
    "HOSP_HOSPITALCOMPARE_OVERALLRATING": {"median": 3.0, "non_null_pct": 41.0},
    "WITH_WHOM_LOCATION_DISTINCT_NPI": {"median": 5.0, "non_null_pct": 86.0},
    "INCOME_RATIO": {"median": 4.68, "p5": 3.76, "p95": 6.19},
    "POP_DENSITY_SQ_MILES": {"median": 613.0, "p5": 84.0, "p95": 2700.0},
    "VIOLENT_CRIME_RATE_PER_100K": {"median": 423.0, "p5": 123.0, "p95": 808.0},
    "PCT_UNINSURED": {"median": 14.0, "p5": 8.0, "p95": 20.0},
}

# 93% of records have zero raw claim count. Any Adequacy driver whose
# distribution is NOT dominated by zeros is not measuring the physician's own
# loss experience. This is the threshold the audit uses to flag that.
EXPECTED_ZERO_CLAIM_SHARE = 0.93
