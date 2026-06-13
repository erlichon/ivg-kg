"""Tests for the GR11 offline precompute sweep harness (src/ivg_kg/experiment/sweep.py).

The sweep is the OFFLINE source of the RQ2 modality-contrast aggregate (SPEC-text
sec 8 / 10 / 4.8). It runs, per question x condition x sample, a seeded generation
(GR4) over the ablated context (GR3, the only ablation site) and grounds the answer
against the FULL reference (perturbations never touch grading). It also emits a
matched no-repair re-run baseline (Condition.FULL_NO_EDIT_RERUN) so EX3 can net out
generator variance.

Everything runs offline: a stub BaseAIClient (answer varies by seed so caching/seed
is observable), the lexical entailment gate, the rule-based extractor, the
label-alias linker. No model download, no network, no time, no pickle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ivg_kg.experiment.question_bank import QuestionBank, QuestionBankItem, QuestionTier
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.grounding.generate import GenerationCache
from ivg_kg.schema import (
    ClaimStatus,
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
# Fixtures: a tiny but real GradingReference + question bank + stub client
# ---------------------------------------------------------------------------

_SLICE_ID = "books-test-slice"
_BANK_ID = "books-test-bank"


def _make_reference() -> GradingReference:
    """A small two-entity books reference with descriptions + one outgoing edge each."""
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
        snapshot_id="snap-test-1",
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


class _StubClient(BaseAIClient):
    """Stub generator: a fixed answer text whose suffix varies by seed.

    The grounded portion ("The Glass Menagerie author Tennessee Williams.") is
    stable so claims are deterministic; only an inert suffix varies by seed so
    that caching / seed propagation is observable without changing grading.
    """

    def __init__(self) -> None:
        self.calls = 0

    def _generate(
        self,
        question: str,
        context: Any,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        self.calls += 1
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
# 1. sweep_seed: deterministic, distinct, stable
# ---------------------------------------------------------------------------


class TestSweepSeed:
    def test_deterministic_across_calls(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        a = sweep_seed("qb-1", Condition.FULL, 3)
        b = sweep_seed("qb-1", Condition.FULL, 3)
        assert a == b

    def test_returns_int(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        assert isinstance(sweep_seed("qb-1", Condition.FULL, 0), int)

    def test_distinct_for_different_question(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        assert sweep_seed("qb-1", Condition.FULL, 0) != sweep_seed("qb-2", Condition.FULL, 0)

    def test_distinct_for_different_condition(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        assert sweep_seed("qb-1", Condition.FULL, 0) != sweep_seed(
            "qb-1", Condition.CONTENT_ABSENT, 0
        )

    def test_distinct_for_different_sample_index(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        assert sweep_seed("qb-1", Condition.FULL, 0) != sweep_seed("qb-1", Condition.FULL, 1)

    def test_full_vs_no_edit_rerun_distinct(self) -> None:
        from ivg_kg.experiment.sweep import sweep_seed

        # The no-repair baseline must draw a DIFFERENT seed than its matched FULL run.
        assert sweep_seed("qb-1", Condition.FULL, 2) != sweep_seed(
            "qb-1", Condition.FULL_NO_EDIT_RERUN, 2
        )


# ---------------------------------------------------------------------------
# 2. default_perturbations_for: condition -> perturbation mapping
# ---------------------------------------------------------------------------


class TestDefaultPerturbationsFor:
    def test_full_yields_empty(self) -> None:
        from ivg_kg.experiment.sweep import default_perturbations_for

        bank = _make_bank()
        ref = _make_reference()
        assert default_perturbations_for(bank.items[0], Condition.FULL, ref) == []

    def test_no_edit_rerun_yields_empty(self) -> None:
        from ivg_kg.experiment.sweep import default_perturbations_for

        bank = _make_bank()
        ref = _make_reference()
        assert default_perturbations_for(bank.items[0], Condition.FULL_NO_EDIT_RERUN, ref) == []

    def test_content_absent_yields_text_content_absence(self) -> None:
        from ivg_kg.experiment.sweep import default_perturbations_for
        from ivg_kg.perturbation.text_content_absence import TextContentAbsence

        bank = _make_bank()
        ref = _make_reference()
        perts = default_perturbations_for(bank.items[0], Condition.CONTENT_ABSENT, ref)
        assert len(perts) == 1
        assert isinstance(perts[0], TextContentAbsence)
        assert perts[0].entity_id == "Q1"

    def test_knowledge_absent_withholds_outgoing_triples(self) -> None:
        from ivg_kg.experiment.sweep import default_perturbations_for
        from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence

        bank = _make_bank()
        ref = _make_reference()
        perts = default_perturbations_for(bank.items[0], Condition.KNOWLEDGE_ABSENT, ref)
        assert len(perts) == 1
        ka = perts[0]
        assert isinstance(ka, KnowledgeAbsence)
        # Q1 has two outgoing edges (P50, P136); both must be selected.
        withheld = {(r.subject_id, r.property_id, r.object_id) for r in ka.triples_to_withhold}
        assert withheld == {("Q1", "P50", "Q2"), ("Q1", "P136", "Q3")}

    def test_knowledge_absent_applied_removes_triples_from_context(self) -> None:
        from ivg_kg.experiment.sweep import default_perturbations_for
        from ivg_kg.grounding.context import assemble_context

        bank = _make_bank()
        ref = _make_reference()
        perts = default_perturbations_for(bank.items[0], Condition.KNOWLEDGE_ABSENT, ref)
        ctx = assemble_context(ref, "Q1", perturbations=perts)
        assert ctx.triples == []


# ---------------------------------------------------------------------------
# 3. run_sweep: counts, identity, grading-vs-full
# ---------------------------------------------------------------------------


class TestRunSweepCounts:
    def test_run_counts_with_baseline(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        client = _StubClient()
        n = 3
        conditions = [Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT]
        rs = run_sweep(
            bank,
            ref,
            client,
            conditions=conditions,
            n_runs=n,
            config=_config(),
        )
        # per item: n * len(conditions) primary runs + n baselines (one per FULL run)
        per_item = n * len(conditions) + n
        assert len(rs.runs) == per_item * len(bank.items)

    def test_run_counts_without_baseline(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        client = _StubClient()
        n = 2
        conditions = [Condition.FULL, Condition.CONTENT_ABSENT]
        rs = run_sweep(
            bank,
            ref,
            client,
            conditions=conditions,
            n_runs=n,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        assert len(rs.runs) == n * len(conditions) * len(bank.items)

    def test_runset_metadata(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(bank, ref, _StubClient(), n_runs=1, config=_config())
        assert rs.slice_id == _SLICE_ID
        assert rs.bank_id == _BANK_ID
        assert rs.n_runs == 1
        assert Condition.FULL in rs.conditions

    def test_each_run_has_condition_sample_and_deterministic_id(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        by_id = {r.run_id: r for r in rs.runs}
        assert "qb-1--full--s0" in by_id
        assert "qb-1--content-absent--s1" in by_id
        r = by_id["qb-1--content-absent--s1"]
        assert r.condition == Condition.CONTENT_ABSENT
        assert r.sample_index == 1

    def test_perturbed_run_records_active_perturbations(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.CONTENT_ABSENT],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = next(r for r in rs.runs if r.condition == Condition.CONTENT_ABSENT)
        assert run.active_perturbations == ["text_content_absence:Q1"]

    def test_grading_uses_full_reference_not_perturbation(self) -> None:
        """Control: identical answer text grounded under FULL vs CONTENT_ABSENT
        yields the SAME claims, because grading ignores the perturbation
        (the perturbation only changed what the generator saw, not grading).
        """
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        # Same stub answer text for both conditions (it does not branch on context),
        # so any claim-status difference would have to come from grading -- which
        # must not happen.
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        full = next(
            r for r in rs.runs if r.condition == Condition.FULL and r.run_id.startswith("qb-1")
        )
        absent = next(
            r
            for r in rs.runs
            if r.condition == Condition.CONTENT_ABSENT and r.run_id.startswith("qb-1")
        )
        # The stub answer suffix differs by seed, but the grounded claim statuses
        # are a function of the FULL reference only.
        assert [c.status for c in full.claims] == [c.status for c in absent.claims]
        assert full.grading_reference_id == absent.grading_reference_id

    def test_a_grounded_claim_is_present(self) -> None:
        """Sanity: the canned answer grounds at least one claim (pipeline wired)."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = next(r for r in rs.runs if r.run_id == "qb-1--full--s0")
        statuses = {c.status for c in run.claims}
        assert ClaimStatus.RETRIEVED in statuses or ClaimStatus.REASONED_SUPPORTABLE in statuses


