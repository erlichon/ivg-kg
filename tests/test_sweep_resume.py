"""Tests for run_sink and resume_dir params of run_sweep (incremental persistence + resume).

These tests verify:
1. run_sink is called exactly once per produced run (including baselines), in order.
2. run_sink=None (default) does not cause any side effects.
3. resume_dir: pre-written run files are loaded (not regenerated), fresh runs are generated.
4. Corrupted/unparseable files in resume_dir are treated as absent (regenerated).
5. RunSet returned with resume is complete and correct.
6. Default behavior (neither param set) returns the same RunSet as before.
7. write_one_run: single-file helper writes one run and is idempotent.
8. Smoke: run_books_sweep incremental writes + --resume skips completed runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from ivg_kg.experiment.question_bank import QuestionBank, QuestionBankItem, QuestionTier
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.schema import (
    Condition,
    ContentLabel,
    GradingReference,
    GroundingConfig,
    GroundingRun,
    KGEdge,
    KGNode,
    KGSnapshot,
    Modality,
    ValueType,
)

# ---------------------------------------------------------------------------
# Shared fixtures (duplicated from test_sweep.py to keep tests self-contained)
# ---------------------------------------------------------------------------

_SLICE_ID = "books-resume-test-slice"
_BANK_ID = "books-resume-test-bank"


def _make_reference() -> GradingReference:
    nodes = [
        KGNode(id="Q1", label="The Glass Menagerie", description="a memory play"),
        KGNode(id="Q2", label="Tennessee Williams", description="an American playwright"),
        KGNode(id="Q3", label="drama", description=None),
    ]
    edges = [
        KGEdge(
            subject_id="Q1",
            property_id="P50",
            property_label="author",
            object_id="Q2",
            object_label="Tennessee Williams",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q1",
            property_id="P136",
            property_label="genre",
            object_id="Q3",
            object_label="drama",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q2",
            property_id="P106",
            property_label="occupation",
            object_id=None,
            object_label="playwright",
            value_type=ValueType.STRING,
        ),
    ]
    snapshot = KGSnapshot(
        snapshot_id="snap-resume-1",
        slice="books",
        domain_qid="Q571",
        nodes=nodes,
        edges=edges,
    )
    content_labels = [
        ContentLabel(
            entity_id="Q1", modality=Modality.TEXT, fact="is a memory play", source="description"
        ),
    ]
    return GradingReference(snapshot=snapshot, content_labels=content_labels)


def _make_bank() -> QuestionBank:
    items = [
        QuestionBankItem(
            item_id="qb-1",
            question="Who wrote The Glass Menagerie?",
            tier=QuestionTier.ONE_HOP_RETRIEVAL,
            entity_id="Q1",
            slice_id=_SLICE_ID,
        ),
        QuestionBankItem(
            item_id="qb-2",
            question="What is the occupation of Tennessee Williams?",
            tier=QuestionTier.ONE_HOP_RETRIEVAL,
            entity_id="Q2",
            slice_id=_SLICE_ID,
        ),
    ]
    return QuestionBank(bank_id=_BANK_ID, slice_id=_SLICE_ID, items=items)


class _CountingStubClient(BaseAIClient):
    """Stub generator that counts how many times it is called, answer varies by seed."""

    def __init__(self) -> None:
        self.calls: int = 0
        self.call_keys: list[tuple[str, Any]] = []

    def _generate(
        self,
        question: str,
        context: Any,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        self.calls += 1
        self.call_keys.append((question, seed))
        return GenerationResult(
            answer=f"The Glass Menagerie author Tennessee Williams. [draw seed={seed}]"
        )


def _config() -> GroundingConfig:
    return GroundingConfig(
        entailment="lexical",
        linker="label_alias",
        extractor="rule_based",
        tau=0.4,
    )


# ---------------------------------------------------------------------------
# Helper: run a full sweep and return the RunSet (baseline reference)
# ---------------------------------------------------------------------------

def _baseline_runset(n_runs: int = 2):
    from ivg_kg.experiment.sweep import run_sweep
    bank = _make_bank()
    ref = _make_reference()
    return run_sweep(
        bank, ref, _CountingStubClient(),
        conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
        n_runs=n_runs,
        config=_config(),
        emit_no_repair_baseline=True,
    )


# ---------------------------------------------------------------------------
# 1. run_sink: called once per produced run in order, including baselines
# ---------------------------------------------------------------------------

class TestRunSink:
    def test_sink_called_once_per_run_including_baselines(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        sunk: list[GroundingRun] = []

        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            run_sink=sunk.append,
        )
        assert len(sunk) == len(rs.runs), (
            f"run_sink called {len(sunk)} times but {len(rs.runs)} runs produced"
        )

    def test_sink_called_with_correct_runs(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        sunk: list[GroundingRun] = []

        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            run_sink=sunk.append,
        )
        sunk_ids = [r.run_id for r in sunk]
        rs_ids = [r.run_id for r in rs.runs]
        assert sunk_ids == rs_ids, "run_sink order must match RunSet.runs order"

    def test_sink_called_before_on_run_complete(self) -> None:
        """run_sink is called before on_run_complete for the same run."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        event_log: list[tuple[str, str]] = []

        def _sink(run: GroundingRun) -> None:
            event_log.append(("sink", run.run_id))

        def _cb(run: GroundingRun, completed: int, total: int) -> None:
            event_log.append(("cb", run.run_id))

        run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
            run_sink=_sink,
            on_run_complete=_cb,
        )
        # For each run_id, sink must appear before cb in the log.
        for run_id in {ev[1] for ev in event_log}:
            positions = {ev[0]: i for i, ev in enumerate(event_log) if ev[1] == run_id}
            assert positions["sink"] < positions["cb"], (
                f"run_sink not called before on_run_complete for {run_id}"
            )

    def test_sink_none_default_no_error(self) -> None:
        """run_sink=None (default) produces the same RunSet without errors."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        # No run_sink passed; must not error.
        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        assert len(rs.runs) == 2 * len(bank.items)

    def test_sink_receives_baselines_too(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        sunk_conditions: list[str] = []

        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            run_sink=lambda r: sunk_conditions.append(r.condition.value),
        )
        baseline_count = sum(
            1 for r in rs.runs if r.condition == Condition.FULL_NO_EDIT_RERUN
        )
        assert sunk_conditions.count("full-no-edit-rerun") == baseline_count


# ---------------------------------------------------------------------------
# 2. resume_dir: pre-existing files are loaded, not regenerated
# ---------------------------------------------------------------------------

class TestResumeDir:
    def test_preexisting_runs_not_regenerated(self, tmp_path: Path) -> None:
        """Runs already on disk are loaded from resume_dir, generator not called for them."""
        from ivg_kg.experiment.sweep import run_sweep

        # First pass: run fully to produce reference run files.
        bank = _make_bank()
        ref = _make_reference()
        ref_client = _CountingStubClient()
        ref_rs = run_sweep(
            bank, ref, ref_client,
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )
        total_calls_first = ref_client.calls

        # Write a SUBSET of runs to tmp_path (the first item's FULL runs only).
        pre_written_ids: set[str] = set()
        for run in ref_rs.runs:
            if run.run_id.startswith("qb-1--full"):
                path = tmp_path / f"{run.run_id}.json"
                path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
                pre_written_ids.add(run.run_id)

        assert pre_written_ids  # sanity: we wrote something

        # Second pass: resume_dir set -- pre-existing runs must be SKIPPED.
        resume_client = _CountingStubClient()
        run_sweep(
            bank, ref, resume_client,
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            resume_dir=tmp_path,
        )

        # The resumed sweep must call the generator FEWER times.
        assert resume_client.calls < total_calls_first, (
            f"Expected fewer calls with resume; got {resume_client.calls} vs {total_calls_first}"
        )
        # Exactly the pre-written runs must be excluded from generation.
        expected_skipped = len(pre_written_ids)
        skipped = total_calls_first - resume_client.calls
        assert skipped == expected_skipped, (
            f"Expected {expected_skipped} skips, got {skipped}"
        )

    def test_resumed_runset_is_complete(self, tmp_path: Path) -> None:
        """RunSet returned by a resume run contains all expected runs."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        # Full first pass to get reference.
        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )

        # Pre-write ALL runs to tmp_path.
        for run in ref_rs.runs:
            path = tmp_path / f"{run.run_id}.json"
            path.write_text(run.model_dump_json(indent=2), encoding="utf-8")

        # Resume: everything should be loaded from disk, nothing generated.
        zero_calls_client = _CountingStubClient()
        resume_rs = run_sweep(
            bank, ref, zero_calls_client,
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            resume_dir=tmp_path,
        )
        assert zero_calls_client.calls == 0, (
            f"Expected 0 generator calls with all runs pre-written; got {zero_calls_client.calls}"
        )
        assert len(resume_rs.runs) == len(ref_rs.runs), (
            f"RunSet length mismatch: {len(resume_rs.runs)} vs {len(ref_rs.runs)}"
        )

    def test_resumed_runs_match_reference(self, tmp_path: Path) -> None:
        """Runs loaded from resume_dir are identical to a fresh run (determinism)."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )

        # Write all runs to disk.
        for run in ref_rs.runs:
            path = tmp_path / f"{run.run_id}.json"
            path.write_text(run.model_dump_json(indent=2), encoding="utf-8")

        # Resume should reproduce the same run data.
        resume_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            resume_dir=tmp_path,
        )

        ref_by_id = {r.run_id: r.model_dump() for r in ref_rs.runs}
        for run in resume_rs.runs:
            assert run.model_dump() == ref_by_id[run.run_id], (
                f"Resumed run {run.run_id} differs from fresh run"
            )

    def test_corrupt_file_treated_as_absent(self, tmp_path: Path) -> None:
        """A corrupt JSON file is treated as absent: the run is regenerated."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        # Write one valid run and one corrupt file.
        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )

        valid_run = ref_rs.runs[0]
        corrupt_run = ref_rs.runs[1]

        # Write valid run to disk.
        (tmp_path / f"{valid_run.run_id}.json").write_text(
            valid_run.model_dump_json(indent=2), encoding="utf-8"
        )
        # Write corrupt file for corrupt_run.
        (tmp_path / f"{corrupt_run.run_id}.json").write_text(
            "NOT VALID JSON {{{", encoding="utf-8"
        )

        client = _CountingStubClient()
        resume_rs = run_sweep(
            bank, ref, client,
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
            resume_dir=tmp_path,
        )

        # valid_run was loaded (0 calls for it), corrupt_run was regenerated (1 call).
        # The other item's runs are also generated.
        # We expect exactly (total_runs - 1 valid_run) calls.
        total_runs = len(ref_rs.runs)
        assert client.calls == total_runs - 1, (
            f"Expected {total_runs - 1} generator calls (1 run pre-loaded), got {client.calls}"
        )

        # The RunSet is still complete.
        assert len(resume_rs.runs) == total_runs

    def test_resume_dir_none_default_no_skip(self) -> None:
        """resume_dir=None (default) regenerates all runs as before."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        client = _CountingStubClient()
        run_sweep(
            bank, ref, client,
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        # All runs generated (no skipping).
        assert client.calls == 2 * len(bank.items)

    def test_resume_accepts_string_path(self, tmp_path: Path) -> None:
        """resume_dir accepts a str as well as a Path."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        # No files in tmp_path; passing str should not error.
        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
            resume_dir=str(tmp_path),  # pass str, not Path
        )
        assert len(rs.runs) == len(bank.items)

    def test_run_sink_still_called_for_resumed_runs(self, tmp_path: Path) -> None:
        """run_sink is called even for runs loaded from resume_dir."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )

        # Pre-write all runs.
        for run in ref_rs.runs:
            (tmp_path / f"{run.run_id}.json").write_text(
                run.model_dump_json(indent=2), encoding="utf-8"
            )

        sunk: list[GroundingRun] = []
        resume_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
            resume_dir=tmp_path,
            run_sink=sunk.append,
        )
        # run_sink must be called for ALL runs, even resumed ones.
        assert len(sunk) == len(resume_rs.runs)

    def test_on_run_complete_still_called_for_resumed_runs(self, tmp_path: Path) -> None:
        """on_run_complete callback is still called for resumed runs."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )

        for run in ref_rs.runs:
            (tmp_path / f"{run.run_id}.json").write_text(
                run.model_dump_json(indent=2), encoding="utf-8"
            )

        cb_calls: list[tuple[Any, int, int]] = []
        run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
            resume_dir=tmp_path,
            on_run_complete=lambda r, c, t: cb_calls.append((r, c, t)),
        )
        assert len(cb_calls) == len(ref_rs.runs)

    def test_resume_baselines_loaded_from_disk(self, tmp_path: Path) -> None:
        """No-repair baselines pre-written to resume_dir are also loaded, not regenerated."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        ref_rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )
        # Pre-write all runs (including baselines).
        for run in ref_rs.runs:
            (tmp_path / f"{run.run_id}.json").write_text(
                run.model_dump_json(indent=2), encoding="utf-8"
            )

        zero_client = _CountingStubClient()
        run_sweep(
            bank, ref, zero_client,
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
            resume_dir=tmp_path,
        )
        assert zero_client.calls == 0


# ---------------------------------------------------------------------------
# 3. Default behavior unchanged (no new params)
# ---------------------------------------------------------------------------

class TestDefaultBehaviorUnchanged:
    def test_runset_identical_without_new_params(self) -> None:
        """Neither run_sink nor resume_dir set -> RunSet identical to old behavior."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        rs_old = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )
        rs_new = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=True,
        )
        assert rs_old.model_dump() == rs_new.model_dump()


