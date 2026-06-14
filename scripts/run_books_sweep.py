"""Run the real M-BOOKS offline precompute sweep (A3-PREP).

This is the ONE-COMMAND real-run path for the M-BOOKS experiment.
It loads the frozen books-p0-v1 slice, the real question_bank.json and
manifest.json, assembles the FULL GradingReference (including all
content_labels.json labels), and runs run_sweep() over the three conditions
{full, content-absent, knowledge-absent} with the specified generator and
entailment gate.

Generator: Qwen2.5 via Ollama (default) or a CannedStubClient (--stub).
Verifier:  MiniCheck-7B offline (default; --gate minicheck) or the lexical
           gate (--gate lexical, for smoke tests / CI).

The tau used for grading is read from the committed reliability_report.json
(frozen_tau field) by default; override with --tau.

The sweep output files use '<item_id>--<condition>--sN.json' naming (NOT
'slice-*'), so they are correctly gitignored.  Do NOT commit them.

Reported numbers come from the offline MiniCheck-7B path (Invariant #22).
The lexical gate is for CI/fixture smoke tests ONLY and must NEVER source a
reported number.

Usage (smoke / CI):
    uv run python scripts/run_books_sweep.py --stub --gate lexical --n-runs 1

Usage (real run on Apple-Silicon with Ollama + MiniCheck):
    uv run python scripts/run_books_sweep.py --n-runs 20
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to repo root (robust regardless of cwd).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SLICE_DIR = _REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1"
_RUNS_DIR = _REPO_ROOT / "data" / "runs"


# ---------------------------------------------------------------------------
# CannedStubClient (offline stub; no model required)
# ---------------------------------------------------------------------------


def _make_stub_client():
    """Return a CannedStubClient instance (offline, no model download)."""
    from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
    from ivg_kg.schema import GenerationContext

    class CannedStubClient(BaseAIClient):
        """Offline canned generator: fixed grounded answer with seed-varying tail.

        The grounded sentence is stable so claims are deterministic; the
        bracketed suffix varies by seed so the sweep is honest about seeding
        without requiring any real model.
        """

        def _generate(
            self,
            question: str,
            context: GenerationContext,
            *,
            temperature: float = 0.7,
            seed: int | None = None,
        ) -> GenerationResult:
            answer = (
                "The Glass Menagerie author Tennessee Williams. "
                "The Glass Menagerie genre drama. "
                f"[draw seed={seed}]"
            )
            return GenerationResult(answer=answer)

    return CannedStubClient()


# ---------------------------------------------------------------------------
# Core importable function
# ---------------------------------------------------------------------------


def build_books_sweep(
    *,
    n_runs: int = 20,
    stub: bool = False,
    gate: str = "minicheck",
    tau: float | None = None,
    out_dir: Path | None = None,
):
    """Run the M-BOOKS offline precompute sweep and return the RunSet.

    Parameters
    ----------
    n_runs:
        Number of seeded draws per (question, condition). Default 20.
    stub:
        If True, use the CannedStubClient instead of the real Qwen generator.
        Use for smoke tests and CI (no Ollama required).
    gate:
        Entailment gate selector: "minicheck" (default; all reported numbers)
        or "lexical" (CI/smoke only; must never source reported numbers).
    tau:
        Grounding threshold. If None, read from reliability_report.json
        (frozen_tau). Override with an explicit float.
    out_dir:
        Directory to write run files. Defaults to data/runs/.

    Returns
    -------
    RunSet
        The completed sweep (also written to out_dir).
    """
    from ivg_kg.data.reference import load_reference
    from ivg_kg.experiment.ablation import manifest_perturbations_for
    from ivg_kg.experiment.question_bank import load_question_bank
    from ivg_kg.experiment.sweep import run_sweep, write_runset
    from ivg_kg.perturbation.base import AblationManifest
    from ivg_kg.schema import Condition, GroundingConfig

    # --- Load frozen slice ---------------------------------------------------
    reference = load_reference(_SLICE_DIR)
    bank = load_question_bank(_SLICE_DIR / "question_bank.json")
    manifest = AblationManifest.from_json(
        (_SLICE_DIR / "manifest.json").read_text(encoding="utf-8")
    )

    # --- Resolve tau ---------------------------------------------------------
    if tau is None:
        report_path = _SLICE_DIR / "reliability_report.json"
        if not report_path.exists():
            raise FileNotFoundError(
                f"reliability_report.json not found at {report_path}. "
                "Run: uv run python scripts/emit_calibration_report.py "
                "(lexical for demo; --gate minicheck for deployment)"
            )
        frozen_tau = json.loads(report_path.read_text(encoding="utf-8"))["frozen_tau"]
    else:
        frozen_tau = tau

    # --- Build config --------------------------------------------------------
    config = GroundingConfig(
        k_hops=2,
        tau=frozen_tau,
        entailment=gate,
        linker="label_alias",
        extractor="rule_based",
    )

    # --- Build generator client ----------------------------------------------
    if stub:
        client = _make_stub_client()
    else:
        # Real path: Qwen2.5 via Ollama. Will raise loudly if Ollama is not
        # running or the model is not pulled (OllamaClient raises on first call).
        from ivg_kg.grounding.clients.factory import get_default_client  # noqa: PLC0415
        client = get_default_client()

    # --- Build manifest-driven perturbations adapter -------------------------
    adapter = manifest_perturbations_for(manifest)

    # --- Progress callback ---------------------------------------------------
    _sweep_start = time.monotonic()

    def _on_run_complete(run, completed: int, total: int) -> None:
        elapsed = time.monotonic() - _sweep_start
        eta_s = (elapsed / completed) * (total - completed) if completed else 0.0
        # Compact status summary: count each ClaimStatus value in the run.
        status_counts: dict[str, int] = {}
        for claim in run.claims:
            k = claim.status.value
            status_counts[k] = status_counts.get(k, 0) + 1
        counts_str = " ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        parts = run.run_id.split("--")
        item_id = parts[0] if parts else run.run_id
        condition = parts[1] if len(parts) > 1 else ""
        sample = parts[2] if len(parts) > 2 else ""
        print(
            f"[{completed}/{total}] {item_id} {condition} {sample}"
            f" -> {counts_str}"
            f"  elapsed={elapsed:.1f}s  eta={eta_s:.1f}s",
            flush=True,
        )

    # --- Run the sweep -------------------------------------------------------
    runset = run_sweep(
        bank,
        reference,
        client,
        conditions=[
            Condition.FULL,
            Condition.CONTENT_ABSENT,
            Condition.KNOWLEDGE_ABSENT,
        ],
        n_runs=n_runs,
        config=config,
        perturbations_for=adapter,
        emit_no_repair_baseline=True,
        on_run_complete=_on_run_complete,
    )

    # --- Write runs ----------------------------------------------------------
    target = out_dir if out_dir is not None else _RUNS_DIR
    write_runset(runset, out_dir=target)

    return runset


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "M-BOOKS offline precompute sweep (A3-PREP). "
            "Default: Qwen2.5 generator + MiniCheck-7B verifier, n_runs=20."
        )
    )
    p.add_argument(
        "--n-runs",
        type=int,
        default=20,
        metavar="N",
        help="Seeded draws per (question, condition). Default 20.",
    )
    p.add_argument(
        "--stub",
        action="store_true",
        help="Use CannedStubClient instead of the real Qwen generator (offline/CI).",
    )
    p.add_argument(
        "--gate",
        choices=["lexical", "minicheck"],
        default="minicheck",
        help=(
            "Entailment gate. 'minicheck' = offline MiniCheck-7B (all reported numbers). "
            "'lexical' = model-free Jaccard gate (CI/smoke only; never sources reported numbers)."
        ),
    )
    p.add_argument(
        "--tau",
        type=float,
        default=None,
        metavar="TAU",
        help=(
            "Grounding threshold tau. If omitted, read frozen_tau from "
            "reliability_report.json (the calibrated operating point)."
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"Output directory. Default: {_RUNS_DIR}",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    runset = build_books_sweep(
        n_runs=args.n_runs,
        stub=args.stub,
        gate=args.gate,
        tau=args.tau,
        out_dir=args.out_dir,
    )

    from ivg_kg.schema import Condition

    n_items = len({r.run_id.split("--")[0] for r in runset.runs})
    n_conditions = len(runset.conditions)
    n_baseline = sum(
        1 for r in runset.runs if r.condition == Condition.FULL_NO_EDIT_RERUN
    )
    n_regular = len(runset.runs) - n_baseline
    target = args.out_dir if args.out_dir is not None else _RUNS_DIR

    print(
        f"Swept {n_items} questions x {n_conditions} conditions "
        f"x n_runs={runset.n_runs} = {n_regular} runs "
        f"+ {n_baseline} no-repair baselines "
        f"-> {len(runset.runs)} total"
    )
    print(f"Gate: {args.gate}  tau (frozen): {args.tau}")
    print(f"Wrote {len(runset.runs)} run files to {target}")
    print(
        "(gitignored '<item_id>--<condition>--sN.json'; do NOT commit sweep output)"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
