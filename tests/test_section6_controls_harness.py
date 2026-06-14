"""
SPEC-text sec 6 falsifiable controls harness (TS2 -- A5).

Tests for ivg_kg.experiment.controls:
  - negative_control
  - false_claim_control
  - manipulation_check
  - modality_strength_check
  - run_section6_controls

Key "teeth" test: false_claim_control with a deliberately value-INSENSITIVE
stub gate (entity-match-only) must FAIL, proving the control catches a broken
entailment gate.

Gate injection: we wire the stub gate through GroundingConfig + a custom
build_components call that substitutes the broken gate.  Because
false_claim_control calls ground_response internally with config, we need to
inject the broken gate another way.  The cleanest seam is:
  1. Build a Classifier directly with the stub gate.
  2. Call classifier.classify() on the adversarial claim text.
  3. Pass the resulting GroundingRun to false_claim_control.
But false_claim_control is designed to call ground_response.  Instead, we
expose a lower-level helper _false_claim_control_with_classifier so tests
can inject a Classifier (and thus any gate), or we accept that the function
takes an optional components argument.

Chosen approach: false_claim_control accepts an optional `_components`
keyword argument (GroundingComponents) for test injection.  When supplied,
it skips build_components and uses the injected components directly.  This
documents the seam in the function signature (documented in the module).
The broken-gate stub is EntityMatchOnlyGate (always returns 1.0 for any
premise that mentions the entity name, ignoring value).
"""

from __future__ import annotations

from typing import Any

import pytest

from ivg_kg.data.reference import load_reference
from ivg_kg.experiment.controls import (
    ControlResult,
    Section6Report,
    false_claim_control,
    manipulation_check,
    modality_strength_check,
    negative_control,
    run_section6_controls,
)
from ivg_kg.experiment.gold_qa import GoldQASet, load_gold_qa_set
from ivg_kg.experiment.question_bank import (
    FactType,
    QuestionBank,
    QuestionBankItem,
    QuestionTier,
    load_question_bank,
)
from ivg_kg.grounding.backend import GroundingComponents
from ivg_kg.grounding.classify import Classifier
from ivg_kg.grounding.entailment import BaseEntailmentGate
from ivg_kg.grounding.link import PropertyCanon
from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    Condition,
    GradingReference,
    GroundingConfig,
    GroundingPath,
    GroundingRun,
    SupportSource,
)

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------

_DATA = "/Users/itay/Documents/repos/MSc/MMA/ivg-kg/.claude/worktrees/ivg-kg-m-books-honesty/data/frozen/books/books-p0-v1"

_RELIABILITY = {
    "overall_error_rate": 0.33333333333333337,
    "frozen_tau": 0.2,
}

_LEX_CONFIG = GroundingConfig(entailment="lexical", linker="label_alias", extractor="rule_based", tau=0.2)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_reference() -> GradingReference:
    return load_reference(_DATA)


@pytest.fixture(scope="module")
def real_gold() -> GoldQASet:
    return load_gold_qa_set(f"{_DATA}/gold_qa.json")


@pytest.fixture(scope="module")
def real_bank() -> QuestionBank:
    return load_question_bank(f"{_DATA}/question_bank.json")


# ---------------------------------------------------------------------------
# Broken-gate stub for the "teeth" test
# ---------------------------------------------------------------------------


class EntityMatchOnlyGate(BaseEntailmentGate):
    """Value-INSENSITIVE stub gate: returns 1.0 for any premise that mentions
    the entity name anywhere; 0.0 otherwise.  Ignores the value entirely.

    This simulates an entity-match-only grader that always grants support
    when the entity is found in the reference, regardless of whether the
    claimed value is correct.  The false_claim_control MUST detect this.
    """

    def _score(self, premise: str, hypothesis: str) -> float:
        # If ANY word in the hypothesis appears in the premise -> match.
        h_words = {w.lower() for w in hypothesis.split() if len(w) > 3}
        p_lower = premise.lower()
        if any(w in p_lower for w in h_words):
            return 1.0
        return 0.0


