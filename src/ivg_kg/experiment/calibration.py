"""GR10 -- Gold-QA calibration, per-modality error, and reliability curve.

SPEC-text 4.7 + 4.9a. This is the DEPLOYMENT-LEVEL trust tier: the verifier's
error measured on the CURATED gold QA set, with the operating point (tau)
frozen on a disjoint calibration fold.

TWO-TIER TRUST DISTINCTION
  - instrument-level: the NLI gate's published benchmark accuracy plus a
    per-claim margin-to-tau confidence PROXY. Data-agnostic; NOT calibrated on
    our data.
  - deployment-level (THIS module): error CALIBRATED on the curated gold set.
    This is the ONLY tier that earns the word "calibrated".

The honesty flag CalibrationReport.calibrated is True ONLY when the report was
produced with the real model gate (config.entailment == "minicheck"). The
model-free "lexical" gate is a deterministic DEMO/UNCALIBRATED stand-in and
always yields calibrated == False.

DISJOINT-FOLD DISCIPLINE
  tau is calibrated (swept) on the CALIBRATION fold ONLY and then FROZEN. The
  report is produced by evaluating the SWEEP fold (the held-out anchor) with the
  frozen tau. The sweep fold is never used to tune tau; nothing is tuned
  post-hoc on the reported fold.

These are eval OUTPUTS, not the UI contract, so they live experiment-side (like
gold_qa.py) and are NOT added to schema.py.

Determinism: the lexical-gate path is fully deterministic; no randomness, time,
network, or pickle. The reliability curve uses fixed-width margin bins.

BOOKS-FIRST: modality is text/structure only; no image axis.
"""

from __future__ import annotations

from pydantic import BaseModel

from ivg_kg.experiment.gold_qa import GoldQASet
from ivg_kg.grounding.classify import Classifier
from ivg_kg.grounding.entailment import make_entailment_gate
from ivg_kg.grounding.link import PropertyCanon, make_entity_linker
from ivg_kg.schema import (
    ClaimStatus,
    GradingReference,
    GroundingConfig,
    LinkedEntity,
)

__all__ = [
    "ModalityError",
    "ReliabilityBin",
    "CalibrationReport",
    "evaluate_gold_set",
    "calibrate_tau",
    "build_reliability_report",
]

# Number of fixed-width margin bins for the reliability curve. The margin axis
# is |entailment_score - tau| in [0, 1], split into this many equal-width bins.
_RELIABILITY_BINS: int = 5


# ---------------------------------------------------------------------------
# Output types (JSON-serialisable, deterministic eval outputs)
# ---------------------------------------------------------------------------


class ModalityError(BaseModel):
    """Per-modality classifier error on the evaluated fold.

    The text-NLI gate axis ("text") and the structure-path gate axis
    ("structure") are reported SEPARATELY (SPEC-text 4.9a).
    """

    modality: str  # "text" | "structure"
    n: int  # claims evaluated in this modality
    n_correct: int  # produced status == expected status
    error_rate: float  # 1 - n_correct/n; 0.0 when n == 0


class ReliabilityBin(BaseModel):
    """One bin of the reliability curve: margin band vs empirical accuracy.

    The margin is |entailment_score - tau|; higher margin should track higher
    empirical accuracy if the gate is well-behaved.
    """

    margin_lo: float  # bin lower edge of |entailment_score - tau|
    margin_hi: float
    n: int
    accuracy: float  # empirical fraction correct in this bin; 0.0 when n == 0


