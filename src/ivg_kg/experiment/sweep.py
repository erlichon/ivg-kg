"""GR11: offline precompute sweep harness + runs store (SPEC-text sec 8 / 10 / 4.8 / 4.6).

This module is the OFFLINE PRECOMPUTE SWEEP. For each question in the bank, under
each condition {full, content-absent, knowledge-absent}, it generates N seeded
answers (GR4) over the (possibly ablated) generation context (GR3, the ONLY
ablation site) and grounds each answer against the FULL reference (GR9). The
resulting GroundingRuns are collected into a RunSet and written to data/runs/.

This sweep IS the source of the RQ2 modality-contrast aggregate (SPEC-text sec 8 /
10): the reported numbers come from THIS offline precompute, never from the live
single-run path. It also emits a matched NO-REPAIR re-run baseline so EX3's
repair_leverage is net of generator variance (SPEC-text sec 4.6 / 4.8).

Grade-vs-FULL-reference under withhold (REMOVE semantics, Invariant #1): the
perturbation only changes what the GENERATOR sees; grading ALWAYS uses the full
reference passed to ``run_sweep`` (never the ablated context). ``active_perturbations``
on each run is recorded for attribution only and never alters a grading decision.

Seed scheme (deterministic): ``sweep_seed(question_id, condition, sample_index)`` is
a stable int derived from sha256 of "<qid>|<condition.value>|<sample_index>". It is
identical across runs and processes (no Python hash()/PYTHONHASHSEED dependence).

No-repair baseline keying: for each FULL run at sample_index i, a synthetic re-run
of the SAME FULL question with NO edit is produced at a DIFFERENT seed (the seed for
condition=FULL_NO_EDIT_RERUN, sample_index i), grounded, and stored as its own
GroundingRun with condition=FULL_NO_EDIT_RERUN and baseline_run_id set to the matched
FULL run's run_id.

Deterministic / pure: given the seed scheme (generator) and the fixed answer texts
(verifier is deterministic), the same inputs produce a byte-identical RunSet. No
time, no network, no pickle. A GenerationCache (when supplied) prevents
re-generation of identical (question, context, temperature, seed) draws.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from ivg_kg.experiment.question_bank import QuestionBank, QuestionBankItem
from ivg_kg.grounding.backend import _ground_with_components, build_components
from ivg_kg.grounding.clients.base import BaseAIClient
from ivg_kg.grounding.context import assemble_context
from ivg_kg.grounding.generate import GenerationCache, generate_answer
from ivg_kg.perturbation.base import Perturbation
from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence
from ivg_kg.perturbation.text_content_absence import TextContentAbsence
from ivg_kg.schema import (
    Condition,
    GradingReference,
    GroundingConfig,
    GroundingRun,
    TripleRef,
)

__all__ = [
    "sweep_seed",
    "default_perturbations_for",
    "RunSet",
    "run_sweep",
    "write_runset",
]

# Generation temperature for the sweep. GroundingConfig carries no temperature
# field (it is a verifier-side config), so the generator-side default lives here.
_DEFAULT_TEMPERATURE: float = 0.7

# Default output directory for written runs (same convention as the rest of the
# codebase; gitignored except slice-*.json fixtures).
_DEFAULT_RUNS_DIR = Path("data/runs")

# Conditions whose default perturbation set is empty (no withholding): the FULL
# question and its synthetic no-edit re-run baseline.
_NO_WITHHOLD_CONDITIONS = frozenset({Condition.FULL, Condition.FULL_NO_EDIT_RERUN})


# ---------------------------------------------------------------------------
# Seed scheme
# ---------------------------------------------------------------------------


def sweep_seed(question_id: str, condition: Condition, sample_index: int) -> int:
    """Return a deterministic seed for one (question, condition, sample) draw.

    The seed is a stable non-negative int derived from the SHA-256 digest of
    "<question_id>|<condition.value>|<sample_index>". It is identical across
    process restarts (no Python hash()/PYTHONHASHSEED dependence) and distinct
    for distinct (question_id, condition, sample_index) triples, including the
    FULL vs FULL_NO_EDIT_RERUN distinction (so the no-repair baseline draws a
    different answer than its matched FULL run).
    """
    payload = f"{question_id}|{condition.value}|{sample_index}".encode()
    digest = hashlib.sha256(payload).hexdigest()
    # Take 16 hex chars (64 bits) -> a stable, comfortably-sized seed int.
    return int(digest[:16], 16)


# ---------------------------------------------------------------------------
# Condition -> perturbations mapping (harness default for the books spine)
# ---------------------------------------------------------------------------


def _outgoing_triple_refs(reference: GradingReference, entity_id: str) -> list[TripleRef]:
    """Return a TripleRef for each OUTGOING edge of entity_id, in snapshot order."""
    return [
        TripleRef(
            subject_id=edge.subject_id,
            property_id=edge.property_id,
            object_id=edge.object_id,
        )
        for edge in reference.snapshot.edges
        if edge.subject_id == entity_id
    ]


def default_perturbations_for(
    item: QuestionBankItem,
    condition: Condition,
    reference: GradingReference,
) -> list[Perturbation]:
    """Default condition -> perturbations mapping for the books spine.

    - FULL / FULL_NO_EDIT_RERUN -> [] (no withholding).
    - CONTENT_ABSENT  -> [TextContentAbsence(item.entity_id)] (withhold description).
    - KNOWLEDGE_ABSENT -> [KnowledgeAbsence(outgoing triples of item.entity_id)].

    The richer per-question manifests EX2 / the data stream may supply later are
    injected via the ``perturbations_for`` override on ``run_sweep``; this is the
    harness default. IMAGE_ABSENT is intentionally unsupported (books-first).
    """
    if condition in _NO_WITHHOLD_CONDITIONS:
        return []
    if condition == Condition.CONTENT_ABSENT:
        return [TextContentAbsence(item.entity_id)]
    if condition == Condition.KNOWLEDGE_ABSENT:
        refs = _outgoing_triple_refs(reference, item.entity_id)
        return [KnowledgeAbsence(refs)]
    raise ValueError(f"Unsupported condition for the books spine: {condition!r}")


# ---------------------------------------------------------------------------
# RunSet
# ---------------------------------------------------------------------------


class RunSet(BaseModel):
    """All runs produced by one offline sweep (SPEC-text sec 4.8).

    Fields:
        sweep_id:   Stable identifier for this sweep.
        slice_id:   The frozen slice the bank covers.
        bank_id:    The question bank version swept.
        conditions: The generation conditions swept (in order).
        n_runs:     Number of seeded draws per (question, condition).
        runs:       Every produced run -- each question x condition x sample,
                    plus the FULL_NO_EDIT_RERUN no-repair baselines.
    """

    sweep_id: str
    slice_id: str
    bank_id: str
    conditions: list[Condition]
    n_runs: int
    runs: list[GroundingRun]

    def get(self, item_id: str, condition: Condition, sample_index: int) -> GroundingRun | None:
        """Return the run matching (item_id, condition, sample_index), or None.

        Looks up by the deterministic run_id '<item_id>--<condition.value>--s<sample_index>'
        (the same key used by ``_run_id``). This avoids consumers re-scanning ``runs``
        with manual comprehensions (useful for EX3/EX4 repair-leverage lookups).
        """
        target_id = _run_id(item_id, condition, sample_index)
        for run in self.runs:
            if run.run_id == target_id:
                return run
        return None


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------


def _run_id(item_id: str, condition: Condition, sample_index: int) -> str:
    """Deterministic run id: '<item_id>--<condition.value>--s<sample_index>'."""
    return f"{item_id}--{condition.value}--s{sample_index}"


def run_sweep(
    bank: QuestionBank,
    reference: GradingReference,
    client: BaseAIClient,
    *,
    conditions: Sequence[Condition] = (
        Condition.FULL,
        Condition.CONTENT_ABSENT,
        Condition.KNOWLEDGE_ABSENT,
    ),
    n_runs: int = 20,
    config: GroundingConfig | None = None,
    cache: GenerationCache | None = None,
    perturbations_for: Callable[[QuestionBankItem, Condition, GradingReference], list[Perturbation]]
    | None = None,
    emit_no_repair_baseline: bool = True,
    on_run_complete: Callable[[GroundingRun, int, int], None] | None = None,
) -> RunSet:
    """Run the offline precompute sweep over a question bank against one reference.

    For each item, condition, and sample_index in range(n_runs): seed the draw,
    resolve the condition's perturbations, assemble the (ablated) context (GR3),
    generate a seeded answer (GR4), and ground it against the FULL ``reference``
    (GR9 via the shared ``_ground_with_components`` seam). Grading ALWAYS uses
    the full reference -- perturbations only changed the generator's context.

    When ``emit_no_repair_baseline`` is True, each FULL run also yields a synthetic
    FULL_NO_EDIT_RERUN run (same FULL question, NO edit, a DIFFERENT seed) whose
    ``baseline_run_id`` points at the matched FULL run, letting EX3 subtract
    generator variance.

    The verifier-side pipeline components (linker, canon, gate -> classifier, and
    the extractor) are built ONCE here and reused across every draw, since the
    reference is immutable for the whole sweep.

    ``on_run_complete``: optional progress callback invoked after each grounding
    completes with signature ``(run, completed_count, total_count)``.  Default
    ``None`` -- no side-effects (existing callers and tests are unaffected).

    Deterministic: same inputs -> equal RunSet (see module docstring).
    """
    cfg = config if config is not None else GroundingConfig()
    pert_fn = perturbations_for if perturbations_for is not None else default_perturbations_for
    conditions = list(conditions)

    # Build verifier-side components ONCE (the reference is immutable across the
    # whole sweep) -- avoids rebuilding the NetworkX graph / reloading the canon
    # per draw.
    components = build_components(reference, cfg)

    def _ground_one(
        item: QuestionBankItem,
        condition: Condition,
        sample_index: int,
        run_id: str,
        baseline_run_id: str | None,
    ) -> GroundingRun:
        seed = sweep_seed(item.item_id, condition, sample_index)
        perts = pert_fn(item, condition, reference)
        context = assemble_context(reference, item.entity_id, perturbations=perts)
        answer = generate_answer(
            item.question,
            context,
            client,
            temperature=_DEFAULT_TEMPERATURE,
            seed=seed,
            cache=cache,
        )
        run = _ground_with_components(
            item.question,
            answer,
            reference,
            active_perturbations=[p.id for p in perts],
            components=components,
        )
        return run.model_copy(
            update={
                "run_id": run_id,
                "condition": condition,
                "sample_index": sample_index,
                "baseline_run_id": baseline_run_id,
            }
        )

    # Pre-compute total run count for the progress callback (if supplied).
    # Each (item, condition, sample) primary run may also emit a no-repair
    # baseline run -- count them up-front so the callback receives an accurate
    # denominator without look-ahead.
    _emit_baseline = emit_no_repair_baseline and Condition.FULL_NO_EDIT_RERUN not in conditions
    _full_in_conditions = Condition.FULL in conditions
    _baseline_per_item = n_runs if (_emit_baseline and _full_in_conditions) else 0
    _primary_per_item = n_runs * len(conditions)
    _total_runs = len(bank.items) * (_primary_per_item + _baseline_per_item)

    runs: list[GroundingRun] = []
    completed = 0
    for item in bank.items:
        for condition in conditions:
            for sample_index in range(n_runs):
                run_id = _run_id(item.item_id, condition, sample_index)
                run = _ground_one(item, condition, sample_index, run_id, None)
                runs.append(run)
                completed += 1
                if on_run_complete is not None:
                    on_run_complete(run, completed, _total_runs)

                # Matched no-repair baseline: only for FULL runs, and only when
                # FULL_NO_EDIT_RERUN was not itself an explicit condition.
                if _emit_baseline and condition == Condition.FULL:
                    base_run_id = _run_id(item.item_id, Condition.FULL_NO_EDIT_RERUN, sample_index)
                    baseline_run = _ground_one(
                        item,
                        Condition.FULL_NO_EDIT_RERUN,
                        sample_index,
                        base_run_id,
                        run_id,
                    )
                    runs.append(baseline_run)
                    completed += 1
                    if on_run_complete is not None:
                        on_run_complete(baseline_run, completed, _total_runs)

    sweep_id = f"sweep:{bank.bank_id}:{bank.slice_id}"
    return RunSet(
        sweep_id=sweep_id,
        slice_id=bank.slice_id,
        bank_id=bank.bank_id,
        conditions=conditions,
        n_runs=n_runs,
        runs=runs,
    )


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_runset(runset: RunSet, out_dir: Path | str | None = None) -> list[Path]:
    """Write each run to <out_dir>/<run_id>.json (default data/runs/).

    Deterministic: each file is the pydantic JSON of one GroundingRun. Sweep
    output run ids use the '<item_id>--<condition>--sN' naming, which is NOT
    'slice-*', so the files are correctly gitignored (do not commit them).
    Returns the list of written paths (in run order).

    Note: item_id must be filename-safe (no '/', whitespace) -- it becomes part
    of the run file name via the '<item_id>--<condition>--sN' pattern.  The
    standard 'qb-N' ids produced by QuestionBank fixtures satisfy this.
    """
    target = Path(out_dir) if out_dir is not None else _DEFAULT_RUNS_DIR
    target.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for run in runset.runs:
        path = target / f"{run.run_id}.json"
        path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        paths.append(path)
    return paths