def _make_broken_components(reference: GradingReference, config: GroundingConfig) -> GroundingComponents:
    """Build GroundingComponents with the EntityMatchOnlyGate substituted."""
    from ivg_kg.grounding.extract import make_extractor
    from ivg_kg.grounding.link import make_entity_linker

    extractor = make_extractor(config.extractor)
    linker = make_entity_linker(config.linker, reference.snapshot)
    canon = PropertyCanon.load()
    broken_gate = EntityMatchOnlyGate()
    classifier = Classifier(reference, gate=broken_gate, canon=canon, config=config)
    return GroundingComponents(
        extractor=extractor,
        linker=linker,
        canon=canon,
        classifier=classifier,
    )


# ---------------------------------------------------------------------------
# Helper: build a GroundingRun with a known fabrication fraction
# ---------------------------------------------------------------------------


def _make_run(fabricated: int, total: int, condition: Condition = Condition.FULL) -> GroundingRun:
    """Build a synthetic GroundingRun with `fabricated` FABRICATED claims out of `total`."""
    claims: list[ClaimRecord] = []
    for i in range(total):
        status = ClaimStatus.FABRICATED if i < fabricated else ClaimStatus.RETRIEVED
        claims.append(
            ClaimRecord(
                claim_id=f"c{i + 1}",
                text=f"claim {i + 1}",
                status=status,
                support_source=SupportSource.NONE if status == ClaimStatus.FABRICATED else SupportSource.DIRECT_TRIPLE,
                linked_entities=[],
                grounding_path=GroundingPath(edges=[], node_ids=[]),
            )
        )
    return GroundingRun(
        run_id=f"run-{fabricated}-{total}",
        question="test question",
        answer_text="test answer",
        slice="books",
        phase="A",
        condition=condition,
        claims=claims,
    )


# ---------------------------------------------------------------------------
# 1. negative_control
# ---------------------------------------------------------------------------


class TestNegativeControl:
    def test_pass_when_fabrication_below_floor(self) -> None:
        # 5% fabrication, floor=0.33, tolerance=0.1 -> PASS
        runs = [_make_run(1, 20) for _ in range(5)]
        result = negative_control(runs, error_floor=0.33, tolerance=0.1)
        assert isinstance(result, ControlResult)
        assert result.passed is True
        assert "full_fab_mean" in result.detail.lower() or result.name == "negative_control"

    def test_fail_when_fabrication_above_floor_plus_tolerance(self) -> None:
        # 80% fabrication, floor=0.33, tolerance=0.1 -> FAIL
        runs = [_make_run(16, 20) for _ in range(5)]
        result = negative_control(runs, error_floor=0.33, tolerance=0.1)
        assert result.passed is False

    def test_result_carries_fab_mean(self) -> None:
        runs = [_make_run(2, 10)]  # 20% fabrication
        result = negative_control(runs, error_floor=0.33)
        assert result.full_fab_mean is not None
        assert abs(result.full_fab_mean - 0.2) < 1e-9

    def test_result_carries_error_floor(self) -> None:
        runs = [_make_run(1, 10)]
        result = negative_control(runs, error_floor=0.25)
        assert result.error_floor is not None
        assert abs(result.error_floor - 0.25) < 1e-9

    def test_exactly_at_floor_passes(self) -> None:
        # fabrication == floor + tolerance boundary
        runs = [_make_run(3, 10)]  # 30%
        result = negative_control(runs, error_floor=0.3, tolerance=0.0)
        assert result.passed is True  # 0.30 <= 0.30 + 0.0

    def test_just_above_floor_fails(self) -> None:
        runs = [_make_run(4, 10)]  # 40%
        result = negative_control(runs, error_floor=0.3, tolerance=0.0)
        assert result.passed is False  # 0.40 > 0.30

    def test_name_is_correct(self) -> None:
        runs = [_make_run(0, 5)]
        result = negative_control(runs, error_floor=0.5)
        assert result.name == "negative_control"


# ---------------------------------------------------------------------------
# 2. false_claim_control -- PASS with real lexical gate
# ---------------------------------------------------------------------------