class CalibrationReport(BaseModel):
    """Deployment-level calibrated trust report (SPEC-text 4.7 + 4.9a)."""

    set_id: str
    slice_id: str
    gate: str  # entailment selector used ("lexical"/"minicheck"); honesty flag
    calibrated: bool  # True ONLY when gate == "minicheck"
    frozen_tau: float  # tau frozen on the CALIBRATION fold (or config.tau)
    frozen_k: int  # k_hops frozen (recorded from config)
    overall_error_rate: float
    per_modality_error: list[ModalityError]  # text and structure separately
    adversarial_negative_accuracy: float  # fraction of adversarial items graded FABRICATED
    supportable_bucket_accuracy: float  # accuracy restricted to expected == REASONED_SUPPORTABLE
    linking_coverage: float  # fraction of claims that linked + reached the gate
    accepted_path_multiplicity_mean: (
        float  # mean accepted (> tau) distinct paths per supportable claim
    )
    reliability_curve: list[ReliabilityBin]  # margin-bin vs empirical accuracy
    n_items: int
    n_claims: int


# ---------------------------------------------------------------------------
# Internal per-claim evaluation record
# ---------------------------------------------------------------------------


class _ClaimEval(BaseModel):
    """One evaluated (expected, produced) pair plus the metadata the metrics need."""

    expected_status: ClaimStatus
    produced_status: ClaimStatus
    modality: str
    margin: float  # |entailment_score - tau|; score treated as 0.0 when None
    reached_gate: bool  # linked to >= 1 in-slice entity (so the gate ran)
    adversarial: bool

    @property
    def correct(self) -> bool:
        return self.expected_status == self.produced_status


# ---------------------------------------------------------------------------
# Accepted-path multiplicity helper
# ---------------------------------------------------------------------------


def _accepted_path_multiplicity(
    classifier: Classifier,
    claim_text: str,
    linked_entities: list[LinkedEntity],
    tau: float,
) -> int:
    """Count DISTINCT multi-hop paths the gate accepts (> tau) for a claim.

    Spurious-path exposure metric (SPEC-text 4.8): for a supportable claim,
    counts how many distinct 2..k-hop paths between the claim's linked entity
    endpoints score above tau. Uses the classifier's public surface exclusively
    so enumeration cannot silently diverge from the real classifier.
    """
    endpoints = classifier.resolve_endpoints(linked_entities)
    if len(endpoints) < 2:
        return 0
    return len(classifier.accepted_multi_hop_paths(claim_text, endpoints, tau=tau))


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def _evaluate_items(
    items: list,
    reference: GradingReference,
    *,
    config: GroundingConfig,
) -> tuple[list[_ClaimEval], list[float]]:
    """Run the verifier over every expected outcome of every item.

    Returns (per-claim evals, per-supportable-claim accepted-path multiplicities).
    The classifier, gate, linker, and canon are built ONCE and reused.
    """
    gate = make_entailment_gate(config)
    canon = PropertyCanon({}, {})
    classifier = Classifier(reference, gate=gate, canon=canon, config=config)
    linker = make_entity_linker(config.linker, reference.snapshot)
    tau = config.tau

    evals: list[_ClaimEval] = []
    multiplicities: list[float] = []

    for item in items:
        for outcome in item.expected_outcomes:
            claim_text = outcome.claim_text
            linked, unresolved = linker.link_text(claim_text)
            record = classifier.classify(
                claim_text,
                linked,
                claim_id=item.item_id,
                unresolved_entities=unresolved,
            )
            score = record.entailment_score if record.entailment_score is not None else 0.0
            margin = abs(score - tau)
            reached_gate = len(linked) > 0
            evals.append(
                _ClaimEval(
                    expected_status=outcome.expected_status,
                    produced_status=record.status,
                    modality=outcome.modality.value,
                    margin=margin,
                    reached_gate=reached_gate,
                    adversarial=item.adversarial_negative,
                )
            )
            if outcome.expected_status == ClaimStatus.REASONED_SUPPORTABLE:
                multiplicities.append(
                    float(_accepted_path_multiplicity(classifier, claim_text, linked, tau))
                )

    return evals, multiplicities