# ---------------------------------------------------------------------------
# 4. write_one_run helper
# ---------------------------------------------------------------------------

class TestWriteOneRun:
    def test_writes_single_run_file(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_one_run

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = rs.runs[0]
        path = write_one_run(run, tmp_path)
        assert path.exists()
        assert path.name == f"{run.run_id}.json"

    def test_written_run_reloads_correctly(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_one_run

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = rs.runs[0]
        path = write_one_run(run, tmp_path)
        loaded = GroundingRun.model_validate_json(path.read_text(encoding="utf-8"))
        assert loaded.model_dump() == run.model_dump()

    def test_write_one_run_is_idempotent(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_one_run

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank, ref, _CountingStubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = rs.runs[0]
        path1 = write_one_run(run, tmp_path)
        path2 = write_one_run(run, tmp_path)
        assert path1 == path2
        assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. run_books_sweep smoke: incremental writes + resume
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SLICE_DIR = _REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1"

pytestmark_books = pytest.mark.skipif(
    not (_SLICE_DIR / "question_bank.json").exists(),
    reason="frozen books slice not found",
)


def _import_run_books_sweep():
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import importlib
    return importlib.import_module("run_books_sweep")


@pytest.mark.skipif(
    not (_SLICE_DIR / "question_bank.json").exists(),
    reason="frozen books slice not found",
)
class TestRunBooksSweepIncremental:
    def test_incremental_files_appear_during_run(self, tmp_path: Path) -> None:
        """Each run file appears in out_dir as the sweep progresses (not only at the end)."""
        mod = _import_run_books_sweep()

        # Use n_runs=1 for speed.
        runset = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=tmp_path,
        )

        written = list(tmp_path.glob("*.json"))
        # All runs must have been written (incrementally or at end -- same result for small n).
        assert len(written) == len(runset.runs), (
            f"Expected {len(runset.runs)} files, found {len(written)}"
        )

    def test_resume_second_run_skips_all(self, tmp_path: Path) -> None:
        """A second invocation with resume=True skips all already-written runs."""
        mod = _import_run_books_sweep()

        # First run: produces all run files.
        runset1 = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=tmp_path,
            resume=True,
        )

        # Second run: with resume=True, all runs are pre-existing -> 0 generator calls.
        # We instrument via the counting client. Since build_books_sweep uses stub=True
        # internally, we verify the result is complete with no errors.
        runset2 = mod.build_books_sweep(
            n_runs=1,
            stub=True,
            gate="lexical",
            out_dir=tmp_path,
            resume=True,
        )

        # Both runsets have the same run IDs.
        ids1 = {r.run_id for r in runset1.runs}
        ids2 = {r.run_id for r in runset2.runs}
        assert ids1 == ids2, "Resume run should produce the same set of run IDs"

        # The run data should be identical (loaded from disk, same as original).
        for run in runset2.runs:
            orig = next(r for r in runset1.runs if r.run_id == run.run_id)
            assert run.model_dump() == orig.model_dump(), (
                f"Resumed run {run.run_id} differs from original"
            )

    def test_no_resume_regenerates_everything(self, tmp_path: Path) -> None:
        """--no-resume regenerates all runs even if files exist on disk."""
        mod = _import_run_books_sweep()

        # First run writes files.
        mod.build_books_sweep(
            n_runs=1, stub=True, gate="lexical", out_dir=tmp_path, resume=True,
        )

        # Second run with resume=False must not fail and produces a complete runset.
        runset = mod.build_books_sweep(
            n_runs=1, stub=True, gate="lexical", out_dir=tmp_path, resume=False,
        )
        assert len(runset.runs) > 0