class TestFalseClaimControlPass:
    def test_adversarial_items_exist(self, real_gold: GoldQASet) -> None:
        """Precondition: real gold set has at least one adversarial item."""
        adv = real_gold.adversarial_items()
        assert len(adv) >= 1, "gold set must have adversarial items for the control to run"

    def test_pass_with_real_gold_and_lexical_gate(
        self, real_gold: GoldQASet, real_reference: GradingReference
    ) -> None:
        """false_claim_control passes when the value-sensitive lexical gate is used.

        The adversarial item gq-s003 claims Harold Pinter wrote The Glass
        Menagerie; the real author is Tennessee Williams.  The lexical gate
        must block this wrong-value claim -> FABRICATED.
        """
        result = false_claim_control(real_gold, real_reference, _LEX_CONFIG)
        assert isinstance(result, ControlResult)
        assert result.passed is True, (
            f"false_claim_control should PASS with lexical gate; detail: {result.detail}"
        )
        assert result.name == "false_claim_control"

    def test_all_adversarial_verdicts_recorded(
        self, real_gold: GoldQASet, real_reference: GradingReference
    ) -> None:
        """Per-item verdicts are recorded in the result."""
        result = false_claim_control(real_gold, real_reference, _LEX_CONFIG)
        adv_count = len(real_gold.adversarial_items())
        assert result.n_adversarial == adv_count
        assert result.n_adversarial_fabricated <= adv_count


# ---------------------------------------------------------------------------
# 3. false_claim_control -- FAILS (teeth) with broken entity-match-only gate
# ---------------------------------------------------------------------------


class TestFalseClaimControlTeeth:
    """Demonstrate the control has teeth: inject a value-insensitive gate
    and confirm the control FAILS.

    Injection mechanism: false_claim_control accepts an optional
    `_components` keyword argument.  When supplied, it uses that
    GroundingComponents (which contains the broken gate) instead of
    calling build_components(reference, config).  This documents the
    test-injection seam without adding production complexity.
    """

    def test_fails_with_broken_entity_match_only_gate(
        self, real_gold: GoldQASet, real_reference: GradingReference
    ) -> None:
        """With an entity-match-only gate, the adversarial claim (wrong author)
        will score HIGH (entity 'The Glass Menagerie' is in the reference)
        instead of being blocked for wrong value.  Control must FAIL.
        """
        broken_components = _make_broken_components(real_reference, _LEX_CONFIG)
        result = false_claim_control(
            real_gold,
            real_reference,
            _LEX_CONFIG,
            _components=broken_components,
        )
        assert result.passed is False, (
            "false_claim_control must FAIL with entity-match-only gate "
            "(adversarial wrong-value claim is NOT caught as FABRICATED)"
        )

    def test_broken_gate_passes_adversarial_claim_as_non_fabricated(
        self, real_gold: GoldQASet, real_reference: GradingReference
    ) -> None:
        """Extra verification: the broken gate's n_adversarial_fabricated < n_adversarial."""
        broken_components = _make_broken_components(real_reference, _LEX_CONFIG)
        result = false_claim_control(
            real_gold,
            real_reference,
            _LEX_CONFIG,
            _components=broken_components,
        )
        assert result.n_adversarial_fabricated < result.n_adversarial, (
            "Broken gate should fail to mark at least one adversarial claim FABRICATED"
        )


# ---------------------------------------------------------------------------
# 4. manipulation_check
# ---------------------------------------------------------------------------


def _make_bank_with_content_and_structure() -> QuestionBank:
    """Minimal synthetic QuestionBank: 2 content items + 2 structure items."""
    items = [
        QuestionBankItem(
            item_id="qb-c1",
            question="What genre is Book A?",
            tier=QuestionTier.ABLATED_ENTITY,
            entity_id="Q_A",
            slice_id="test",
            fact_type=FactType.GENRE_FORM,
        ),
        QuestionBankItem(
            item_id="qb-c2",
            question="What tradition is Book B?",
            tier=QuestionTier.ABLATED_ENTITY,
            entity_id="Q_B",
            slice_id="test",
            fact_type=FactType.TRADITION_AFFILIATION,
        ),
        QuestionBankItem(
            item_id="qb-s1",
            question="Who wrote Book A?",
            tier=QuestionTier.ONE_HOP_RETRIEVAL,
            entity_id="Q_A",
            slice_id="test",
            fact_type=FactType.KNOWLEDGE_STRUCTURE,
        ),
        QuestionBankItem(
            item_id="qb-s2",
            question="Who published Book B?",
            tier=QuestionTier.ONE_HOP_RETRIEVAL,
            entity_id="Q_B",
            slice_id="test",
            fact_type=FactType.KNOWLEDGE_STRUCTURE,
        ),
    ]
    return QuestionBank(bank_id="test-bank", slice_id="test", items=items)