def _build_report(
    *,
    set_id: str,
    slice_id: str,
    gate_selector: str,
    config: GroundingConfig,
    frozen_tau: float,
    n_items: int,
    evals: list[_ClaimEval],
    multiplicities: list[float],
) -> CalibrationReport:
    """Aggregate per-claim evals into a CalibrationReport (deterministic)."""
    n_claims = len(evals)
    n_correct = sum(1 for e in evals if e.correct)
    overall_error_rate = 0.0 if n_claims == 0 else 1.0 - n_correct / n_claims

    # Per-modality error: one entry per modality present in the evals, sorted for
    # determinism. Data-derived so a future third modality (image, post-BOOKS)
    # flows through with no code edit.
    modalities = sorted({e.modality for e in evals})
    per_modality: list[ModalityError] = []
    for modality in modalities:
        mod_evals = [e for e in evals if e.modality == modality]
        n = len(mod_evals)
        correct = sum(1 for e in mod_evals if e.correct)
        error_rate = 0.0 if n == 0 else 1.0 - correct / n
        per_modality.append(
            ModalityError(modality=modality, n=n, n_correct=correct, error_rate=error_rate)
        )

    # Adversarial accuracy: fraction of adversarial items correctly graded
    # FABRICATED (the produced status is FABRICATED).
    adv_evals = [e for e in evals if e.adversarial]
    if adv_evals:
        adv_correct = sum(1 for e in adv_evals if e.produced_status == ClaimStatus.FABRICATED)
        adversarial_negative_accuracy = adv_correct / len(adv_evals)
    else:
        adversarial_negative_accuracy = 0.0

    # Supportable-bucket accuracy over expected == REASONED_SUPPORTABLE only.
    sup_evals = [e for e in evals if e.expected_status == ClaimStatus.REASONED_SUPPORTABLE]
    if sup_evals:
        sup_correct = sum(1 for e in sup_evals if e.correct)
        supportable_bucket_accuracy = sup_correct / len(sup_evals)
    else:
        supportable_bucket_accuracy = 0.0

    # Linking coverage: fraction of evaluated claims that linked to an in-slice
    # entity and reached the gate. DISTINCT from error: an uncovered claim can
    # still be graded correctly (e.g. correctly FABRICATED).
    linking_coverage = 0.0 if n_claims == 0 else sum(1 for e in evals if e.reached_gate) / n_claims

    # Accepted-path multiplicity mean over supportable claims (0.0 if none).
    accepted_path_multiplicity_mean = (
        0.0 if not multiplicities else sum(multiplicities) / len(multiplicities)
    )

    reliability_curve = _reliability_curve(evals)

    return CalibrationReport(
        set_id=set_id,
        slice_id=slice_id,
        gate=gate_selector,
        calibrated=(gate_selector == "minicheck"),
        frozen_tau=frozen_tau,
        frozen_k=config.k_hops,
        overall_error_rate=overall_error_rate,
        per_modality_error=per_modality,
        adversarial_negative_accuracy=adversarial_negative_accuracy,
        supportable_bucket_accuracy=supportable_bucket_accuracy,
        linking_coverage=linking_coverage,
        accepted_path_multiplicity_mean=accepted_path_multiplicity_mean,
        reliability_curve=reliability_curve,
        n_items=n_items,
        n_claims=n_claims,
    )


