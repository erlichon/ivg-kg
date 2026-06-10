"""Light tests for the Chopin mock fixtures + single-/multi-run diagnostics.

Mock-only, offline, deterministic. Validates the fixtures against the schema and
checks the §4.8 aggregation (single-run summary, multi-run mean+/-SE,
support-frequency, repair-leverage) is stable.
"""
from __future__ import annotations

from ivg_kg.diagnostics import aggregate_runset, single_run_summary
from ivg_kg.mock import fixtures as fx
from ivg_kg.schema import (
    AnswerDiagnostics,
    ClaimStatus,
    Condition,
    GroundingRun,
    RepairResult,
    SingleRunStatusSummary,
    StatusMeanSE,
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
    # grounded claims carry a support path; fabricated ones do not
    for c in run.claims:
        if c.status == ClaimStatus.FABRICATED:
            assert not c.grounding_path.node_ids and not c.grounding_path.edges
        else:
            assert c.grounding_path.node_ids


def test_both_supportable_variants_and_value_mismatch_present():
    run = fx.mock_grounding_run()
    supportable = [c for c in run.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE]
    assert any(c.spurious_path for c in supportable), "need a flagged spurious path"
    assert any(not c.spurious_path for c in supportable), "need a genuine path"
    spur = next(c for c in supportable if c.spurious_path)
    assert spur.spurious_reason  # has a reason
    # the fabricated claim asserts the wrong date and has no support
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


# --- single-run (no SE) ----------------------------------------------------
def test_single_run_summary_no_se():
    s = fx.mock_single_run_summary()
    assert isinstance(s, SingleRunStatusSummary)
    assert sum(s.status_counts.values()) == 6
    assert abs(sum(s.status_percentages.values()) - 1.0) < 1e-9
    # 3 retrieved, 2 supportable, 1 fabricated in the displayed answer
    assert s.status_counts[ClaimStatus.FABRICATED.value] == 1


# --- multi-run (mean +/- SE, support-frequency) ----------------------------
def test_build_runset_shapes():
    for n in fx.N_CHOICES:
        runs = fx.build_runset(n)
        conds = {r.condition for r in runs}
        assert conds == {
            Condition.FULL,
            Condition.KNOWLEDGE_ABSENT,
            Condition.CONTENT_ABSENT,
        }
        for cond in conds:  # n runs per condition
            assert sum(1 for r in runs if r.condition == cond) == n
        assert all(isinstance(r, GroundingRun) for r in runs)
    # claims are NOT aligned across runs: within-run claim_ids only
    runs = fx.build_condition_runset(5, Condition.FULL)
    assert runs[0].claims[0].claim_id != runs[1].claims[0].claim_id


def test_runset_clamped():
    assert len(fx.build_runset(0)) == len(fx.build_runset(1))  # clamped to >=1
    assert len({r.condition for r in fx.build_runset(50)}) == 3  # clamped to <=20, still 3 conds


def test_multirun_diagnostics_stable_and_well_formed():
    d1 = fx.mock_answer_diagnostics(20, Condition.FULL)
    d2 = fx.mock_answer_diagnostics(20, Condition.FULL)
    assert isinstance(d1, AnswerDiagnostics)
    assert d1.model_dump() == d2.model_dump(), "aggregation must be deterministic/stable"
    assert d1.n_runs == 20
    # mean per-run fractions over the three grades sum to ~1 (claims always emitted)
    assert all(isinstance(v, StatusMeanSE) for v in d1.status_distribution.values())
    assert abs(sum(v.mean for v in d1.status_distribution.values()) - 1.0) < 1e-6
    # SE of a proportion, not the ~0.5 per-draw std
    for v in d1.status_distribution.values():
        assert 0.0 <= v.se < 0.2


def test_withhold_from_context_shifts_distribution():
    cd = fx.mock_condition_diagnostics(20)
    fab = ClaimStatus.FABRICATED.value
    full = cd[Condition.FULL.value].status_distribution[fab].mean
    content = cd[Condition.CONTENT_ABSENT.value].status_distribution[fab].mean
    knowledge = cd[Condition.KNOWLEDGE_ABSENT.value].status_distribution[fab].mean
    # withholding raises fabrication; knowledge-absence hurts most (structure withheld)
    assert content > full
    assert knowledge > content


def test_support_frequency_observational_over_kg_items():
    d = fx.mock_answer_diagnostics(20, Condition.FULL)
    sf = d.support_frequency
    assert sf, "expected a non-empty support-frequency map"
    assert all(0.0 <= v <= 1.0 for v in sf.values())
    # keys are entity ids and triplet ids "<subj>|<prop>|<obj>"
    assert any("|" in k for k in sf), "expected triplet keys"
    assert any("|" not in k for k in sf), "expected entity keys"
    # the father triple grounds c1 in almost every FULL run
    assert sf.get(f"{fx.FCHOPIN}|P22|{fx.NCHOPIN}", 0.0) > 0.8


def test_n_selector_changes_distribution():
    d5 = fx.mock_answer_diagnostics(5, Condition.FULL)
    d20 = fx.mock_answer_diagnostics(20, Condition.FULL)
    means5 = {k: v.mean for k, v in d5.status_distribution.items()}
    means20 = {k: v.mean for k, v in d20.status_distribution.items()}
    assert means5 != means20


def test_aggregate_direct_runset_matches_helper():
    runs = fx.build_condition_runset(10, Condition.FULL)
    assert aggregate_runset(runs).model_dump() == fx.mock_answer_diagnostics(10).model_dump()


def test_single_run_summary_matches_helper():
    assert single_run_summary(fx.mock_grounding_run()).model_dump() == (
        fx.mock_single_run_summary().model_dump()
    )


# --- edit-the-KG + repair-leverage -----------------------------------------
def test_graph_editor_logic():
    # full graph: 5 grounded (c3 = date fabricated until a date-of-birth triple is injected)
    assert fx.grounded_count(fx.ALL_TRIPLE_IDS, []) == 5
    # remove the father triple (P22) -> c1 (and c5, which needs P22) fabricate
    without_p22 = [t for t in fx.ALL_TRIPLE_IDS if t != "P22"]
    s = fx.statuses_for_graph(without_p22, [])
    assert s["c1"].value == "fabricated" and s["c5"].value == "fabricated"
    assert s["c2"].value != "fabricated"  # P19 still present
    # injecting an (editable) date-of-birth triple grounds the date claim c3
    inj = [{"subject": fx.NCHOPIN, "relation": "date of birth", "value": "15 April 1771"}]
    assert fx.statuses_for_graph(fx.ALL_TRIPLE_IDS, inj)["c3"].value == "retrieved"
    # editable elements: the removed triple's edge is gone; the injected edge is tagged
    edges = [e for e in fx.editable_elements(without_p22, inj) if "source" in e["data"]]
    assert "P22" not in {e["data"].get("property_id") for e in edges}
    assert any(e["data"].get("injected") == "1" for e in edges)
    assert [t["id"] for t in fx.removed_triples(without_p22)] == ["P22"]


def test_repair_leverage_counts_fabricated_to_grounded_flips():
    # baseline (original answer): only the date claim c3 is fabricated -> leverage 0
    base = fx.repair_result(fx.ALL_TRIPLE_IDS, [])
    assert isinstance(base, RepairResult)
    assert base.repair_leverage == 0
    # inject the curated date -> c3 flips fabricated->grounded -> leverage +1
    inj = [{"subject": fx.NCHOPIN, "relation": "date of birth", "value": "15 April 1771"}]
    rr = fx.repair_result(fx.ALL_TRIPLE_IDS, inj)
    assert rr.repair_leverage == 1 and rr.repaired_claim_ids == ["c3"]
