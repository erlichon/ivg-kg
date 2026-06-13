"""Emit the committed books gold-QA set + reliability report (GR10).

SPEC-text 4.7 + 4.9a. Deterministic generator for the DEMO calibration
artifacts the UI (UI6) renders:

    data/frozen/books/books-p0-v1/gold_qa.json
    data/frozen/books/books-p0-v1/reliability_report.json

The gold set is hand-authored against the frozen books-p0-v1 snapshot and
covers both folds (calibration + sweep), every modality the books spine uses
(text + structure), a genuine 2-hop REASONED_SUPPORTABLE shared-author claim,
and a value-swapped adversarial negative (the section-6 control). Every
expected_outcome was verified to grade as written under the offline lexical
gate before being committed; the script asserts assert_complete() passes.

The reliability report is built with entailment="lexical" -- the model-free
deterministic gate -- so it carries calibrated=false / gate="lexical": HONEST
demo data, NOT a calibrated deployment number. The real deployment report uses
entailment="minicheck" (calibrated=true), produced offline with the model.

The whole path (lexical gate, label-alias linker) is deterministic, so running
this script twice produces byte-identical output files.

Usage:
    uv run python scripts/emit_calibration_report.py
"""

from __future__ import annotations

from pathlib import Path

from ivg_kg.data.graph_store import load_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.experiment.calibration import build_reliability_report
from ivg_kg.experiment.gold_qa import (
    ExpectedClaimOutcome,
    GoldFold,
    GoldQAItem,
    GoldQASet,
)
from ivg_kg.schema import ClaimStatus, GroundingConfig, Modality

_SLICE_DIR = Path(__file__).parent.parent / "data" / "frozen" / "books" / "books-p0-v1"

# Offline deterministic gate. tau=0.4 is the PRE-CALIBRATION seed used when no
# tau_candidates are supplied (the no-candidates path). When tau_candidates is
# passed to build_reliability_report, calibrate_tau sweeps those candidates on
# the CALIBRATION fold and freezes the actual operating point (0.2 on the
# books-p0-v1 fold, visible as frozen_tau:0.2 in the emitted report). The
# model-gate sweep (GR11) selects its own tau and does NOT inherit 0.4.
_CONFIG = GroundingConfig(
    k_hops=2,
    tau=0.4,
    entailment="lexical",
    linker="label_alias",
    extractor="rule_based",
)

# Candidate taus swept on the CALIBRATION fold to freeze the operating point.
_TAU_CANDIDATES = [0.2, 0.3, 0.4, 0.5, 0.6]


def build_gold_set() -> GoldQASet:
    """Author the committed books gold-QA set (both folds, all modalities)."""
    items = [
        # --- CALIBRATION fold ------------------------------------------------
        GoldQAItem(
            item_id="gq-c001",
            question="Who wrote The Glass Menagerie?",
            entity_id="Q678832",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="The Glass Menagerie author Tennessee Williams",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
            notes="direct triple Q678832 --[P50 author]--> Q134262",
        ),
        GoldQAItem(
            item_id="gq-c002",
            question="What kind of play is The Glass Menagerie?",
            entity_id="Q678832",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="The Glass Menagerie is a memory play",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.TEXT,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
            notes="text content label for Q678832",
        ),
        GoldQAItem(
            item_id="gq-c003",
            question="Who wrote Principles of Economics?",
            entity_id="Q4338113",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Principles of Economics author Carl Menger",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.CALIBRATION,
            notes="direct triple Q4338113 --[P50 author]--> Q84177",
        ),
        # --- SWEEP fold (held-out anchor; reported, never tuned) -------------
        GoldQAItem(
            item_id="gq-s001",
            question="Tell me about Pelevin's books.",
            entity_id="Q105485274",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Blue Lantern and DTP(NN) were written by Victor Pelevin",
                    expected_status=ClaimStatus.REASONED_SUPPORTABLE,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.SWEEP,
            notes=(
                "genuine 2-hop shared-author path "
                "Q105485274 --[author]--> Q246722 <--[author]-- Q105623200"
            ),
        ),
        GoldQAItem(
            item_id="gq-s002",
            question="What is Principles of Economics about?",
            entity_id="Q4338113",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="Principles of Economics concerns economics",
                    expected_status=ClaimStatus.RETRIEVED,
                    modality=Modality.TEXT,
                )
            ],
            adversarial_negative=False,
            fold=GoldFold.SWEEP,
            notes="text content label for Q4338113",
        ),
        GoldQAItem(
            item_id="gq-s003",
            question="Who wrote The Glass Menagerie?",
            entity_id="Q678832",
            slice_id="books-p0-v1",
            expected_outcomes=[
                ExpectedClaimOutcome(
                    claim_text="The Glass Menagerie author Harold Pinter",
                    expected_status=ClaimStatus.FABRICATED,
                    modality=Modality.STRUCTURE,
                )
            ],
            adversarial_negative=True,
            fold=GoldFold.SWEEP,
            notes=(
                "adversarial value-swapped negative (section-6 control): entity "
                "Q678832 IS in reference but the author value is wrong (the true "
                "author is Tennessee Williams). A value-sensitive grader must "
                "grade FABRICATED; an entity-match-only grader passes."
            ),
        ),
    ]
    gold = GoldQASet(set_id="gold-books-p0-v1", slice_id="books-p0-v1", items=items)
    gold.assert_complete()
    return gold


def build_reference():
    """Assemble the books grading reference with the content labels the gold set needs."""
    snapshot = load_snapshot(_SLICE_DIR)
    content = author_books_content_labels(
        [
            ("Q678832", "The Glass Menagerie is a memory play", "description"),
            ("Q4338113", "Principles of Economics concerns economics", "description"),
        ]
    )
    return assemble_reference(snapshot, content)


def main() -> None:
    gold = build_gold_set()
    reference = build_reference()

    # Persist the gold set (promotes the thin .stub.json to a richer committed set).
    (_SLICE_DIR / "gold_qa.json").write_text(gold.to_json() + "\n", encoding="utf-8")

    # Freeze tau on the calibration fold; report on the sweep fold.
    report = build_reliability_report(
        gold, reference, config=_CONFIG, tau_candidates=_TAU_CANDIDATES
    )
    assert report.calibrated is False  # lexical gate -> demo/uncalibrated
    assert report.gate == "lexical"

    (_SLICE_DIR / "reliability_report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    print(f"wrote {_SLICE_DIR / 'gold_qa.json'}")
    print(f"wrote {_SLICE_DIR / 'reliability_report.json'}")
    print(
        f"frozen_tau={report.frozen_tau} frozen_k={report.frozen_k} "
        f"overall_error_rate={report.overall_error_rate:.3f} "
        f"n_items={report.n_items} n_claims={report.n_claims}"
    )


if __name__ == "__main__":
    main()
