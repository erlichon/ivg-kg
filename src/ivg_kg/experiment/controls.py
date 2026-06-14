"""
SPEC-text sec 6 falsifiable controls harness (A5 / TS2).

Provides four control functions that MUST pass before trusting any M-BOOKS
result.  The false-claim control is NON-NEGOTIABLE: its absence lets a broken
entailment gate pass everything else.

Controls
--------
negative_control            -- no-ablation (FULL) mean fabrication <= error_floor + tolerance
false_claim_control         -- adversarial wrong-value claims grade FABRICATED under full context
manipulation_check          -- ablating content raises targeted fab, leaves structure stable
modality_strength_check     -- reporting; flags thin content axis

Aggregator
----------
run_section6_controls       -- runs all four; overall_passed = negative AND false_claim AND manipulation

Test-injection seam
-------------------
false_claim_control and run_section6_controls accept an optional `_components`
/ `_false_claim_components` keyword argument (GroundingComponents).  When
supplied, the function skips build_components() and uses the injected
components directly.  This allows tests to wire a broken gate (e.g.
EntityMatchOnlyGate) to verify the control has teeth.  Normal production
callers pass nothing; the seam is invisible at the call site.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ivg_kg.experiment.gold_qa import GoldQASet
from ivg_kg.experiment.question_bank import FactType, QuestionBank
from ivg_kg.experiment.sweep import RunSet
from ivg_kg.grounding.backend import GroundingComponents, _ground_with_components, build_components
from ivg_kg.schema import (
    ClaimStatus,
    Condition,
    GradingReference,
    GroundingConfig,
    GroundingRun,
)

__all__ = [
    "ControlResult",
    "Section6Report",
    "negative_control",
    "false_claim_control",
    "manipulation_check",
    "modality_strength_check",
    "run_section6_controls",
]

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

# Content fact_types: everything except knowledge_structure (which relies on KG
# triples) is a content-only fact.  None fact_type items are multi-hop and are
# excluded from both content and structure partitions.
_CONTENT_FACT_TYPES: frozenset[FactType] = frozenset({
    FactType.GENRE_FORM,
    FactType.TRADITION_AFFILIATION,
    FactType.SCOPE,
    FactType.DESCRIPTIVE_ROLE,
})

_STRUCTURE_FACT_TYPES: frozenset[FactType] = frozenset({
    FactType.KNOWLEDGE_STRUCTURE,
})

# Minimum rise in fabrication rate under ablation for the targeted effect to
# count as "rises" in the manipulation check.
_MANIPULATION_MIN_RISE: float = 0.15

# Maximum permitted rise in the NON-targeted modality under ablation before
# it is considered leakage (generation/grading separation violated).
_MANIPULATION_MAX_CROSS: float = 0.20

# Default tolerance for negative_control: the FULL condition fabrication may
# sit this far above the classifier-error floor without triggering a failure.
# 0.1 (10 pp) is a generous offline budget; the real run uses MiniCheck-7B
# which is tighter.
_NEGATIVE_CONTROL_DEFAULT_TOLERANCE: float = 0.1

# Default minimum content labels for modality_strength_check.  Below this
# count the content axis is considered "thin" and the detail warns.
_MODALITY_STRENGTH_MIN_CONTENT_LABELS: int = 3


class ControlResult(BaseModel):
    """Result for one SPEC-text sec 6 falsifiable control.

    Fields:
        name              -- control identifier.
        passed            -- True if the control passes (or is reporting-only).
        detail            -- human-readable summary of what was checked and the outcome.

    Control-specific numeric fields (None when not applicable):
        full_fab_mean         -- negative_control: FULL condition mean fabrication rate.
        error_floor           -- negative_control: the classifier-error floor passed in.
        n_adversarial         -- false_claim_control: total adversarial items checked.
        n_adversarial_fabricated -- false_claim_control: those that graded FABRICATED.
        content_full_fab      -- manipulation_check: content items fab under FULL.
        content_absent_fab    -- manipulation_check: content items fab under CONTENT_ABSENT.
        structure_full_fab    -- manipulation_check: structure items fab under FULL.
        structure_absent_fab  -- manipulation_check: structure items fab under CONTENT_ABSENT.
        content_label_count   -- modality_strength_check: number of content labels in ref.
    """

    name: str
    passed: bool
    detail: str

    # negative_control
    full_fab_mean: float | None = None
    error_floor: float | None = None

    # false_claim_control
    n_adversarial: int | None = None
    n_adversarial_fabricated: int | None = None

    # manipulation_check
    content_full_fab: float | None = None
    content_absent_fab: float | None = None
    structure_full_fab: float | None = None
    structure_absent_fab: float | None = None

    # modality_strength_check
    content_label_count: int | None = None


class Section6Report(BaseModel):
    """Aggregated result of all four sec 6 controls.

    Fields:
        results         -- all four ControlResult objects (in run order).
        overall_passed  -- True iff negative AND false_claim AND manipulation all pass.
                          modality_strength is reporting-only and does NOT veto.
    """

    results: list[ControlResult] = Field(default_factory=list)
    overall_passed: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fab_rate(runs: list[GroundingRun]) -> float:
    """Mean fabrication rate over a list of runs (answer-level per-run mean)."""
    if not runs:
        return 0.0
    per_run = [r.fabrication_rate() for r in runs]
    return sum(per_run) / len(per_run)


def _filter_runs_by_condition(runset: RunSet, condition: Condition) -> list[GroundingRun]:
    return [r for r in runset.runs if r.condition == condition]


def _runs_for_questions(
    runs: list[GroundingRun], question_ids: set[str]
) -> list[GroundingRun]:
    """Filter runs whose .question field is in question_ids."""
    return [r for r in runs if r.question in question_ids]


# ---------------------------------------------------------------------------
# 1. negative_control
# ---------------------------------------------------------------------------


def negative_control(
    full_runs: list[GroundingRun],
    error_floor: float,
    *,
    tolerance: float = _NEGATIVE_CONTROL_DEFAULT_TOLERANCE,
) -> ControlResult:
    """Negative control: FULL-condition mean fabrication must sit at/below the
    classifier-error floor (within tolerance).

    A high no-ablation fabrication rate signals that the pipeline is broken
    independent of any perturbation.

    Parameters
    ----------
    full_runs:
        GroundingRuns produced under the FULL condition (no withholding).
    error_floor:
        The classifier-error floor from the reliability report
        (reliability_report["overall_error_rate"]).
    tolerance:
        Permitted excess above the floor before the control fails (default 0.1).

    Returns
    -------
    ControlResult
        passed=True iff full_fab_mean <= error_floor + tolerance.
    """
    full_fab_mean = _fab_rate(full_runs)
    threshold = error_floor + tolerance
    passed = full_fab_mean <= threshold
    detail = (
        f"full_fab_mean={full_fab_mean:.4f} "
        f"error_floor={error_floor:.4f} tolerance={tolerance:.4f} "
        f"threshold={threshold:.4f} -> {'PASS' if passed else 'FAIL'}"
    )
    return ControlResult(
        name="negative_control",
        passed=passed,
        detail=detail,
        full_fab_mean=full_fab_mean,
        error_floor=error_floor,
    )


# ---------------------------------------------------------------------------
# 2. false_claim_control
# ---------------------------------------------------------------------------


def false_claim_control(
    gold: GoldQASet,
    reference: GradingReference,
    config: GroundingConfig,
    *,
    _components: GroundingComponents | None = None,
) -> ControlResult:
    """False-claim rejection control (NON-NEGOTIABLE).

    For each adversarial_negative item in the gold set, runs
    ground_response(question, adversarial_claim, reference,
                    active_perturbations=[], config=config)
    under FULL context and asserts the produced claim grades FABRICATED.

    An entity-match-only grader is caught here because the entity IS in the
    reference but the value is wrong; a value-sensitive gate blocks it.

    Parameters
    ----------
    gold:
        The GoldQASet; must contain at least one adversarial_negative item.
    reference:
        The full grading reference (never ablated).
    config:
        GroundingConfig.  Use entailment="lexical" for CI/testing; the
        offline sweep uses "minicheck".
    _components:
        Optional GroundingComponents for test injection.  When supplied,
        these components (which may contain a deliberately broken gate) are
        used instead of build_components(reference, config).  This is the
        test-injection seam; production callers omit this argument.

    Returns
    -------
    ControlResult
        passed=True iff ALL adversarial items grade FABRICATED.
    """
    adversarial = gold.adversarial_items()
    if not adversarial:
        return ControlResult(
            name="false_claim_control",
            passed=False,
            detail="no adversarial items in gold set -- control cannot run",
            n_adversarial=0,
            n_adversarial_fabricated=0,
        )

    # Build components once (reused across all adversarial items).
    if _components is None:
        components = build_components(reference, config)
    else:
        components = _components

    n_fabricated = 0
    verdicts: list[str] = []

    for item in adversarial:
        # Derive the adversarial claim text from the expected_outcomes: use the
        # first outcome that has expected_status=FABRICATED (the swapped-value
        # claim).  If none carry an explicit FABRICATED outcome, fall back to
        # the first outcome's claim_text (the item was authored as adversarial
        # so all outcomes should be FABRICATED by construction).
        adv_claim_text: str | None = None
        for outcome in item.expected_outcomes:
            if outcome.expected_status == ClaimStatus.FABRICATED:
                adv_claim_text = outcome.claim_text
                break
        if adv_claim_text is None and item.expected_outcomes:
            adv_claim_text = item.expected_outcomes[0].claim_text

        if adv_claim_text is None:
            verdicts.append(f"{item.item_id}: no claim text -- SKIP")
            continue

        # Ground the adversarial claim under FULL context (active_perturbations=[]).
        run = _ground_with_components(
            item.question,
            adv_claim_text,
            reference,
            active_perturbations=[],
            components=components,
        )

        # Check whether all claims in the run were graded FABRICATED.
        # We expect all extracted claims to be FABRICATED since the entire
        # answer_text IS the adversarial claim.
        all_fabricated = bool(run.claims) and all(c.status == ClaimStatus.FABRICATED for c in run.claims)

        # PASS criterion: all extracted claims are FABRICATED (not merely "some").
        if all_fabricated:
            n_fabricated += 1
            verdicts.append(f"{item.item_id}: FABRICATED (PASS)")
        elif not run.claims:
            # No claims extracted -- cannot verify; count as failure.
            verdicts.append(f"{item.item_id}: no claims extracted -- FAIL")
        else:
            non_fab = [c.status.value for c in run.claims if c.status != ClaimStatus.FABRICATED]
            verdicts.append(f"{item.item_id}: non-FABRICATED claims {non_fab} -- FAIL")

    passed = n_fabricated == len(adversarial)
    verdict_str = "; ".join(verdicts)
    detail = (
        f"adversarial_items={len(adversarial)} "
        f"all_fabricated={n_fabricated} "
        f"-> {'PASS' if passed else 'FAIL'}. "
        f"Per-item: {verdict_str}"
    )
    return ControlResult(
        name="false_claim_control",
        passed=passed,
        detail=detail,
        n_adversarial=len(adversarial),
        n_adversarial_fabricated=n_fabricated,
    )


# ---------------------------------------------------------------------------
# 3. manipulation_check
# ---------------------------------------------------------------------------


def manipulation_check(
    runset: RunSet,
    bank: QuestionBank,
) -> ControlResult:
    """Manipulation check: ablating a content-only fact raises fabrication
    on content-targeting questions AND leaves structure-answerable questions
    stable (and symmetrically for KNOWLEDGE_ABSENT on structure vs content).

    Checks the CONTENT_ABSENT arm (primary ablation axis for books-P0):
      - content items: CONTENT_ABSENT fab > FULL fab by at least _MANIPULATION_MIN_RISE
      - structure items: CONTENT_ABSENT fab does NOT rise more than _MANIPULATION_MAX_CROSS
        above FULL fab (cross-effect tolerance)

    A perturbation that flips claims it should not affect signals that the
    generation/grading separation is leaking.

    Parameters
    ----------
    runset:
        The full RunSet containing FULL and CONTENT_ABSENT condition runs.
    bank:
        QuestionBank; items with content fact_types are "content-targeting";
        items with knowledge_structure fact_type are "structure-answerable".

    Returns
    -------
    ControlResult
        passed=True iff targeted effect rises AND cross-effect is within tolerance.
    """
    # Partition question bank into content vs structure items.
    content_ids = {
        it.item_id for it in bank.items
        if it.fact_type in _CONTENT_FACT_TYPES
    }
    structure_ids = {
        it.item_id for it in bank.items
        if it.fact_type in _STRUCTURE_FACT_TYPES
    }

    full_runs = _filter_runs_by_condition(runset, Condition.FULL)
    absent_runs = _filter_runs_by_condition(runset, Condition.CONTENT_ABSENT)

    # FULL condition fab for content items
    content_full = _fab_rate(_runs_for_questions(full_runs, content_ids))
    # CONTENT_ABSENT condition fab for content items
    content_absent = _fab_rate(_runs_for_questions(absent_runs, content_ids))
    # FULL condition fab for structure items
    structure_full = _fab_rate(_runs_for_questions(full_runs, structure_ids))
    # CONTENT_ABSENT condition fab for structure items
    structure_absent = _fab_rate(_runs_for_questions(absent_runs, structure_ids))

    targeted_rise = content_absent - content_full
    cross_rise = structure_absent - structure_full

    # Directional effect: content fab must rise by at least _MANIPULATION_MIN_RISE.
    targeted_ok = targeted_rise >= _MANIPULATION_MIN_RISE
    # Cross-effect: structure fab rise must stay within tolerance.
    cross_ok = cross_rise <= _MANIPULATION_MAX_CROSS

    passed = targeted_ok and cross_ok

    reasons: list[str] = []
    if not targeted_ok:
        reasons.append(
            f"targeted_rise={targeted_rise:.4f} < min_rise={_MANIPULATION_MIN_RISE:.4f}"
        )
    if not cross_ok:
        reasons.append(
            f"cross_rise={cross_rise:.4f} > max_cross={_MANIPULATION_MAX_CROSS:.4f} (leaking)"
        )
    if not reasons:
        reasons.append("OK")

    detail = (
        f"content_full={content_full:.4f} content_absent={content_absent:.4f} "
        f"targeted_rise={targeted_rise:.4f} (min={_MANIPULATION_MIN_RISE:.2f}); "
        f"structure_full={structure_full:.4f} structure_absent={structure_absent:.4f} "
        f"cross_rise={cross_rise:.4f} (max={_MANIPULATION_MAX_CROSS:.2f}); "
        f"-> {'PASS' if passed else 'FAIL: ' + ', '.join(reasons)}"
    )
    return ControlResult(
        name="manipulation_check",
        passed=passed,
        detail=detail,
        content_full_fab=content_full,
        content_absent_fab=content_absent,
        structure_full_fab=structure_full,
        structure_absent_fab=structure_absent,
    )


# ---------------------------------------------------------------------------
# 4. modality_strength_check
# ---------------------------------------------------------------------------


def modality_strength_check(
    reference: GradingReference,
    bank: QuestionBank,
    *,
    min_content_labels: int = _MODALITY_STRENGTH_MIN_CONTENT_LABELS,
) -> ControlResult:
    """Modality-strength check (REPORTING ONLY -- does not veto overall_passed).

    Flags when the content axis is thin (few content labels in the reference)
    so that a weak content result is attributed to thin content rather than
    being interpreted as a modality failure.

    Always returns passed=True; the detail string carries the thin-or-adequate
    judgment so the caller can surface it in the report.

    Parameters
    ----------
    reference:
        The full grading reference; content_labels are examined.
    bank:
        QuestionBank; used to count content-targeting questions.
    min_content_labels:
        Minimum number of content labels in the reference before the content
        axis is considered "adequate".  Below this is "thin".

    Returns
    -------
    ControlResult with passed=True always; detail describes the count and judgment.
    """
    n_labels = len(reference.content_labels)
    n_content_questions = sum(
        1 for it in bank.items if it.fact_type in _CONTENT_FACT_TYPES
    )
    is_thin = n_labels < min_content_labels

    if is_thin:
        detail = (
            f"content_label_count={n_labels} < min_content_labels={min_content_labels} -- "
            f"THIN: content axis result reflects thin content, not modality strength. "
            f"content_questions_in_bank={n_content_questions}"
        )
    else:
        detail = (
            f"content_label_count={n_labels} >= min_content_labels={min_content_labels} -- "
            f"adequate content axis. "
            f"content_questions_in_bank={n_content_questions}"
        )

    return ControlResult(
        name="modality_strength_check",
        passed=True,  # reporting only; never vetoes
        detail=detail,
        content_label_count=n_labels,
    )


# ---------------------------------------------------------------------------
# 5. Aggregator
# ---------------------------------------------------------------------------


def run_section6_controls(
    runset: RunSet,
    gold: GoldQASet,
    reference: GradingReference,
    bank: QuestionBank,
    reliability: dict[str, Any],
    config: GroundingConfig,
    *,
    _false_claim_components: GroundingComponents | None = None,
    min_content_labels: int = _MODALITY_STRENGTH_MIN_CONTENT_LABELS,
) -> Section6Report:
    """Run all four sec 6 falsifiable controls and return an aggregated report.

    Parameters
    ----------
    runset:
        The full offline RunSet (must contain FULL and ideally
        CONTENT_ABSENT / KNOWLEDGE_ABSENT conditions for manipulation_check).
    gold:
        The GoldQASet with adversarial_negative items for false_claim_control.
    reference:
        The full grading reference.
    bank:
        The QuestionBank (used by manipulation_check and modality_strength_check).
    reliability:
        The reliability report dict; must contain "overall_error_rate".
    config:
        GroundingConfig for false_claim_control (use lexical for CI).
    _false_claim_components:
        Optional GroundingComponents for test injection into false_claim_control.
        Normal callers omit this; tests inject a broken gate here.
    min_content_labels:
        Threshold for modality_strength_check (passed through).

    Returns
    -------
    Section6Report
        overall_passed = negative AND false_claim AND manipulation.
        modality_strength is reporting-only and does NOT veto.
    """
    error_floor = float(reliability.get("overall_error_rate", 0.0))
    full_runs = _filter_runs_by_condition(runset, Condition.FULL)

    neg = negative_control(full_runs, error_floor)
    fc = false_claim_control(gold, reference, config, _components=_false_claim_components)
    mc = manipulation_check(runset, bank)
    ms = modality_strength_check(reference, bank, min_content_labels=min_content_labels)

    overall_passed = neg.passed and fc.passed and mc.passed
    # modality_strength is reporting-only; does not affect overall_passed

    return Section6Report(
        results=[neg, fc, mc, ms],
        overall_passed=overall_passed,
    )