def _reliability_curve(evals: list[_ClaimEval]) -> list[ReliabilityBin]:
    """Bin claims that reached the gate by margin and report empirical accuracy.

    Fixed equal-width bins over the margin range [0, 1] (margin = |score - tau|).
    Only claims that reached the gate are binned (they carry a real score); the
    bin counts therefore sum to the number of gate-reaching claims. A margin of
    exactly 1.0 falls in the last bin (the top edge is inclusive there).
    """
    gated = [e for e in evals if e.reached_gate]
    width = 1.0 / _RELIABILITY_BINS
    bins: list[ReliabilityBin] = []
    for i in range(_RELIABILITY_BINS):
        lo = i * width
        hi = (i + 1) * width
        if i == _RELIABILITY_BINS - 1:
            members = [e for e in gated if lo <= e.margin <= hi]
        else:
            members = [e for e in gated if lo <= e.margin < hi]
        n = len(members)
        accuracy = 0.0 if n == 0 else sum(1 for e in members if e.correct) / n
        bins.append(ReliabilityBin(margin_lo=lo, margin_hi=hi, n=n, accuracy=accuracy))
    return bins


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def evaluate_gold_set(
    gold: GoldQASet,
    reference: GradingReference,
    *,
    config: GroundingConfig,
) -> CalibrationReport:
    """Evaluate the verifier over EVERY item/outcome in the gold set.

    For each GoldQAItem and each ExpectedClaimOutcome, the claim text is linked
    and classified against the full reference; the produced status is compared
    to the expected status. Aggregates overall + per-modality error, adversarial
    -> FABRICATED accuracy, supportable-bucket accuracy, linking coverage,
    accepted-path multiplicity mean, and the margin-binned reliability curve.

    The operating tau is config.tau; report.calibrated is True only when
    config.entailment == "minicheck".
    """
    evals, multiplicities = _evaluate_items(gold.items, reference, config=config)
    return _build_report(
        set_id=gold.set_id,
        slice_id=gold.slice_id,
        gate_selector=config.entailment,
        config=config,
        frozen_tau=config.tau,
        n_items=len(gold.items),
        evals=evals,
        multiplicities=multiplicities,
    )


def calibrate_tau(
    gold: GoldQASet,
    reference: GradingReference,
    *,
    config: GroundingConfig,
    candidates: list[float],
) -> float:
    """Sweep tau over candidates on the CALIBRATION FOLD ONLY; return the best.

    Picks the tau maximising calibration-fold accuracy. Deterministic tie-break:
    on equal accuracy the SMALLEST tau wins. This FREEZES tau; the sweep fold is
    never touched here (it stays read-only for downstream RQ2/sweep eval).
    """
    if not candidates:
        raise ValueError("calibrate_tau requires at least one candidate tau")

    cal_items = gold.calibration_items()
    best_tau: float | None = None
    best_accuracy = -1.0
    # Iterate candidates in ascending order so the smallest tau wins ties.
    for tau in sorted(candidates):
        trial_config = config.model_copy(update={"tau": tau})
        evals, _ = _evaluate_items(cal_items, reference, config=trial_config)
        n = len(evals)
        accuracy = 0.0 if n == 0 else sum(1 for e in evals if e.correct) / n
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_tau = tau
    # Typed fallback: candidates is non-empty (checked above) so best_tau is
    # always set after the loop, but returning the smallest candidate is safe
    # under -O (where assert is stripped) in case the loop somehow ran zero
    # iterations due to an empty list that slipped through.
    return best_tau if best_tau is not None else sorted(candidates)[0]


def build_reliability_report(
    gold: GoldQASet,
    reference: GradingReference,
    *,
    config: GroundingConfig,
    tau_candidates: list[float] | None = None,
) -> CalibrationReport:
    """Freeze tau on the calibration fold, then report on the SWEEP fold.

    If tau_candidates is given, frozen_tau = calibrate_tau(...) over the
    CALIBRATION fold; otherwise frozen_tau = config.tau. The report is then
    produced by evaluating the SWEEP fold (the held-out anchor) with the frozen
    tau. This enforces the disjoint-fold rule: calibrate on CALIBRATION, report
    on SWEEP, never tune post-hoc on the reported fold.
    """
    if tau_candidates is not None:
        frozen_tau = calibrate_tau(gold, reference, config=config, candidates=tau_candidates)
    else:
        frozen_tau = config.tau

    eval_config = config.model_copy(update={"tau": frozen_tau})
    sweep_items = gold.sweep_items()
    evals, multiplicities = _evaluate_items(sweep_items, reference, config=eval_config)
    return _build_report(
        set_id=gold.set_id,
        slice_id=gold.slice_id,
        gate_selector=config.entailment,
        config=eval_config,
        frozen_tau=frozen_tau,
        n_items=len(sweep_items),
        evals=evals,
        multiplicities=multiplicities,
    )
