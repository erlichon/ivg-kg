"""Tests for scripts/run_books_sweep.py (A3-PREP).

All tests run OFFLINE: stub generator + lexical gate (no ollama, no torch).
The real run (Qwen via ollama + MiniCheck-7B verifier) happens on the user's
Apple-Silicon machine following RUNBOOK.md.

Coverage:
  - build_books_sweep() with --stub --gate lexical --n-runs 1 completes and
    produces a RunSet covering every (item, condition) + no-repair baselines.
  - Two calls are byte-identical (determinism).
  - The reference contains all 5 committed content_labels.json labels.
  - A content-arm item under CONTENT_ABSENT has active_perturbations set.
  - emit_calibration_report default (lexical) still produces calibrated=False
    / gate="lexical".
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate the frozen slice once for the whole test module.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SLICE_DIR = _REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1"

# Guard: if the frozen slice is not present, skip gracefully (should not happen
# in CI since the slice is committed).
pytestmark = pytest.mark.skipif(
    not (_SLICE_DIR / "question_bank.json").exists(),
    reason="frozen books slice not found; cannot run sweep tests",
)


# ---------------------------------------------------------------------------
# Import the importable entry point from the script.
# ---------------------------------------------------------------------------

def _import_build_books_sweep():
    """Import build_books_sweep from scripts/run_books_sweep.py at runtime.

    We insert the scripts/ directory into sys.path temporarily so the module
    imports cleanly without being in a package.
    """
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import importlib
    mod = importlib.import_module("run_books_sweep")
    return mod


# ---------------------------------------------------------------------------
# Test: smoke sweep completes with stub + lexical
# ---------------------------------------------------------------------------


def test_smoke_sweep_produces_runset():
    """build_books_sweep with --stub --gate lexical --n-runs 1 completes."""
    mod = _import_build_books_sweep()
    with tempfile.TemporaryDirectory() as tmp:
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=Path(tmp),
        )
    assert runset is not None
    assert runset.n_runs == 1
    assert len(runset.runs) > 0


def test_smoke_sweep_covers_all_items_and_conditions():
    """Every (item, condition) pair is present in the runset, plus no-repair baselines."""
    mod = _import_build_books_sweep()
    with tempfile.TemporaryDirectory() as tmp:
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=Path(tmp),
        )

    from ivg_kg.schema import Condition

    conditions = [Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT]
    # Load bank to know how many items there are
    from ivg_kg.experiment.question_bank import load_question_bank
    bank = load_question_bank(_SLICE_DIR / "question_bank.json")
    n_items = len(bank.items)

    # For each item x condition we expect 1 run (n_runs=1), plus 1 no-repair
    # baseline per FULL run (FULL_NO_EDIT_RERUN).
    expected_run_count = n_items * len(conditions) + n_items  # FULL_NO_EDIT_RERUN baselines
    assert len(runset.runs) == expected_run_count, (
        f"Expected {expected_run_count} runs, got {len(runset.runs)}"
    )

    # Every (item, condition) pair is present.
    for item in bank.items:
        for cond in conditions:
            run = runset.get(item.item_id, cond, 0)
            assert run is not None, f"Missing run for ({item.item_id}, {cond})"


def test_smoke_sweep_deterministic():
    """Two calls with the same args produce byte-identical run JSON."""
    mod = _import_build_books_sweep()

    def _run_and_serialize():
        with tempfile.TemporaryDirectory() as tmp:
            runset = mod.build_books_sweep(
                n_runs=1,
                stub=True,
                gate="lexical",
                out_dir=Path(tmp),
            )
        return [run.model_dump_json() for run in runset.runs]

    result_a = _run_and_serialize()
    result_b = _run_and_serialize()
    assert result_a == result_b, "Two sweep calls with identical args are not byte-identical"


# ---------------------------------------------------------------------------
# Test: reference contains the committed content labels
# ---------------------------------------------------------------------------


def test_reference_has_five_content_labels():
    """The GradingReference assembled from content_labels.json has >= 5 labels."""
    from ivg_kg.data.reference import load_reference

    reference = load_reference(_SLICE_DIR)
    assert len(reference.content_labels) >= 5, (
        f"Expected at least 5 content labels, got {len(reference.content_labels)}"
    )


def test_reference_content_labels_entity_ids_match_committed_json():
    """Entity IDs in the loaded reference match the committed content_labels.json."""
    committed_raw = json.loads(
        (_SLICE_DIR / "content_labels.json").read_text(encoding="utf-8")
    )
    committed_eids = {d["entity_id"] for d in committed_raw}

    from ivg_kg.data.reference import load_reference
    reference = load_reference(_SLICE_DIR)
    loaded_eids = {lb.entity_id for lb in reference.content_labels}

    assert committed_eids == loaded_eids, (
        f"Entity ID mismatch: committed={committed_eids}, loaded={loaded_eids}"
    )


# ---------------------------------------------------------------------------
# Test: content-arm item under CONTENT_ABSENT has active_perturbations set
# ---------------------------------------------------------------------------


def test_content_absent_run_has_active_perturbations():
    """A content-arm entity under CONTENT_ABSENT has at least one active perturbation."""
    mod = _import_build_books_sweep()

    with tempfile.TemporaryDirectory() as tmp:
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=Path(tmp),
        )

    from ivg_kg.schema import Condition

    # Find a run with CONTENT_ABSENT condition that actually had a perturbation
    # (i.e. an entity in the content arm of the manifest).
    content_absent_runs = [
        r for r in runset.runs if r.condition == Condition.CONTENT_ABSENT
    ]
    assert content_absent_runs, "No CONTENT_ABSENT runs found"

    # At least one content-absent run must have active_perturbations populated
    runs_with_perts = [r for r in content_absent_runs if r.active_perturbations]
    assert runs_with_perts, (
        "No CONTENT_ABSENT run has active_perturbations; "
        "expected at least one content-arm item to have perturbations applied"
    )


# ---------------------------------------------------------------------------
# Test: no-repair baselines point back at the matched FULL run
# ---------------------------------------------------------------------------


def test_no_repair_baselines_have_baseline_run_id():
    """FULL_NO_EDIT_RERUN runs carry baseline_run_id pointing at the FULL run."""
    mod = _import_build_books_sweep()

    with tempfile.TemporaryDirectory() as tmp:
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=Path(tmp),
        )

    from ivg_kg.schema import Condition

    baseline_runs = [
        r for r in runset.runs if r.condition == Condition.FULL_NO_EDIT_RERUN
    ]
    assert baseline_runs, "No FULL_NO_EDIT_RERUN runs found"

    full_run_ids = {
        r.run_id for r in runset.runs if r.condition == Condition.FULL
    }
    for run in baseline_runs:
        assert run.baseline_run_id is not None, (
            f"FULL_NO_EDIT_RERUN run {run.run_id} missing baseline_run_id"
        )
        assert run.baseline_run_id in full_run_ids, (
            f"baseline_run_id {run.baseline_run_id!r} not found among FULL run ids"
        )


# ---------------------------------------------------------------------------
# Test: write_runset does NOT pollute data/runs/ (uses tmp dir)
# ---------------------------------------------------------------------------


def test_smoke_sweep_writes_to_tmp_dir():
    """Files are written to the specified tmp dir, not the default data/runs/."""
    mod = _import_build_books_sweep()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=tmp_path,
        )
        written = list(tmp_path.glob("*.json"))

    assert len(written) == len(runset.runs), (
        f"Expected {len(runset.runs)} files, found {len(written)}"
    )


# ---------------------------------------------------------------------------
# Test: emit_calibration_report default (lexical) preserves existing behaviour
# ---------------------------------------------------------------------------


def test_emit_calibration_report_lexical_default_produces_uncalibrated():
    """Running emit_calibration_report with default (lexical) produces calibrated=False."""
    import importlib
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    with tempfile.TemporaryDirectory():
        # We call main() with lexical gate; the script should accept a gate arg
        # and route through the lexical path.
        mod = importlib.import_module("emit_calibration_report")
        report = mod.build_report(gate="lexical")

    assert report.calibrated is False, f"Expected calibrated=False, got {report.calibrated}"
    assert report.gate == "lexical", f"Expected gate='lexical', got {report.gate!r}"
    assert report.frozen_tau > 0.0, "frozen_tau should be > 0"
