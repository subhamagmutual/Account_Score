"""
Command line entry point. Thin wrapper over pipeline.run_pipeline() so the CLI
and the notebook cannot drift apart.

    # Step 1 -- always first. Reports what it found, computes nothing.
    python -m pas_diagnostics --input physician_scores.csv --inspect

    # Step 2 -- full run with an out-of-time split
    python -m pas_diagnostics --input physician_scores.csv --outdir reports/2026-07 \
        --train-years 2017 2018 2019 2020 2021 --test-years 2022 2023 2024 --excel
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline
from .config import DiagnosticConfig
from .schema import ColumnMap


def inspect(cfg: DiagnosticConfig, cm: ColumnMap) -> int:
    """Print the resolved schema without computing anything.

    If the column map is wrong, every downstream metric is confidently wrong.
    """
    df = pipeline.load_data(cfg.replace(nrows=cfg.nrows or 2000))
    res = pipeline.resolve_schema(df, cm)

    print(f"\nColumns in file: {len(df.columns)}\n")
    for kind in ("required", "component", "variable"):
        sub = res[res["kind"] == kind]
        if sub.empty:
            continue
        print(f"--- {kind} ---")
        for _, r in sub.iterrows():
            mark = "OK  " if r["found"] else "MISS"
            w = f"w={r['weight']:.2f}" if r["weight"] == r["weight"] else "     "
            print(f"  {mark}  {r['variable']:<22} {r['role']:<6} {w}  {r['column']}")
        print()

    miss = res[~res["found"]]
    print(f"{(~res['found']).sum()} of {len(res)} expected columns not found.")
    if not miss.empty:
        sug = pipeline.suggest_column_map(df, cm)
        if not sug.empty:
            print("\n--- fuzzy suggestions (verify before accepting) ---")
            cols = ["variable", "role", "expected", "suggestion_1", "suggestion_2"]
            print(sug[cols].to_string(index=False, max_colwidth=38))
        print("\nWrite a map, edit it, pass it back:")
        print("  python -m pas_diagnostics --input F --dump-column-map map.json")
        print("  python -m pas_diagnostics --input F --column-map map.json --inspect")
    return 0 if miss.empty else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pas_diagnostics",
                                description="Validate the Physician MPL PAS.")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--outdir", type=Path, default=Path("pas_diagnostics_out"))
    p.add_argument("--column-map", type=Path, default=None)
    p.add_argument("--config", type=Path, default=None,
                   help="DiagnosticConfig JSON; CLI flags override it")
    p.add_argument("--dump-column-map", type=Path, default=None)
    p.add_argument("--dump-config", type=Path, default=None)
    p.add_argument("--inspect", action="store_true")
    p.add_argument("--nrows", type=int, default=None)
    p.add_argument("--train-years", type=int, nargs="+", default=None)
    p.add_argument("--test-years", type=int, nargs="+", default=None)
    p.add_argument("--target", choices=["loss_ratio", "loss_cost"],
                   default="loss_ratio")
    p.add_argument("--min-exposure-share", type=float, default=None)
    p.add_argument("--permutations", type=int, default=None)
    p.add_argument("--excel", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)

    cfg = DiagnosticConfig.load(a.config) if a.config else DiagnosticConfig()
    cfg = cfg.replace(
        input_path=str(a.input),
        output_dir=str(a.outdir),
        column_map_path=str(a.column_map) if a.column_map else None,
        nrows=a.nrows if a.nrows is not None else cfg.nrows,
        train_years=a.train_years or cfg.train_years,
        test_years=a.test_years or cfg.test_years,
        target_basis=a.target,
        min_exposure_share=(a.min_exposure_share if a.min_exposure_share is not None
                            else cfg.min_exposure_share),
        n_permutations=(a.permutations if a.permutations is not None
                        else cfg.n_permutations),
        write_excel=a.excel or cfg.write_excel,
        verbose=not a.quiet,
    )

    if a.dump_config:
        cfg.dump(a.dump_config)
        print(f"wrote {a.dump_config}")
        return 0

    cm = ColumnMap.load(cfg.column_map_path)
    if a.dump_column_map:
        cm.dump(a.dump_column_map)
        print(f"wrote {a.dump_column_map}")
        return 0

    if not a.input.exists():
        print(f"Input not found: {a.input}", file=sys.stderr)
        return 1
    if a.inspect:
        return inspect(cfg, cm)

    try:
        res = pipeline.run_pipeline(cfg, cm)
    except KeyError as e:
        print(f"\nERROR: {e}\nRun with --inspect first.", file=sys.stderr)
        return 1

    written = res.write()
    counts = res.counts()
    print("\n" + "-" * 62)
    print(counts.to_string() if not counts.empty else "no findings")
    print("-" * 62)
    for k, v in written.items():
        print(f"{k:<9}: {v}")

    blockers = res.blockers()
    if not blockers.empty:
        print("\nTop blocking findings:")
        for _, r in blockers.iterrows():
            print(f"  - {r['check']}/{r['subject']}: {r['message'][:150]}")

    return 3 if not blockers.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