# ---------------------------------------------------------------------------
# 4. No-repair baseline: matched, keyed, tagged
# ---------------------------------------------------------------------------


class TestNoRepairBaseline:
    def test_each_full_run_has_matched_baseline(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        n = 3
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=n,
            config=_config(),
        )
        full_runs = [r for r in rs.runs if r.condition == Condition.FULL]
        baselines = [r for r in rs.runs if r.condition == Condition.FULL_NO_EDIT_RERUN]
        assert len(full_runs) == n * len(bank.items)
        assert len(baselines) == n * len(bank.items)

        full_ids = {r.run_id for r in full_runs}
        for b in baselines:
            assert b.baseline_run_id in full_ids
            assert b.condition == Condition.FULL_NO_EDIT_RERUN

    def test_baseline_run_id_keying(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
        )
        b = next(
            r
            for r in rs.runs
            if r.condition == Condition.FULL_NO_EDIT_RERUN
            and r.run_id == "qb-1--full-no-edit-rerun--s1"
        )
        assert b.baseline_run_id == "qb-1--full--s1"

    def test_no_baseline_for_non_full_conditions(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
        )
        assert all(r.condition != Condition.FULL_NO_EDIT_RERUN for r in rs.runs)


# ---------------------------------------------------------------------------
# 5. Determinism: same inputs -> equal RunSet
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_two_sweeps_equal(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs1 = run_sweep(bank, ref, _StubClient(), n_runs=2, config=_config())
        rs2 = run_sweep(bank, ref, _StubClient(), n_runs=2, config=_config())
        assert rs1.model_dump() == rs2.model_dump()

    def test_cache_avoids_regeneration(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        run_sweep(bank, ref, client, n_runs=2, config=_config(), cache=cache)
        calls_after_first = client.calls
        # Re-running with the SAME cache must not call the client again.
        run_sweep(bank, ref, client, n_runs=2, config=_config(), cache=cache)
        assert client.calls == calls_after_first


# ---------------------------------------------------------------------------
# 6. Component-reuse seam: ground_response still works
# ---------------------------------------------------------------------------


class TestComponentReuseSeam:
    def test_ground_response_still_returns_run(self) -> None:
        from ivg_kg.grounding.backend import ground_response

        ref = _make_reference()
        run = ground_response(
            "Who wrote The Glass Menagerie?",
            "The Glass Menagerie author Tennessee Williams.",
            ref,
            active_perturbations=[],
            config=_config(),
        )
        assert isinstance(run, GroundingRun)
        assert run.slice == "books"

    def test_ground_with_components_importable(self) -> None:
        from ivg_kg.grounding.backend import _ground_with_components

        assert callable(_ground_with_components)


# ---------------------------------------------------------------------------
# 7. write_runset: one json per run, reloadable
# ---------------------------------------------------------------------------


class TestWriteRunset:
    def test_writes_one_file_per_run(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_runset

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        paths = write_runset(rs, out_dir=tmp_path)
        assert len(paths) == len(rs.runs)
        for p in paths:
            assert p.exists()

    def test_filenames_match_run_ids(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_runset

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        paths = write_runset(rs, out_dir=tmp_path)
        stems = {p.stem for p in paths}
        assert {r.run_id for r in rs.runs} == stems

    def test_written_file_reloads_as_grounding_run(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_runset

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        paths = write_runset(rs, out_dir=tmp_path)
        loaded = GroundingRun.model_validate_json(paths[0].read_text(encoding="utf-8"))
        original = next(r for r in rs.runs if r.run_id == paths[0].stem)
        assert loaded.model_dump() == original.model_dump()

    def test_write_is_deterministic(self, tmp_path: Path) -> None:
        from ivg_kg.experiment.sweep import run_sweep, write_runset

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        out1 = tmp_path / "a"
        out2 = tmp_path / "b"
        p1 = write_runset(rs, out_dir=out1)
        p2 = write_runset(rs, out_dir=out2)
        for a, b in zip(sorted(p1), sorted(p2), strict=True):
            assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 8. Schema: FULL_NO_EDIT_RERUN member round-trips
# ---------------------------------------------------------------------------


class TestConditionMember:
    def test_value(self) -> None:
        assert Condition.FULL_NO_EDIT_RERUN.value == "full-no-edit-rerun"

    def test_round_trips_in_grounding_run(self) -> None:
        run = GroundingRun(
            run_id="x--full-no-edit-rerun--s0",
            question="q",
            answer_text="a",
            slice="books",
            phase="A",
            condition=Condition.FULL_NO_EDIT_RERUN,
            sample_index=0,
            baseline_run_id="x--full--s0",
            claims=[],
        )
        dumped = run.model_dump_json()
        reloaded = GroundingRun.model_validate_json(dumped)
        assert reloaded.condition == Condition.FULL_NO_EDIT_RERUN
        assert reloaded.baseline_run_id == "x--full--s0"


# ---------------------------------------------------------------------------
# 9. Custom perturbations_for override is honored
# ---------------------------------------------------------------------------


class TestPerturbationsOverride:
    def test_custom_perturbations_for_used(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()

        def no_perts(item: Any, condition: Any, reference: Any) -> list[Any]:
            return []

        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.CONTENT_ABSENT],
            n_runs=1,
            config=_config(),
            perturbations_for=no_perts,
            emit_no_repair_baseline=False,
        )
        run = next(r for r in rs.runs if r.condition == Condition.CONTENT_ABSENT)
        assert run.active_perturbations == []


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_n_runs_zero_yields_empty_runs(self) -> None:
        """run_sweep with n_runs=0 produces a RunSet with an empty runs list."""
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            n_runs=0,
            config=_config(),
        )
        assert rs.runs == []

    def test_knowledge_absent_leaf_entity_no_outgoing_triples(self) -> None:
        """KNOWLEDGE_ABSENT on a leaf entity (no outgoing edges) yields
        KnowledgeAbsence([]) and assemble_context leaves triples unchanged
        (degenerates gracefully, no error).
        """
        from ivg_kg.experiment.sweep import default_perturbations_for
        from ivg_kg.grounding.context import assemble_context
        from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence

        # Build a reference where Q3 is a leaf: it appears as an object but has
        # no outgoing edges of its own.
        nodes = [
            KGNode(id="Q1", label="The Glass Menagerie", description="a memory play"),
            KGNode(id="Q3", label="drama", description=None),
        ]
        edges = [
            KGEdge(
                subject_id="Q1",
                property_id="P136",
                property_label="genre",
                object_id="Q3",
                object_label="drama",
                value_type=ValueType.ITEM,
            ),
        ]
        snapshot = KGSnapshot(
            snapshot_id="snap-leaf-1",
            slice="books",
            domain_qid="Q571",
            nodes=nodes,
            edges=edges,
        )
        ref = GradingReference(snapshot=snapshot, content_labels=[])

        # QuestionBankItem for the leaf entity Q3.
        leaf_item = QuestionBankItem(
            item_id="qb-leaf",
            question="What is the genre called drama?",
            tier=QuestionTier.ONE_HOP_RETRIEVAL,
            entity_id="Q3",
            slice_id="books-leaf-test",
        )

        perts = default_perturbations_for(leaf_item, Condition.KNOWLEDGE_ABSENT, ref)
        assert len(perts) == 1
        ka = perts[0]
        assert isinstance(ka, KnowledgeAbsence)
        # Q3 has no outgoing edges, so the withhold list is empty.
        assert ka.triples_to_withhold == []

        # assemble_context with KnowledgeAbsence([]) must not error and must
        # leave the triples of Q3 unchanged (there are none to withhold).
        ctx_full = assemble_context(ref, "Q3", perturbations=[])
        ctx_ablated = assemble_context(ref, "Q3", perturbations=perts)
        assert ctx_ablated.triples == ctx_full.triples


# ---------------------------------------------------------------------------
# 11. RunSet.get helper
# ---------------------------------------------------------------------------


class TestRunSetGet:
    def test_get_returns_matching_run(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=2,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        run = rs.get("qb-1", Condition.FULL, 1)
        assert run is not None
        assert run.run_id == "qb-1--full--s1"
        assert run.condition == Condition.FULL
        assert run.sample_index == 1

    def test_get_returns_none_for_missing(self) -> None:
        from ivg_kg.experiment.sweep import run_sweep

        bank = _make_bank()
        ref = _make_reference()
        rs = run_sweep(
            bank,
            ref,
            _StubClient(),
            conditions=[Condition.FULL],
            n_runs=1,
            config=_config(),
            emit_no_repair_baseline=False,
        )
        assert rs.get("qb-99", Condition.FULL, 0) is None
        assert rs.get("qb-1", Condition.CONTENT_ABSENT, 0) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