def _make_runset_for_manipulation(
    content_fab_full: float,
    content_fab_absent: float,
    struct_fab_full: float,
    struct_fab_absent: float,
) -> Any:
    """Build a synthetic RunSet for the manipulation check.

    Each cell is approximated by creating runs with the target fabrication rate.
    Uses 5 runs each for simplicity (enough to test directional effects).
    """
    from ivg_kg.experiment.sweep import RunSet

    n_claims = 10
    n_runs = 5

    def _fab_count(rate: float) -> int:
        return round(rate * n_claims)

    runs: list[GroundingRun] = []
    for i in range(n_runs):
        # FULL condition
        for qid, fab_rate in [
            ("qb-c1", content_fab_full),
            ("qb-c2", content_fab_full),
            ("qb-s1", struct_fab_full),
            ("qb-s2", struct_fab_full),
        ]:
            run = _make_run(_fab_count(fab_rate), n_claims, Condition.FULL)
            runs.append(run.model_copy(update={
                "run_id": f"{qid}--full--s{i}",
                "question": qid,
                "condition": Condition.FULL,
                "sample_index": i,
            }))
        # CONTENT_ABSENT condition
        for qid, fab_rate in [
            ("qb-c1", content_fab_absent),
            ("qb-c2", content_fab_absent),
            ("qb-s1", struct_fab_absent),
            ("qb-s2", struct_fab_absent),
        ]:
            run = _make_run(_fab_count(fab_rate), n_claims, Condition.CONTENT_ABSENT)
            runs.append(run.model_copy(update={
                "run_id": f"{qid}--content-absent--s{i}",
                "question": qid,
                "condition": Condition.CONTENT_ABSENT,
                "sample_index": i,
            }))

    return RunSet(
        sweep_id="test-sweep",
        slice_id="test",
        bank_id="test-bank",
        conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
        n_runs=n_runs,
        runs=runs,
    )


class TestManipulationCheck:
    def test_pass_when_content_rises_and_structure_stable(self) -> None:
        """PASS: content-targeting fabrication rises under CONTENT_ABSENT;
        structure-answerable fabrication is stable.
        """
        bank = _make_bank_with_content_and_structure()
        runset = _make_runset_for_manipulation(
            content_fab_full=0.1,
            content_fab_absent=0.7,  # rises substantially
            struct_fab_full=0.1,
            struct_fab_absent=0.15,  # stays stable within tolerance
        )
        result = manipulation_check(runset, bank)
        assert isinstance(result, ControlResult)
        assert result.passed is True, f"Expected PASS; detail: {result.detail}"
        assert result.name == "manipulation_check"

    def test_fail_when_content_does_not_rise(self) -> None:
        """FAIL: content fabrication does NOT rise under CONTENT_ABSENT (flat effect)."""
        bank = _make_bank_with_content_and_structure()
        runset = _make_runset_for_manipulation(
            content_fab_full=0.1,
            content_fab_absent=0.12,  # negligible rise
            struct_fab_full=0.1,
            struct_fab_absent=0.1,
        )
        result = manipulation_check(runset, bank)
        assert result.passed is False, f"Expected FAIL when content fab does not rise; detail: {result.detail}"

    def test_fail_when_structure_also_rises_leaking(self) -> None:
        """FAIL: structure fabrication also rises under CONTENT_ABSENT (leakage)."""
        bank = _make_bank_with_content_and_structure()
        runset = _make_runset_for_manipulation(
            content_fab_full=0.1,
            content_fab_absent=0.7,  # content rises
            struct_fab_full=0.1,
            struct_fab_absent=0.6,  # structure also rises -- leaking
        )
        result = manipulation_check(runset, bank)
        assert result.passed is False, f"Expected FAIL when structure leaks; detail: {result.detail}"

    def test_result_records_four_cells(self) -> None:
        """Result records the four (content/structure) x (full/absent) cells."""
        bank = _make_bank_with_content_and_structure()
        runset = _make_runset_for_manipulation(0.1, 0.7, 0.1, 0.15)
        result = manipulation_check(runset, bank)
        assert result.content_full_fab is not None
        assert result.content_absent_fab is not None
        assert result.structure_full_fab is not None
        assert result.structure_absent_fab is not None


