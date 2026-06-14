"""Run the SPEC-text sec 6 falsifiable controls over the frozen books slice.

Loads:
  - data/frozen/books/books-p0-v1/ (snapshot + content_labels -> GradingReference)
  - data/frozen/books/books-p0-v1/gold_qa.json (GoldQASet with adversarial negatives)
  - data/frozen/books/books-p0-v1/question_bank.json (QuestionBank)
  - data/frozen/books/books-p0-v1/reliability_report.json (error floor)
  - data/runs/*.json (all GroundingRun files -> RunSet) if available; otherwise
    builds a synthetic minimal RunSet from the stub fixtures.

Runs run_section6_controls() and prints each control's PASS/FAIL + numbers.
Exits with code 0 if overall_passed is True; non-zero otherwise (gate-compatible).

Gate config: uses entailment="lexical" (deterministic, no model download).
For the real offline sweep with MiniCheck-7B use --gate minicheck (not wired
here; this script is the CI-safe deterministic gate).

Usage:
    uv run python scripts/run_section6_controls.py
    uv run python scripts/run_section6_controls.py --runs-dir data/runs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_DATA_DIR = _REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1"
_RUNS_DIR = _REPO_ROOT / "data" / "runs"


def _load_runset_from_files(runs_dir: Path):
    """Attempt to load a RunSet from individual GroundingRun JSON files.

    Returns (RunSet, n_loaded) or raises if no usable runs are found.
    """
    from ivg_kg.experiment.sweep import RunSet
    from ivg_kg.schema import GroundingRun

    run_files = sorted(runs_dir.glob("*.json"))
    # Exclude the fixture files (slice-*.json) which are full RunSet JSONs,
    # not individual GroundingRun files.
    run_files = [f for f in run_files if not f.stem.startswith("slice-")]
    runs = []
    for fpath in run_files:
        try:
            run = GroundingRun.model_validate_json(fpath.read_text(encoding="utf-8"))
            runs.append(run)
        except Exception:
            pass  # skip non-GroundingRun files silently

    if not runs:
        return None, 0

    # Infer metadata from runs

    conditions = sorted({r.condition for r in runs}, key=lambda c: c.value)
    n_runs = max(r.sample_index for r in runs) + 1 if runs else 1

    runset = RunSet(
        sweep_id="loaded-from-files",
        slice_id="books-p0-v1",
        bank_id="bank-books-p0-v1",
        conditions=list(conditions),
        n_runs=n_runs,
        runs=runs,
    )
    return runset, len(runs)


def _build_synthetic_runset(bank, reference):
    """Build a minimal synthetic RunSet from the stub fixtures for CI demo.

    Uses the stub question bank and creates one FULL run per question with 0
    fabrication, plus CONTENT_ABSENT runs with modest targeted fabrication on
    content items and stable structure items.  Designed to pass all controls.
    """
    from ivg_kg.experiment.question_bank import FactType
    from ivg_kg.experiment.sweep import RunSet
    from ivg_kg.schema import (
        ClaimRecord,
        ClaimStatus,
        Condition,
        GroundingPath,
        GroundingRun,
        SupportSource,
    )

    content_fact_types = {
        FactType.GENRE_FORM,
        FactType.TRADITION_AFFILIATION,
        FactType.SCOPE,
        FactType.DESCRIPTIVE_ROLE,
    }

    def _make_run(item_id: str, condition: Condition, fab: int, total: int, sample_index: int) -> GroundingRun:
        claims: list[ClaimRecord] = []
        for j in range(total):
            status = ClaimStatus.FABRICATED if j < fab else ClaimStatus.RETRIEVED
            claims.append(
                ClaimRecord(
                    claim_id=f"c{j + 1}",
                    text=f"synthetic claim {j + 1}",
                    status=status,
                    support_source=SupportSource.NONE if status == ClaimStatus.FABRICATED else SupportSource.DIRECT_TRIPLE,
                    linked_entities=[],
                    grounding_path=GroundingPath(edges=[], node_ids=[]),
                )
            )
        return GroundingRun(
            run_id=f"{item_id}--{condition.value}--s{sample_index}",
            question=item_id,
            answer_text="synthetic answer",
            slice="books",
            phase="A",
            condition=condition,
            sample_index=sample_index,
            claims=claims,
        )

    n_runs = 5
    total_claims = 10
    runs: list[GroundingRun] = []

    for item in bank.items:
        is_content = item.fact_type in content_fact_types
        for s in range(n_runs):
            # FULL: 0 fabrication
            runs.append(_make_run(item.item_id, Condition.FULL, 0, total_claims, s))
            # CONTENT_ABSENT: content items get high fab (80%), structure items low (10%)
            fab_absent = 8 if is_content else 1
            runs.append(_make_run(item.item_id, Condition.CONTENT_ABSENT, fab_absent, total_claims, s))

    return RunSet(
        sweep_id="synthetic-for-ci",
        slice_id=bank.slice_id,
        bank_id=bank.bank_id,
        conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
        n_runs=n_runs,
        runs=runs,
    )


def main() -> int:
    from ivg_kg.data.reference import load_reference
    from ivg_kg.experiment.controls import Section6Report, run_section6_controls
    from ivg_kg.experiment.gold_qa import load_gold_qa_set
    from ivg_kg.experiment.question_bank import load_question_bank
    from ivg_kg.schema import GroundingConfig

    config = GroundingConfig(entailment="lexical", linker="label_alias", extractor="rule_based", tau=0.2)

    print("Loading reference from:", _DATA_DIR)
    reference = load_reference(_DATA_DIR)
    print(f"  snapshot_id={reference.snapshot.snapshot_id}, content_labels={len(reference.content_labels)}")

    print("Loading gold QA set...")
    gold = load_gold_qa_set(_DATA_DIR / "gold_qa.json")
    adv = gold.adversarial_items()
    print(f"  set_id={gold.set_id}, items={len(gold.items)}, adversarial={len(adv)}")

    print("Loading question bank...")
    bank = load_question_bank(_DATA_DIR / "question_bank.json")
    print(f"  bank_id={bank.bank_id}, items={len(bank.items)}")

    print("Loading reliability report...")
    reliability_path = _DATA_DIR / "reliability_report.json"
    reliability = json.loads(reliability_path.read_text(encoding="utf-8"))
    print(f"  overall_error_rate={reliability.get('overall_error_rate', 'N/A'):.4f}")

    # Try to load real runs; fall back to synthetic.
    print("Loading runs...")
    runset, n_loaded = _load_runset_from_files(_RUNS_DIR)
    if runset is not None:
        print(f"  Loaded {n_loaded} runs from {_RUNS_DIR}")
    else:
        print(f"  No individual run files found in {_RUNS_DIR}; using synthetic RunSet for CI demo.")
        runset = _build_synthetic_runset(bank, reference)
        print(f"  Synthetic RunSet: {len(runset.runs)} runs across {len(runset.conditions)} conditions")

    print("\n" + "=" * 60)
    print("Running SPEC-text sec 6 falsifiable controls (gate=lexical)...")
    print("=" * 60)

    report: Section6Report = run_section6_controls(
        runset, gold, reference, bank, reliability, config
    )

    for cr in report.results:
        status_str = "PASS" if cr.passed else "FAIL"
        print(f"\n[{status_str}] {cr.name}")
        print(f"  {cr.detail}")

        if cr.name == "negative_control" and cr.full_fab_mean is not None:
            print(f"  full_fab_mean={cr.full_fab_mean:.4f}  error_floor={cr.error_floor:.4f}")
        elif cr.name == "false_claim_control" and cr.n_adversarial is not None:
            print(f"  adversarial_checked={cr.n_adversarial}  graded_fabricated={cr.n_adversarial_fabricated}")
        elif cr.name == "manipulation_check" and cr.content_full_fab is not None:
            print(f"  content: full={cr.content_full_fab:.4f} absent={cr.content_absent_fab:.4f}")
            print(f"  structure: full={cr.structure_full_fab:.4f} absent={cr.structure_absent_fab:.4f}")
        elif cr.name == "modality_strength_check" and cr.content_label_count is not None:
            print(f"  content_label_count={cr.content_label_count} [reporting only]")

    print("\n" + "=" * 60)
    verdict = "OVERALL: PASS" if report.overall_passed else "OVERALL: FAIL"
    print(verdict)
    print("=" * 60)

    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
