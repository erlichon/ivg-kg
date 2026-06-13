"""Tests for GR10 -- gold-QA calibration, per-modality error, reliability curve.

TDD coverage (SPEC-text 4.7 + 4.9a):
  1. evaluate_gold_set returns a CalibrationReport; n_items/n_claims correct;
     overall_error_rate in [0, 1].
  2. Per-modality error reported SEPARATELY (text vs structure ModalityError).
  3. Adversarial value-swapped negative graded FABRICATED -> counts toward
     adversarial_negative_accuracy.
  4. supportable_bucket_accuracy computed over expected==REASONED_SUPPORTABLE only.
  5. linking_coverage: out-of-slice mention lowers coverage; in-slice counts as
     covered; coverage is DISTINCT from error.
  6. Reliability curve: bins returned, each accuracy in [0, 1], counts sum to the
     number of claims that reached the gate (documented).
  7. calibrate_tau uses ONLY the calibration fold; returns a candidate; smallest
     tau on a tie.
  8. build_reliability_report freezes tau on calibration, reports on sweep;
     frozen_tau/frozen_k set; calibrated == False for entailment="lexical".
  9. Determinism: two identical evaluate_gold_set calls -> equal reports.
 10. Committed reliability_report.json (if present) loads + validates with
     calibrated == False.

All tests use the model-free lexical gate (no torch, no download, deterministic).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.experiment.calibration import (
    CalibrationReport,
    ModalityError,
    ReliabilityBin,
    build_reliability_report,
    calibrate_tau,
    evaluate_gold_set,
)
from ivg_kg.experiment.gold_qa import (
    ExpectedClaimOutcome,
    GoldFold,
    GoldQAItem,
    GoldQASet,
)
from ivg_kg.schema import (
    ClaimStatus,
    GradingReference,
    GroundingConfig,
    KGEdge,
    KGNode,
    KGSnapshot,
    Modality,
    ValueType,
)

# ---------------------------------------------------------------------------
# Fixtures: a small two-book snapshot with a shared author (enables a genuine
# 2-hop REASONED_SUPPORTABLE path) plus content labels.
# ---------------------------------------------------------------------------

# Two books by the same author Q200 ("Ada Prose"):
#   Q100 "Northwind"  --P50 author--> Q200 "Ada Prose"
#   Q101 "Southwind"  --P50 author--> Q200 "Ada Prose"
# So the 2-hop path Q100 -- Q200 -- Q101 grounds the shared-author claim.
# Q300 "Eastwind" is an out-of-slice book used to test linking coverage; it is
# NOT a node in the snapshot.


def _config(tau: float = 0.4) -> GroundingConfig:
    return GroundingConfig(
        k_hops=2,
        tau=tau,
        entailment="lexical",
        linker="label_alias",
        extractor="rule_based",
    )


def _reference() -> GradingReference:
    nodes = [
        KGNode(id="Q100", label="Northwind"),
        KGNode(id="Q101", label="Southwind"),
        KGNode(id="Q200", label="Ada Prose"),
    ]
    edges = [
        KGEdge(
            subject_id="Q100",
            property_id="P50",
            property_label="author",
            object_id="Q200",
            object_label="Ada Prose",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q101",
            property_id="P50",
            property_label="author",
            object_id="Q200",
            object_label="Ada Prose",
            value_type=ValueType.ITEM,
        ),
    ]
    snapshot = KGSnapshot(
        snapshot_id="cal-test",
        slice="books",
        domain_qid="Q100",
        nodes=nodes,
        edges=edges,
    )
    content = author_books_content_labels([("Q100", "Northwind is a memory play", "description")])
    return assemble_reference(snapshot, content)


def _gold_set() -> GoldQASet:
    """In-memory gold set: text RETRIEVED, structure SUPPORTABLE, adversarial."""
    items = [
        # CALIBRATION fold: a direct-triple structure claim (RETRIEVED).
        GoldQAItem(
            item_id="c1",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
        ),
        # CALIBRATION fold: a text content claim (RETRIEVED, text modality).
        GoldQAItem(
            item_id="c2",
            question="What kind of work is Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind is a memory play",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.TEXT,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
        ),
        # SWEEP fold: a genuine 2-hop shared-author claim (REASONED_SUPPORTABLE).
        GoldQAItem(
            item_id="s1",
            question="Do Northwind and Southwind share an author?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose Southwind author Ada Prose",
                    expected_status=ClaimStatus.REASONED_SUPPORTABLE,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.SWEEP,
        ),
        # SWEEP fold: adversarial value-swapped negative -> must grade FABRICATED.
        # In-slice entity Q100 with a wrong author value.
        GoldQAItem(
            item_id="s2",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Zebulon Falsewright",
                    expected_status=ClaimStatus.FABRICATED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=True,
            fold=GoldFold.SWEEP,
        ),
    ]
    return GoldQASet(set_id="gold-cal-test", slice_id="cal-test", items=items)


# ---------------------------------------------------------------------------
# 1. Structure + ranges
# ---------------------------------------------------------------------------


def test_evaluate_returns_report_with_counts_and_error_range() -> None:
    gold = _gold_set()
    ref = _reference()
    report = evaluate_gold_set(gold, ref, config=_config())

    assert isinstance(report, CalibrationReport)
    assert report.n_items == 4
    # one expected outcome per item here.
    assert report.n_claims == 4
    assert 0.0 <= report.overall_error_rate <= 1.0
    assert report.set_id == gold.set_id
    assert report.slice_id == gold.slice_id


# ---------------------------------------------------------------------------
# 2. Per-modality error reported separately
# ---------------------------------------------------------------------------


def test_per_modality_error_text_and_structure_separate() -> None:
    gold = _gold_set()
    report = evaluate_gold_set(gold, _reference(), config=_config())

    by_mod = {m.modality: m for m in report.per_modality_error}
    assert "text" in by_mod
    assert "structure" in by_mod
    assert isinstance(by_mod["text"], ModalityError)
    # 1 text claim (c2), 3 structure claims (c1, s1, s2).
    assert by_mod["text"].n == 1
    assert by_mod["structure"].n == 3
    for me in report.per_modality_error:
        assert 0.0 <= me.error_rate <= 1.0
        assert 0 <= me.n_correct <= me.n


# ---------------------------------------------------------------------------
# 3. Adversarial negative accuracy
# ---------------------------------------------------------------------------


def test_adversarial_negative_graded_fabricated_counts() -> None:
    gold = _gold_set()
    report = evaluate_gold_set(gold, _reference(), config=_config())
    # The single adversarial item asserts a wrong author value; the value-
    # sensitive lexical gate must NOT ground it, so it grades FABRICATED and the
    # adversarial accuracy is 1.0.
    assert report.adversarial_negative_accuracy == 1.0


def test_adversarial_accuracy_drops_when_wrongly_grounded() -> None:
    # Build an adversarial item whose claim DOES lexically match a real edge,
    # so the gate (wrongly, from the adversarial design's view) grounds it as
    # RETRIEVED rather than FABRICATED. Expected is FABRICATED -> accuracy 0.0.
    ref = _reference()
    items = [
        GoldQAItem(
            item_id="adv-bad",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.FABRICATED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=True,
            fold=GoldFold.SWEEP,
        ),
    ]
    gold = GoldQASet(set_id="adv", slice_id="cal-test", items=items)
    report = evaluate_gold_set(gold, ref, config=_config())
    assert report.adversarial_negative_accuracy == 0.0


# ---------------------------------------------------------------------------
# 4. supportable_bucket_accuracy over REASONED_SUPPORTABLE only
# ---------------------------------------------------------------------------


def test_supportable_bucket_accuracy_over_supportable_only() -> None:
    gold = _gold_set()
    report = evaluate_gold_set(gold, _reference(), config=_config())
    # Exactly one expected==REASONED_SUPPORTABLE item (s1). The 2-hop shared-
    # author path should ground it as REASONED_SUPPORTABLE -> accuracy 1.0.
    assert 0.0 <= report.supportable_bucket_accuracy <= 1.0
    assert report.supportable_bucket_accuracy == 1.0


# ---------------------------------------------------------------------------
# 5. linking_coverage distinct from error
# ---------------------------------------------------------------------------


def test_linking_coverage_out_of_slice_lowers_it() -> None:
    ref = _reference()
    # Two items: one in-slice (covered), one referencing an out-of-slice book
    # "Eastwind" (Q300 not in snapshot) that will not link -> not covered.
    items = [
        GoldQAItem(
            item_id="in",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            fold=GoldFold.CALIBRATION,
        ),
        GoldQAItem(
            item_id="out",
            question="Who wrote Eastwind?",
            entity_id="Q300",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Eastwind Qwxyz Vftgh",
                    expected_status=ClaimStatus.FABRICATED,
                    modality=Modality.STRUCTURE,
                )
            ],
            fold=GoldFold.SWEEP,
        ),
    ]
    gold = GoldQASet(set_id="cov", slice_id="cal-test", items=items)
    report = evaluate_gold_set(gold, ref, config=_config())
    # One of two claims linked -> coverage 0.5.
    assert report.linking_coverage == 0.5
    # Coverage and error can differ: the out-of-slice claim is correctly graded
    # FABRICATED (error 0 for it) yet it is uncovered.
    assert report.linking_coverage != (1.0 - report.overall_error_rate)


def test_linking_coverage_full_when_all_in_slice() -> None:
    gold = _gold_set()
    report = evaluate_gold_set(gold, _reference(), config=_config())
    # All four claims mention in-slice entities -> coverage 1.0.
    assert report.linking_coverage == 1.0


# ---------------------------------------------------------------------------
# 6. Reliability curve
# ---------------------------------------------------------------------------


def test_reliability_curve_bins_valid_and_counts_sum() -> None:
    gold = _gold_set()
    report = evaluate_gold_set(gold, _reference(), config=_config())
    assert len(report.reliability_curve) >= 1
    total = 0
    for b in report.reliability_curve:
        assert isinstance(b, ReliabilityBin)
        assert 0.0 <= b.accuracy <= 1.0
        assert b.margin_lo <= b.margin_hi
        assert b.n >= 0
        total += b.n
    # Bin counts sum to the number of claims that reached the gate (all claims
    # that produced an entailment_score, i.e. linked + scored). Here all four
    # claims reach the gate.
    assert total == report.n_claims


# ---------------------------------------------------------------------------
# 7. calibrate_tau: calibration fold only, deterministic tie-break
# ---------------------------------------------------------------------------


def test_calibrate_tau_returns_candidate_and_ignores_sweep() -> None:
    gold = _gold_set()
    ref = _reference()
    candidates = [0.1, 0.4, 0.9]
    tau = calibrate_tau(gold, ref, config=_config(), candidates=candidates)
    assert tau in candidates

    # Adding a sweep-fold item that would change the optimum if it were counted
    # must NOT change the calibrated tau (sweep fold is ignored).
    extra_sweep = GoldQAItem(
        item_id="s-extra",
        question="x",
        entity_id="Q100",
        slice_id="cal-test",
        expected_outcomes=[
            ExpectedClaimOutcome(
                claim_text="Northwind author Ada Prose",
                expected_status=ClaimStatus.FABRICATED,  # would penalise low tau
                modality=Modality.STRUCTURE,
            )
        ],
        fold=GoldFold.SWEEP,
    )
    gold2 = GoldQASet(
        set_id=gold.set_id,
        slice_id=gold.slice_id,
        items=[*gold.items, extra_sweep],
    )
    tau2 = calibrate_tau(gold2, ref, config=_config(), candidates=candidates)
    assert tau2 == tau


def test_calibrate_tau_smallest_on_tie() -> None:
    # A gold calibration fold where multiple candidate taus give the same
    # accuracy: the smallest must win.
    ref = _reference()
    # Single calibration item that grades RETRIEVED for any tau below its score;
    # use two low candidates that both yield identical (perfect) accuracy.
    items = [
        GoldQAItem(
            item_id="c",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            fold=GoldFold.CALIBRATION,
        ),
        GoldQAItem(
            item_id="s",
            question="x",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            fold=GoldFold.SWEEP,
        ),
    ]
    gold = GoldQASet(set_id="tie", slice_id="cal-test", items=items)
    # 0.1 and 0.2 both leave the RETRIEVED claim correctly grounded -> tie.
    tau = calibrate_tau(gold, ref, config=_config(), candidates=[0.2, 0.1])
    assert tau == 0.1


# ---------------------------------------------------------------------------
# 8. build_reliability_report: freeze on calibration, report on sweep
# ---------------------------------------------------------------------------


def test_build_report_freezes_tau_on_calibration_reports_on_sweep() -> None:
    gold = _gold_set()
    ref = _reference()
    candidates = [0.1, 0.4, 0.9]
    report = build_reliability_report(gold, ref, config=_config(tau=0.4), tau_candidates=candidates)
    expected_tau = calibrate_tau(gold, ref, config=_config(tau=0.4), candidates=candidates)
    assert report.frozen_tau == expected_tau
    assert report.frozen_k == 2
    assert report.calibrated is False
    assert report.gate == "lexical"
    # Reported on the sweep fold: n_items equals the number of sweep items.
    assert report.n_items == len(gold.sweep_items())


def test_build_report_without_candidates_uses_config_tau() -> None:
    gold = _gold_set()
    report = build_reliability_report(gold, _reference(), config=_config(tau=0.4))
    assert report.frozen_tau == 0.4
    assert report.n_items == len(gold.sweep_items())


# ---------------------------------------------------------------------------
# 9. Determinism
# ---------------------------------------------------------------------------


def test_evaluate_is_deterministic() -> None:
    gold = _gold_set()
    ref = _reference()
    r1 = evaluate_gold_set(gold, ref, config=_config())
    r2 = evaluate_gold_set(gold, ref, config=_config())
    assert r1.model_dump() == r2.model_dump()


# ---------------------------------------------------------------------------
# 10. Committed demo report (Part 3), if present
# ---------------------------------------------------------------------------

_REPORT_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "frozen"
    / "books"
    / "books-p0-v1"
    / "reliability_report.json"
)


@pytest.mark.skipif(not _REPORT_PATH.exists(), reason="demo report not emitted")
def test_committed_reliability_report_validates() -> None:
    raw = _REPORT_PATH.read_text(encoding="utf-8")
    report = CalibrationReport.model_validate_json(raw)
    assert report.calibrated is False
    assert report.gate == "lexical"
    # sanity: JSON round-trips and the curve is present.
    json.loads(raw)
    assert isinstance(report.reliability_curve, list)


# ---------------------------------------------------------------------------
# M4 edge tests
# ---------------------------------------------------------------------------


def test_empty_gold_set_returns_zero_metrics() -> None:
    # An empty GoldQASet must not crash and must return a report with
    # n_items==0, n_claims==0, and all 0.0 metrics.
    ref = _reference()
    gold = GoldQASet(set_id="empty", slice_id="cal-test", items=[])
    # Skip assert_complete for this synthetic empty set (no folds).
    report = evaluate_gold_set(gold, ref, config=_config())
    assert report.n_items == 0
    assert report.n_claims == 0
    assert report.overall_error_rate == 0.0
    assert report.accepted_path_multiplicity_mean == 0.0


def test_all_correct_gold_set_overall_error_rate_zero() -> None:
    # A gold set where every expected outcome matches what the verifier produces
    # must yield overall_error_rate == 0.0.
    ref = _reference()
    items = [
        GoldQAItem(
            item_id="c1",
            question="Who wrote Northwind?",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
        ),
        GoldQAItem(
            item_id="s1",
            question="x",
            entity_id="Q100",
            slice_id="cal-test",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Northwind author Ada Prose",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.SWEEP,
        ),
    ]
    gold = GoldQASet(set_id="all-correct", slice_id="cal-test", items=items)
    report = evaluate_gold_set(gold, ref, config=_config())
    assert report.overall_error_rate == 0.0


def test_accepted_path_multiplicity_mean_concrete_value() -> None:
    # The fixture has exactly ONE REASONED_SUPPORTABLE expected outcome (s1).
    # The 2-hop shared-author path Q100 -- Q200 -- Q101 is the ONLY entity path
    # between Q100 and Q101 in the fixture reference (tau=0.4 with the lexical
    # gate on the claim "Northwind author Ada Prose Southwind author Ada Prose").
    # accepted_path_multiplicity_mean must equal 1.0 (one accepted path).
    gold = _gold_set()
    ref = _reference()
    report = evaluate_gold_set(gold, ref, config=_config(tau=0.4))
    assert report.accepted_path_multiplicity_mean == 1.0