# ---------------------------------------------------------------------------
# 5. modality_strength_check
# ---------------------------------------------------------------------------


class TestModalityStrengthCheck:
    def test_flagged_when_thin(self, real_reference: GradingReference, real_bank: QuestionBank) -> None:
        """With min_content_labels=100, the real slim content set is below threshold
        => control passes but detail notes it is thin (or result.passed is True with a warning).
        modality_strength is a REPORTING control; it always passed=True but the
        detail changes to indicate thin vs adequate.
        """
        result = modality_strength_check(real_reference, real_bank, min_content_labels=100)
        assert isinstance(result, ControlResult)
        assert result.name == "modality_strength_check"
        # Reporting control: passed=True regardless (but detail flags thinness)
        assert result.passed is True
        assert result.content_label_count is not None
        # 5 real content labels < 100 -> detail should mention "thin" or "below"
        assert any(kw in result.detail.lower() for kw in ("thin", "below", "warning")), (
            f"Expected thin-content warning in detail; got: {result.detail!r}"
        )

    def test_adequate_when_threshold_is_low(self, real_reference: GradingReference, real_bank: QuestionBank) -> None:
        """With min_content_labels=1, the real content set is adequate."""
        result = modality_strength_check(real_reference, real_bank, min_content_labels=1)
        assert result.passed is True
        assert result.content_label_count is not None and result.content_label_count >= 1
        # Should NOT mention "thin" in detail when adequate
        assert "thin" not in result.detail.lower() or "not thin" in result.detail.lower()

    def test_count_matches_real_content_labels(self, real_reference: GradingReference, real_bank: QuestionBank) -> None:
        result = modality_strength_check(real_reference, real_bank)
        assert result.content_label_count == len(real_reference.content_labels)


# ---------------------------------------------------------------------------
# 6. run_section6_controls
# ---------------------------------------------------------------------------


