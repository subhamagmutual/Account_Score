"""
Every tunable in one place.

Previously thresholds were scattered as default arguments across checks.py --
fine for a CLI, useless in a notebook where the whole point is turning knobs and
re-running. `DiagnosticConfig` collects them so the notebook, the CLI, and any
scheduled job are all driving the same parameters, and so a run's settings can be
serialised into its output alongside the data hash.

Defaults reproduce the behaviour documented in README.md. Change them from the
notebook's PARAMS cell rather than editing this file, so your runs stay
reproducible from the config JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class DiagnosticConfig:
    """Thresholds and switches for a diagnostic run."""

    # --- Data ------------------------------------------------------------
    input_path: str | None = None
    column_map_path: str | None = None
    output_dir: str = "pas_diagnostics_out"
    nrows: int | None = None
    """Read only the first N rows. Use while iterating -- a 48 MB CSV takes a
    while to parse and none of the checks need the whole book to be informative."""

    # --- Target ----------------------------------------------------------
    target_basis: str = "loss_ratio"
    """'loss_ratio' divides by on-levelled premium -- what the current design
    tiered specialty and state on, which is exactly why those tiers are circular
    against it. 'loss_cost' divides by BCE exposure and is rate-independent; use
    it to re-tier, and to sanity-check any lift claim."""

    drop_nonpositive_exposure: bool = True

    # --- Out-of-time split -----------------------------------------------
    train_years: tuple[int, ...] | None = None
    test_years: tuple[int, ...] | None = None
    min_split_records: int = 500

    # --- Scoring conventions ---------------------------------------------
    anchor: float = 4.5
    """The band the portfolio mean is designed to land in. Also the origin for
    reason-code attribution. Note the Adequacy credibility complement is 5, not
    4.5 -- that mismatch is why reconciliation() shows a residual."""

    credibility_complement: float = 5.0
    score_min: float = 1.0
    score_max: float = 10.0

    # --- Check thresholds ------------------------------------------------
    min_exposure_share: float = 0.005
    """Bands holding less than this share of exposure are excluded from
    monotonicity. A band with twelve policies violates monotonicity by noise."""

    n_permutations: int = 2000
    """Permutation draws for the monotonicity significance test. With 5-10 bands,
    |rho| of 0.9 arises by chance far more often than intuition suggests. Raise
    for stabler p-values; 2000 gives resolution to ~0.0005."""

    permutation_seed: int = 20260727
    p_value_threshold: float = 0.05
    """Above this, the honest finding is 'no evidence of ordering' -- in either
    direction. Note ~26 variables are tested, so expect roughly one false
    positive at 0.05. Treat a lone significant result as a lead."""

    inversion_threshold: float = -0.30
    weak_signal_threshold: float = 0.30

    tie_threshold: float = 0.50
    """Flag a variable when this share of records receive an identical score.
    77% of policies sit at exactly $1M per-occurrence."""

    min_effective_bands: float = 3.0
    min_level_records: int = 30
    circularity_corr_threshold: float = 0.90

    vif_severe: float = 10.0
    vif_moderate: float = 5.0
    pairwise_corr_threshold: float = 0.85

    psi_bins: int = 10
    psi_unstable: float = 0.25

    present_pct_threshold: float = 0.80
    """Flag a variable available on less than this share of records. Hospital
    Rating is missing on 59%, so its nominal weight is fiction for most of the
    book."""

    burn_factor_max_zero_share: float = 0.20
    burn_factor_min_non_null: float = 0.98
    burn_factor_max_spread: float = 0.60
    """An Adequacy driver that is rarely zero, almost never missing, and tightly
    spread is not the physician's loss experience -- 93% of physicians are
    claim-free, so their loss experience is zero. These three thresholds define
    'looks like a burn or on-level factor instead'."""

    expected_zero_claim_share: float = 0.93
    spec_drift_tolerance: float = 0.25

    # --- Reason codes / tooling ------------------------------------------
    reason_top_n: int = 3
    min_contribution_points: float = 0.01
    card_limit: int = 25
    card_top_drivers: int = 4
    triage_top_n: int = 250
    triage_min_premium: float = 0.0

    # --- Output ----------------------------------------------------------
    write_csvs: bool = True
    write_excel: bool = False
    write_markdown: bool = True
    verbose: bool = True

    notes: dict = field(default_factory=dict)
    """Free-form provenance -- analyst name, ticket number, what you were testing.
    Written into run_metadata.json."""

    def __post_init__(self) -> None:
        if self.target_basis not in {"loss_ratio", "loss_cost"}:
            raise ValueError(
                f"target_basis must be 'loss_ratio' or 'loss_cost', "
                f"got {self.target_basis!r}")
        for name in ("train_years", "test_years"):
            v = getattr(self, name)
            if v is not None:
                setattr(self, name, tuple(int(x) for x in v))

    @property
    def has_split(self) -> bool:
        return bool(self.train_years and self.test_years)

    @classmethod
    def load(cls, path: str | Path) -> "DiagnosticConfig":
        return cls(**json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("train_years", "test_years"):
            if d[k] is not None:
                d[k] = list(d[k])
        return d

    def replace(self, **kw) -> "DiagnosticConfig":
        """Return a copy with overrides -- for sweeping one threshold."""
        return DiagnosticConfig(**{**self.to_dict(), **kw})
