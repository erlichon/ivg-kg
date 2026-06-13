"""Tests for Task #1a vertical-slice grounding backend.

Covers the TDD requirements from the task spec:
  1. grade-vs-reference invariant: active_perturbations do NOT change claim grades.
  2. Value-sensitive FABRICATED: a wrong-VALUE claim grades FABRICATED + spurious_path=True.
  3. REASONED_SUPPORTABLE via undirected 2-hop path (book->author<-book shape).
  4. JSON round-trip for every emitted GroundingRun.
  5. Generator determinism: two runs produce byte-identical output.
  6. Generator coverage: >=3 runs, >=1 FABRICATED, >=1 REASONED_SUPPORTABLE.
  7. ground_response no longer raises NotImplementedError.
"""
from __future__ import annotations

from pathlib import Path

from ivg_kg.data.graph_store import load_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.grounding.backend import ground_response
from ivg_kg.grounding.slice import entails, run_cascade, split_claims
from ivg_kg.schema import (
    ClaimStatus,
    GradingReference,
    GroundingConfig,
    GroundingRun,
    SupportSource,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SNAPSHOT_DIR = Path(__file__).parent.parent / "data" / "frozen" / "books" / "books-p0-v1"
_DEFAULT_CONFIG = GroundingConfig(k_hops=2, tau=0.3)


def _load_snapshot():
    return load_snapshot(_SNAPSHOT_DIR)


def _make_glass_menagerie_ref(snapshot) -> GradingReference:
    """GradingReference for The Glass Menagerie examples."""
    return assemble_reference(
        snapshot,
        author_books_content_labels([
            (
                "Q678832",
                "The Glass Menagerie is set in a small apartment in St Louis during the Great Depression",
                "description",
            ),
        ]),
    )


def _make_pelevin_ref(snapshot) -> GradingReference:
    """GradingReference for the Pelevin shared-author example."""
    return assemble_reference(
        snapshot,
        author_books_content_labels([
            (
                "Q105485274",
                "Blue Lantern is a short story collection by Victor Pelevin in Russian",
                "description",
            ),
            (
                "Q105623200",
                "DTP(NN) is a novel by Victor Pelevin published in 2003 by Eksmo",
                "description",
            ),
        ]),
    )


def _make_principles_ref(snapshot) -> GradingReference:
    """GradingReference for Principles of Economics."""
    return assemble_reference(
        snapshot,
        author_books_content_labels([
            (
                "Q4338113",
                "Principles of Economics introduced the concept of marginal utility and founded the Austrian School",
                "description",
            ),
        ]),
    )


# ---------------------------------------------------------------------------
# 7. ground_response does NOT raise NotImplementedError
# ---------------------------------------------------------------------------

def test_ground_response_not_stub():
    """ground_response must no longer raise NotImplementedError."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    run = ground_response(
        "Who wrote The Glass Menagerie?",
        "Tennessee Williams wrote The Glass Menagerie.",
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    assert isinstance(run, GroundingRun)
    assert len(run.claims) > 0


# ---------------------------------------------------------------------------
# 1. grade-vs-reference invariant
# ---------------------------------------------------------------------------

def test_perturbations_do_not_change_claim_grades():
    """active_perturbations is for attribution only; grading must be identical
    regardless of whether perturbations are present or empty."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    answer = (
        "Tennessee Williams wrote The Glass Menagerie. "
        "The Glass Menagerie is set in a small apartment during the Great Depression. "
        "The Glass Menagerie had its world premiere in New York in 1960."
    )

    run_no_pert = ground_response(
        "Tell me about The Glass Menagerie.",
        answer,
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    run_with_pert = ground_response(
        "Tell me about The Glass Menagerie.",
        answer,
        ref,
        active_perturbations=["pert-knowledge-q678832", "pert-text-q678832"],
        config=_DEFAULT_CONFIG,
    )

    # Same number of claims
    assert len(run_no_pert.claims) == len(run_with_pert.claims), (
        "Perturbations must not change the number of claims"
    )

    # Identical grading for every claim (status, support_source, entailment_score)
    for c_no, c_with in zip(run_no_pert.claims, run_with_pert.claims, strict=False):
        assert c_no.status == c_with.status, (
            f"Claim {c_no.claim_id}: status changed with perturbations "
            f"({c_no.status} vs {c_with.status})"
        )
        assert c_no.support_source == c_with.support_source
        assert c_no.entailment_score == c_with.entailment_score


# ---------------------------------------------------------------------------
# 2. Value-sensitive FABRICATED (wrong value -> spurious_path=True)
# ---------------------------------------------------------------------------

def test_wrong_value_claim_grades_fabricated_with_spurious_path():
    """A claim asserting a concrete value not in the reference must be FABRICATED
    with spurious_path=True (value-sensitive gate fired)."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    # The real premiere was 1944 in Chicago; claim says 1960 in New York.
    wrong_year_claim = "The Glass Menagerie had its world premiere in New York in 1960."
    records = run_cascade(
        "When was the premiere?",
        wrong_year_claim,
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    assert len(records) == 1
    rec = records[0]
    assert rec.status == ClaimStatus.FABRICATED, (
        f"Expected FABRICATED, got {rec.status}"
    )
    assert rec.spurious_path is True, (
        "spurious_path must be True when value gate killed a candidate"
    )
    assert rec.spurious_reason is not None, "spurious_reason must be set"


def test_entity_match_alone_is_not_support():
    """A claim that mentions the correct entity but asserts a wrong concrete
    value must still grade FABRICATED, not RETRIEVED."""
    snapshot = _load_snapshot()
    ref = _make_principles_ref(snapshot)
    # Principles of Economics was published in Vienna in 1871; claim says Berlin 1850.
    wrong_city_claim = "Principles of Economics was published in Berlin in 1850."
    records = run_cascade(
        "Where was it published?",
        wrong_city_claim,
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    assert len(records) == 1
    assert records[0].status == ClaimStatus.FABRICATED
    assert records[0].spurious_path is True


# ---------------------------------------------------------------------------
# 3. REASONED_SUPPORTABLE via 2-hop path
# ---------------------------------------------------------------------------

def test_two_hop_shared_author_grades_reasoned_supportable():
    """A claim derivable only via a 2-hop undirected path must grade
    REASONED_SUPPORTABLE with support_source MULTI_HOP_PATH.

    Path: Blue Lantern --[author]--> Victor Pelevin <--[author]-- DTP(NN)
    """
    snapshot = _load_snapshot()
    ref = _make_pelevin_ref(snapshot)
    multi_hop_claim = "Blue Lantern and DTP were both written by Pelevin."
    records = run_cascade(
        "Tell me about Pelevin books.",
        multi_hop_claim,
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    assert len(records) == 1
    rec = records[0]
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE, (
        f"Expected REASONED_SUPPORTABLE, got {rec.status}"
    )
    assert rec.support_source == SupportSource.MULTI_HOP_PATH
    # Path must have >= 2 edges
    assert len(rec.grounding_path.edges) >= 2, (
        f"Expected >= 2 path edges, got {len(rec.grounding_path.edges)}"
    )
    # At least one edge traversed in reverse (undirected search)
    assert any(not pe.traversed_forward for pe in rec.grounding_path.edges), (
        "Expected at least one reverse edge in the 2-hop path"
    )
    # Victor Pelevin (Q246722) must appear in the path node_ids
    assert "Q246722" in rec.grounding_path.node_ids, (
        "Victor Pelevin (Q246722) must be an intermediate node in the path"
    )


# ---------------------------------------------------------------------------
# 4. JSON round-trip for every emitted GroundingRun
# ---------------------------------------------------------------------------

def test_grounding_run_json_round_trip():
    """Every GroundingRun from ground_response round-trips via model_dump_json."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    answer = (
        "Tennessee Williams wrote The Glass Menagerie. "
        "The Glass Menagerie is set in a small apartment during the Great Depression. "
        "The Glass Menagerie had its world premiere in New York in 1960."
    )
    run = ground_response(
        "Tell me about The Glass Menagerie.",
        answer,
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    json_str = run.model_dump_json()
    reconstructed = GroundingRun.model_validate_json(json_str)
    assert reconstructed == run
    # Verify enums survive round-trip
    for claim in reconstructed.claims:
        assert isinstance(claim.status, ClaimStatus)
        assert isinstance(claim.support_source, SupportSource)


def test_all_slice_examples_round_trip():
    """All 3 slice examples must round-trip cleanly."""
    from scripts.emit_slice_runs import build_slice_examples

    runs = build_slice_examples()
    assert len(runs) >= 3
    for run in runs:
        json_str = run.model_dump_json()
        reconstructed = GroundingRun.model_validate_json(json_str)
        assert reconstructed == run, f"Round-trip failed for run {run.run_id}"


# ---------------------------------------------------------------------------
# 5. Generator determinism
# ---------------------------------------------------------------------------

def test_generator_is_deterministic(tmp_path):
    """Running the generator twice produces byte-identical files."""
    from scripts.emit_slice_runs import emit_slice_runs

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"
    paths1 = emit_slice_runs(dir1)
    paths2 = emit_slice_runs(dir2)

    assert len(paths1) == len(paths2)
    for p1, p2 in zip(paths1, paths2, strict=False):
        content1 = p1.read_text(encoding="utf-8")
        content2 = p2.read_text(encoding="utf-8")
        assert content1 == content2, (
            f"Non-deterministic output: {p1.name} differs between two runs"
        )


# ---------------------------------------------------------------------------
# 6. Generator coverage: >=3 runs, >=1 FABRICATED, >=1 REASONED_SUPPORTABLE
# ---------------------------------------------------------------------------

def test_generator_coverage():
    """Generator must emit >= 3 runs spanning FABRICATED and REASONED_SUPPORTABLE."""
    from scripts.emit_slice_runs import build_slice_examples

    runs = build_slice_examples()
    assert len(runs) >= 3, f"Expected >= 3 runs, got {len(runs)}"

    all_claims = [claim for run in runs for claim in run.claims]
    has_fabricated = any(c.status == ClaimStatus.FABRICATED for c in all_claims)
    has_reasoned = any(c.status == ClaimStatus.REASONED_SUPPORTABLE for c in all_claims)

    assert has_fabricated, "Generator must produce >= 1 FABRICATED claim across the 3 runs"
    assert has_reasoned, "Generator must produce >= 1 REASONED_SUPPORTABLE claim across the 3 runs"


def test_generator_run_ids_are_unique():
    """Each emitted run must have a unique run_id."""
    from scripts.emit_slice_runs import build_slice_examples

    runs = build_slice_examples()
    run_ids = [r.run_id for r in runs]
    assert len(set(run_ids)) == len(run_ids), "Run IDs must be unique"


# ---------------------------------------------------------------------------
# Additional slice invariants
# ---------------------------------------------------------------------------

def test_claim_splitting_deterministic():
    """split_claims produces the same output on repeated calls (deterministic)."""
    text = "Tennessee Williams wrote The Glass Menagerie. It premiered in 1944."
    result1 = split_claims(text)
    result2 = split_claims(text)
    assert result1 == result2
    assert len(result1) == 2


def test_entailment_gate_value_sensitive():
    """entails must return 0.0 when hypothesis asserts a value absent from premise."""
    # premise says 1944; hypothesis says 1960 -> value check fires
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie was first performed in 1960."
    score = entails(premise, hypothesis)
    assert score == 0.0, (
        f"Value-sensitive gate should return 0.0 when year is wrong, got {score}"
    )


def test_entailment_gate_passes_on_correct_value():
    """entails must return a positive score when the correct value is present."""
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie first performance was in 1944."
    score = entails(premise, hypothesis)
    assert score > 0.3, (
        f"Entailment should pass (>tau) when year matches, got {score}"
    )


def test_grounding_run_has_grading_reference_id():
    """Every GroundingRun from ground_response must carry a non-None grading_reference_id."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    run = ground_response(
        "Q?",
        "Tennessee Williams wrote The Glass Menagerie.",
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    assert run.grading_reference_id is not None


def test_fabricated_claims_have_empty_grounding_path():
    """FABRICATED claims must have an empty grounding_path (no edges, no nodes)."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    records = run_cascade(
        "Q?",
        "The Glass Menagerie had its world premiere in New York in 1960.",
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    fabricated = [c for c in records if c.status == ClaimStatus.FABRICATED]
    assert fabricated, "Expected at least one FABRICATED claim"
    for c in fabricated:
        assert not c.grounding_path.edges, "FABRICATED claim must have no path edges"
        assert not c.grounding_path.node_ids, "FABRICATED claim must have no path nodes"


def test_retrieved_direct_triple_has_single_edge_path():
    """RETRIEVED/DIRECT_TRIPLE claims must have a single-edge grounding path."""
    snapshot = _load_snapshot()
    ref = _make_glass_menagerie_ref(snapshot)
    records = run_cascade(
        "Who wrote it?",
        "Tennessee Williams wrote The Glass Menagerie.",
        ref,
        active_perturbations=[],
        config=_DEFAULT_CONFIG,
    )
    direct = [c for c in records if c.support_source == SupportSource.DIRECT_TRIPLE]
    assert direct, "Expected at least one DIRECT_TRIPLE claim"
    for c in direct:
        assert len(c.grounding_path.edges) == 1, (
            f"DIRECT_TRIPLE must have exactly 1 path edge, got {len(c.grounding_path.edges)}"
        )
        assert c.grounding_path.edges[0].traversed_forward is True


def test_active_perturbations_recorded_on_claims():
    """active_perturbations is recorded on each claim but does not change grading."""
    snapshot = _load_snapshot()
    ref = _make_pelevin_ref(snapshot)
    perturbs = ["pert-text-q105485274"]
    records = run_cascade(
        "Q?",
        "Blue Lantern and DTP were both written by Pelevin.",
        ref,
        active_perturbations=perturbs,
        config=_DEFAULT_CONFIG,
    )
    for c in records:
        assert c.active_perturbations == perturbs, (
            "active_perturbations must be recorded on claims as-is"
        )
