"""Emit the RQ2 modality-contrast report figure (EX4).

Loads a RunSet (from data/runs/ or a passed JSON path) + the reliability report,
computes the RQ2 aggregate, and writes the figure to data/figures/.

Output files (HTML always; PNG/PDF if kaleido is installed):
    data/figures/rq2_modality_contrast.html
    data/figures/rq2_modality_contrast.png   (best-effort)
    data/figures/rq2_modality_contrast.pdf   (best-effort)

Prints a summary of the aggregate and which shifts cleared the noise floor.

Usage:
    # Uses the synthetic sweep (runs from data/runs/) + frozen reliability report:
    uv run python scripts/emit_rq2_figure.py

    # Pass a custom RunSet JSON:
    uv run python scripts/emit_rq2_figure.py --runset path/to/runset.json

    # Pass a custom reliability report:
    uv run python scripts/emit_rq2_figure.py --reliability path/to/reliability_report.json

Notes:
    - If data/runs/ has no real sweep files the script falls back to building a
      SYNTHETIC RunSet via the mock fixtures so it can always be run offline.
    - data/figures/ is an output directory (gitignored); produced figure binaries
      are NOT committed.
    - This script calls no live model.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ivg_kg.experiment.rq2_aggregate import (
    compute_rq2_aggregate,
    load_reliability_report,
    make_rq2_figure,
    save_rq2_figure,
)
from ivg_kg.experiment.sweep import RunSet
from ivg_kg.schema import Condition

_REPO_ROOT = Path(__file__).parent.parent
_RUNS_DIR = _REPO_ROOT / "data" / "runs"
_RELIABILITY_PATH = (
    _REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1" / "reliability_report.json"
)
_FIGURES_DIR = _REPO_ROOT / "data" / "figures"
_FIGURE_STEM = "rq2_modality_contrast"


# ---------------------------------------------------------------------------
# RunSet loading / fallback
# ---------------------------------------------------------------------------


def _load_runset_from_dir(runs_dir: Path) -> RunSet | None:
    """Try to load a RunSet from individual run JSON files in runs_dir.

    Returns None if no qualifying run files are found (so the caller can fall back
    to the synthetic fixture).  The runs_dir convention stores one GroundingRun per
    file; we reconstruct a minimal RunSet wrapper from them.
    """
    from ivg_kg.schema import GroundingRun

    run_files = [
        f for f in runs_dir.glob("*.json")
        if "--" in f.stem and not f.stem.startswith("slice-")
    ]
    if not run_files:
        return None

    runs: list[GroundingRun] = []
    for f in sorted(run_files):
        try:
            runs.append(GroundingRun.model_validate_json(f.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: skipping malformed run file {f.name}: {exc}", file=sys.stderr)

    if not runs:
        return None

    # Determine conditions present.
    conditions = sorted({r.condition for r in runs}, key=lambda c: c.value)
    # Best-effort n_runs: max sample_index + 1 across any condition.
    n_runs = max((r.sample_index for r in runs), default=0) + 1

    return RunSet(
        sweep_id="emit-script-loaded",
        slice_id="books",
        bank_id="loaded",
        conditions=conditions,
        n_runs=n_runs,
        runs=runs,
    )


def _make_synthetic_runset() -> RunSet:
    """Synthetic RunSet via mock fixtures (offline; no model needed).

    Used when data/runs/ contains no sweep files.  The RunSet covers
    {FULL, CONTENT_ABSENT, KNOWLEDGE_ABSENT} with N=20 draws of the
    Chopin scenario at controlled fabrication fractions, so the figure
    shows a meaningful pattern without real sweep data.
    """
    from ivg_kg.mock.fixtures import build_condition_runset
    from ivg_kg.schema import GroundingRun

    runs: list[GroundingRun] = []
    conditions = [Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT]
    n = 20
    for cond in conditions:
        runs.extend(build_condition_runset(n, cond))

    return RunSet(
        sweep_id="synthetic-mock",
        slice_id="books",
        bank_id="mock",
        conditions=conditions,
        n_runs=n,
        runs=runs,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Emit the RQ2 modality-contrast figure.")
    parser.add_argument(
        "--runset",
        type=Path,
        default=None,
        help="Path to a RunSet JSON file (overrides auto-detect from data/runs/).",
    )
    parser.add_argument(
        "--reliability",
        type=Path,
        default=_RELIABILITY_PATH,
        help=f"Path to the reliability_report.json (default: {_RELIABILITY_PATH}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_FIGURES_DIR / _FIGURE_STEM,
        help="Output path stem (default: data/figures/rq2_modality_contrast).",
    )
    args = parser.parse_args(argv)

    # --- Load RunSet ---
    if args.runset is not None:
        print(f"Loading RunSet from {args.runset} ...")
        runset = RunSet.model_validate_json(args.runset.read_text(encoding="utf-8"))
        print(f"  Loaded {len(runset.runs)} runs.")
    else:
        print(f"Auto-detecting RunSet from {_RUNS_DIR} ...")
        runset = _load_runset_from_dir(_RUNS_DIR)
        if runset is None:
            print("  No sweep files found -- falling back to SYNTHETIC mock RunSet.")
            runset = _make_synthetic_runset()
            print(f"  Built synthetic RunSet: {len(runset.runs)} runs.")
        else:
            print(f"  Loaded {len(runset.runs)} runs.")

    # --- Load reliability report ---
    rel_path = args.reliability
    print(f"Loading reliability report from {rel_path} ...")
    reliability = load_reliability_report(rel_path)
    print(
        f"  gate={reliability.get('gate')} "
        f"calibrated={reliability.get('calibrated')} "
        f"overall_error_rate={reliability.get('overall_error_rate', '?'):.3f}"
    )

    # --- Compute aggregate ---
    print("Computing RQ2 aggregate ...")
    agg = compute_rq2_aggregate(runset, reliability)

    # --- Print summary ---
    _print_summary(agg)

    # --- Emit figure ---
    print(f"\nWriting figure to {args.out}.html (+ PNG/PDF if kaleido) ...")
    fig = make_rq2_figure(agg)
    save_rq2_figure(fig, args.out)
    html_path = Path(str(args.out)).with_suffix(".html")
    print(f"  Written: {html_path}")
    png_path = Path(str(args.out)).with_suffix(".png")
    if png_path.exists():
        print(f"  Written: {png_path}")
    pdf_path = Path(str(args.out)).with_suffix(".pdf")
    if pdf_path.exists():
        print(f"  Written: {pdf_path}")


def _print_summary(agg) -> None:
    from ivg_kg.schema import ClaimStatus

    print("\n--- RQ2 Aggregate Summary ---")
    print(f"Epistemic level    : {agg.epistemic_level}")
    print(f"Text noise floor   : {agg.text_noise_floor * 100:.2f}%")
    print(f"Structure noise floor: {agg.structure_noise_floor * 100:.2f}%")
    print(f"FULL baseline fab mean: {agg.full_baseline_fab_mean * 100:.2f}%  "
          f"(SE {agg.full_baseline_fab_se * 100:.2f}%)")
    print()

    fab_key = ClaimStatus.FABRICATED.value
    for cond_val, diag in agg.condition_diagnostics.items():
        ms = diag.status_distribution.get(fab_key)
        m = ms.mean if ms else 0.0
        e = ms.se if ms else 0.0
        print(f"  [{cond_val}] fab: {m * 100:.2f}% +/- {e * 100:.2f}%  (N={diag.n_runs})")

    print()
    if agg.content_absent_shift is not None:
        s = agg.content_absent_shift
        verdict = "CLEARS floor" if s.clears_floor else "within noise (does NOT clear floor)"
        print(f"Content-absent shift  : {s.shift * 100:+.2f}pp  "
              f"noise_floor={s.noise_floor * 100:.2f}%  => {verdict}")
    else:
        print("Content-absent shift  : N/A (no CONTENT_ABSENT runs)")

    if agg.knowledge_absent_shift is not None:
        s = agg.knowledge_absent_shift
        verdict = "CLEARS floor" if s.clears_floor else "within noise (does NOT clear floor)"
        print(f"Knowledge-absent shift: {s.shift * 100:+.2f}pp  "
              f"noise_floor={s.noise_floor * 100:.2f}%  => {verdict}")
    else:
        print("Knowledge-absent shift: N/A (no KNOWLEDGE_ABSENT runs)")
    print()


if __name__ == "__main__":
    main()