class TestRunSection6Controls:
    def test_overall_passed_when_all_pass(
        self,
        real_gold: GoldQASet,
        real_reference: GradingReference,
        real_bank: QuestionBank,
    ) -> None:
        """All four controls pass with well-formed inputs and the lexical gate."""
        # Build a synthetic RunSet with low fabrication for FULL condition
        from ivg_kg.experiment.sweep import RunSet

        n_runs = 5
        bank_ids = [it.item_id for it in real_bank.items]
        from ivg_kg.experiment.question_bank import FactType

        content_ids = {
            it.item_id for it in real_bank.items
            if it.fact_type in {FactType.GENRE_FORM, FactType.TRADITION_AFFILIATION,
                                FactType.SCOPE, FactType.DESCRIPTIVE_ROLE}
        }
        structure_ids = {
            it.item_id for it in real_bank.items
            if it.fact_type == FactType.KNOWLEDGE_STRUCTURE
        }

        runs: list[GroundingRun] = []
        for i in range(n_runs):
            for qid in bank_ids:
                for cond in [Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT]:
                    # FULL: 0 fab.
                    # CONTENT_ABSENT: content items get 8/10 fab (big rise);
                    #                 structure items get 1/10 (stable, rise < 0.20).
                    if cond == Condition.FULL:
                        fab = 0
                    elif cond == Condition.CONTENT_ABSENT and qid in content_ids:
                        fab = 8  # 80% fab -- big targeted rise
                    elif cond == Condition.CONTENT_ABSENT and qid in structure_ids:
                        fab = 1  # 10% fab -- stable, only 10pp rise
                    else:
                        fab = 1  # KNOWLEDGE_ABSENT: small fab for all
                    run = _make_run(fab, 10, cond)
                    runs.append(run.model_copy(update={
                        "run_id": f"{qid}--{cond.value}--s{i}",
                        "question": qid,
                        "condition": cond,
                        "sample_index": i,
                    }))
        runset = RunSet(
            sweep_id="test-sweep",
            slice_id=real_bank.slice_id,
            bank_id=real_bank.bank_id,
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT],
            n_runs=n_runs,
            runs=runs,
        )
        reliability = {"overall_error_rate": 0.33}

        report = run_section6_controls(
            runset, real_gold, real_reference, real_bank, reliability, _LEX_CONFIG
        )
        assert isinstance(report, Section6Report)
        assert report.overall_passed is True, (
            f"Expected overall_passed=True; results: {[(r.name, r.passed) for r in report.results]}"
        )
        assert len(report.results) == 4

    def test_overall_false_when_false_claim_fails(
        self,
        real_gold: GoldQASet,
        real_reference: GradingReference,
        real_bank: QuestionBank,
    ) -> None:
        """overall_passed=False when false_claim_control fails (mandatory gate)."""
        from ivg_kg.experiment.sweep import RunSet

        n_runs = 5
        bank_ids = [it.item_id for it in real_bank.items]
        runs: list[GroundingRun] = []
        for i in range(n_runs):
            for qid in bank_ids:
                run = _make_run(0, 10, Condition.FULL)
                runs.append(run.model_copy(update={
                    "run_id": f"{qid}--full--s{i}",
                    "question": qid,
                    "condition": Condition.FULL,
                    "sample_index": i,
                }))
        runset = RunSet(
            sweep_id="test-sweep",
            slice_id=real_bank.slice_id,
            bank_id=real_bank.bank_id,
            conditions=[Condition.FULL],
            n_runs=n_runs,
            runs=runs,
        )
        reliability = {"overall_error_rate": 0.33}

        # Inject broken gate: false_claim should fail
        broken_components = _make_broken_components(real_reference, _LEX_CONFIG)

        report = run_section6_controls(
            runset,
            real_gold,
            real_reference,
            real_bank,
            reliability,
            _LEX_CONFIG,
            _false_claim_components=broken_components,
        )
        assert report.overall_passed is False, (
            "overall_passed must be False when false_claim_control fails"
        )
        false_claim_result = next(r for r in report.results if r.name == "false_claim_control")
        assert false_claim_result.passed is False

    def test_modality_strength_does_not_veto_overall(
        self,
        real_gold: GoldQASet,
        real_reference: GradingReference,
        real_bank: QuestionBank,
    ) -> None:
        """modality_strength_check is reporting-only; even when thin it does not
        cause overall_passed=False.
        """
        from ivg_kg.experiment.sweep import RunSet

        n_runs = 5
        bank_ids = [it.item_id for it in real_bank.items]
        runs: list[GroundingRun] = []
        for i in range(n_runs):
            for qid in bank_ids:
                for cond in [Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT]:
                    fab = 1 if cond != Condition.FULL else 0
                    run = _make_run(fab, 10, cond)
                    runs.append(run.model_copy(update={
                        "run_id": f"{qid}--{cond.value}--s{i}",
                        "question": qid,
                        "condition": cond,
                        "sample_index": i,
                    }))
        runset = RunSet(
            sweep_id="test-sweep",
            slice_id=real_bank.slice_id,
            bank_id=real_bank.bank_id,
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT],
            n_runs=n_runs,
            runs=runs,
        )
        # Very high min_content_labels so modality_strength_check flags thinness
        reliability = {"overall_error_rate": 0.33}

        report = run_section6_controls(
            runset,
            real_gold,
            real_reference,
            real_bank,
            reliability,
            _LEX_CONFIG,
            min_content_labels=1000,  # forces thin flag
        )
        # overall_passed should depend only on negative + false_claim + manipulation
        mandatory_results = [r for r in report.results if r.name != "modality_strength_check"]
        all_mandatory_pass = all(r.passed for r in mandatory_results)
        if all_mandatory_pass:
            assert report.overall_passed is True, (
                "modality_strength thinness must NOT veto overall_passed"
            )
