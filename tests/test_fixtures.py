"""Light tests for the Chopin mock fixtures + diagnostics aggregation.

Mock-only, offline, deterministic. Validates the fixtures against the schema and
checks the RunSet aggregation is stable.
"""
from __future__ import annotations

from ivg_kg.diagnostics import aggregate_runset
from ivg_kg.mock import fixtures as fx
from ivg_kg.schema import (
    AnswerDiagnostics,
    ClaimStatus,
    Condition,
    GroundingRun,
    SupportSource,
)


def test_mock_run_validates_and_spans_all_statuses():
    run = fx.mock_grounding_run()
    assert isinstance(run, GroundingRun)
    assert run.condition == Condition.FULL
    assert run.error_rates == {"text-nli": 0.06, "structure-path": 0.09}
    statuses = {c.status for c in run.claims}
    assert statuses == {
        ClaimStatus.RETRIEVED,
        ClaimStatus.REASONED_SUPPORTABLE,
        ClaimStatus.FABRICATED,
    }
    # every claim carries a claim_key (needed for RunSet alignment)
    assert all(c.claim_key for c in run.claims)


def test_both_supportable_variants_and_value_mismatch_present():
    run = fx.mock_grounding_run()
    supportable = [c for c in run.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE]
    assert any(c.spurious_path for c in supportable), "need a flagged spurious path"
    assert any(not c.spurious_path for c in supportable), "need a genuine path"
    spur = next(c for c in supportable if c.spurious_path)
    assert spur.spurious_reason  # has a reason
    # the fabricated claim is a value mismatch (asserts 17 June; reference holds 15 April)
    fab = next(c for c in run.claims if c.status == ClaimStatus.FABRICATED)
    assert fx.DOB_FALSE in fab.text and fab.support_source == SupportSource.NONE


def test_subgraph_elements_have_literal_node_and_referential_integrity():
    els = fx.mock_subgraph_elements()
    nodes = {e["data"]["id"] for e in els if "source" not in e["data"]}
    literals = [e for e in els if e["data"].get("kind") == "literal"]
    assert literals, "expected a distinctly-typed literal node (the date of birth)"
    assert any("15 April 1771" in e["data"]["id"] for e in literals)
    for e in els:
        if "source" in e["data"]:
            assert e["data"]["source"] in nodes and e["data"]["target"] in nodes


def test_build_runset_shapes():
    for n in fx.N_CHOICES:
        runs = fx.build_runset(n)
        conds = {r.condition for r in runs}
        assert conds == {
            Condition.FULL,
            Condition.KNOWLEDGE_ABSENT,
            Condition.CONTENT_ABSENT,
        }
        # n draws per condition
        for cond in conds:
            assert sum(1 for r in runs if r.condition == cond) == n
        # all draws validate (pydantic) and carry sample_index
        assert all(isinstance(r, GroundingRun) for r in runs)


def test_runset_clamped():
    assert len(fx.build_runset(0)) == len(fx.build_runset(1))  # clamped to >=1
    assert len({r.condition for r in fx.build_runset(50)}) == 3  # clamped to <=20, still 3 conds


def test_answer_diagnostics_stable_and_well_formed():
    d1 = fx.mock_answer_diagnostics(20)
    d2 = fx.mock_answer_diagnostics(20)
    assert isinstance(d1, AnswerDiagnostics)
    assert d1.model_dump() == d2.model_dump(), "aggregation must be deterministic/stable"
    assert d1.n_generations == 20
    assert len(d1.claim_diagnostics) == 6
    assert 0.0 <= d1.fabrication_rate <= 1.0
    assert abs(sum(d1.status_distribution.values()) - 1.0) < 1e-6


def test_n_selector_changes_distribution():
    d5 = fx.mock_answer_diagnostics(5)
    d20 = fx.mock_answer_diagnostics(20)
    # the N selector must do something: the distribution shifts between N=5 and N=20
    assert d5.status_distribution != d20.status_distribution


def test_aggregate_direct_runset_matches_helper():
    runs = fx.build_runset(10)
    assert aggregate_runset(runs).model_dump() == fx.mock_answer_diagnostics(10).model_dump()
