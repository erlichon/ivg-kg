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


def test_subgraph_elements_referential_integrity_and_date_is_a_gap():
    els = fx.mock_subgraph_elements()
    nodes = {e["data"]["id"] for e in els if "source" not in e["data"]}
    # the date is a GAP at baseline -> no literal date node yet
    assert not any(e["data"].get("kind") == "literal" for e in els)
    for e in els:
        if "source" in e["data"]:
            assert e["data"]["source"] in nodes and e["data"]["target"] in nodes
    # adding the date (generation+verification) introduces the distinct literal node
    edits = [{"op": "add", "kind": "triplet", "scope": "both",
              "subject": fx.NCHOPIN, "relation": "date of birth", "value": "15 April 1771"}]
    added = fx.editable_elements(edits)
    literals = [e for e in added if e["data"].get("kind") == "literal"]
    assert literals and any("15 April 1771" in e["data"]["id"] for e in literals)


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


# --- scoped KG edits (gen-only vs gen+verification) ------------------------
def _rm(tid, scope):
    return {"op": "remove", "kind": "triplet", "scope": scope, "id": tid}


def _add_date(scope):
    return {"op": "add", "kind": "triplet", "scope": scope,
            "subject": fx.NCHOPIN, "relation": "date of birth", "value": "15 April 1771"}


def test_baseline_and_structure_removal():
    # baseline: 5 grounded (c3 = date is a gap), no edits
    assert fx.grounded_count([]) == 5
    # remove the father triple (P22) generation+verification -> c1 and c5 fabricate
    s = fx.statuses_for_graph([_rm("P22", "both")])
    assert s["c1"].value == "fabricated" and s["c5"].value == "fabricated"
    assert s["c2"].value != "fabricated"  # P19 still present
    # the withheld base triple is listed for re-add; its edge is tagged ver_only on a
    # generation-only removal (still in the verifier's reference)
    assert [t["id"] for t in fx.removed_triples([_rm("P22", "gen")])] == ["P22"]
    edges = [e for e in fx.editable_elements([_rm("P22", "gen")]) if "source" in e["data"]]
    p22 = next(e for e in edges if e["data"].get("property_id") == "P22")
    assert p22["data"].get("scope_state") == "ver_only"


def test_scope_distinguishes_generation_only_from_verification():
    # generation-only ADD of the date: model states it, but the verifier cannot
    # confirm it -> c3 stays fabricated (unverifiable); no repair.
    gen = fx.statuses_with_reasons([_add_date("gen")])
    assert gen["c3"][0].value == "fabricated" and "unverifiable" in gen["c3"][1]
    assert fx.repair_result([_add_date("gen")]).repair_leverage == 0
    # generation+verification ADD: grading uses the edited reference -> c3 grounds (+1)
    both = fx.statuses_for_graph([_add_date("both")])
    assert both["c3"].value == "retrieved"
    rr = fx.repair_result([_add_date("both")])
    assert isinstance(rr, RepairResult)
    assert rr.repair_leverage == 1 and rr.repaired_claim_ids == ["c3"]
    # generation-only REMOVE is absence-induced (verifier retains the truth)
    assert "absence-induced" in fx.statuses_with_reasons([_rm("P19", "gen")])["c2"][1]


def test_entity_content_removal_and_add():
    # removing an entity's content (both) clears its description but keeps the node + triplets
    cc = [{"op": "remove", "kind": "content", "scope": "both", "id": fx.NCHOPIN}]
    els = fx.editable_elements(cc)
    nic = next(e for e in els if e["data"].get("id") == fx.NCHOPIN)
    assert nic["data"].get("content_state") == "both" and "description" not in nic["data"]
    assert any(e["data"].get("property_id") == "P19" for e in els)  # triplets intact
    # adding an entity (optional description) creates a new node
    add = [{"op": "add", "kind": "entity", "scope": "both", "id": "new:Q-x",
            "label": "Test Entity", "description": "a mock entity"}]
    assert any(e["data"].get("id") == "new:Q-x" for e in fx.editable_elements(add))
