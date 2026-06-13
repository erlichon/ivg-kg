"""Emit the 3 committed books example runs (GR9 -- real pipeline).

Deterministic generator for the 3 hand-picked books examples that the app
renders. The answers are CANNED (there is no generator call here); each is
grounded by the REAL verifier pipeline behind ground_response (GR9):

    extract  (GR5)  rule-based -> structured (head, relation, tail) claims
    link     (GR6)  label/alias index -> claim entities resolved to KG QIDs
    classify (GR8)  three-way cascade over the FULL reference + entailment gate

Each GradingReference is built from the frozen books-p0-v1 snapshot plus
hand-authored ContentLabels. The whole offline path (lexical gate, rule-based
extractor, label-alias linker) is deterministic, so running this script twice
produces byte-identical output files.

Usage:
    uv run python scripts/emit_slice_runs.py

Writes data/runs/<run_id>.json for each of the 3 examples. These files are
TRACKED fixtures (a gitignore negation keeps data/runs/slice-*.json in the repo).

Statuses produced across the 3 runs (verified against the real pipeline):
  - slice-01 (The Glass Menagerie):    RETRIEVED/DIRECT_TRIPLE, RETRIEVED/TEXT_CONTENT, FABRICATED
  - slice-02 (Pelevin books):          REASONED_SUPPORTABLE/MULTI_HOP_PATH, RETRIEVED/TEXT_CONTENT, FABRICATED
  - slice-03 (Principles of Economics): RETRIEVED/DIRECT_TRIPLE, RETRIEVED/TEXT_CONTENT, FABRICATED

Together the 3 runs exercise all three ClaimStatus values (the app demo and
Playwright depend on this variety).
"""
from __future__ import annotations

from pathlib import Path

from ivg_kg.data.graph_store import load_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.grounding.backend import ground_response
from ivg_kg.schema import GroundingConfig, GroundingRun

# Deterministic run IDs (fixed, not random, for byte-identical output)
_RUN_IDS = [
    "slice-01-glass-menagerie",
    "slice-02-pelevin-shared-author",
    "slice-03-principles-economics",
]

_SNAPSHOT_DIR = Path(__file__).parent.parent / "data" / "frozen" / "books" / "books-p0-v1"
_RUNS_DIR = Path(__file__).parent.parent / "data" / "runs"

# Shared config for all 3 slice examples.
# entailment="lexical" is the OFFLINE deterministic gate (model-free, no torch,
# no download) so the committed runs are CI-safe and byte-stable. The default
# "minicheck" gate needs torch and must NOT be used for the committed fixtures.
#
# tau=0.4 (raised from the slice's 0.3): an AUTHORED-INPUT adjustment made for
# GR9 variety, NOT a classifier change. Under the real lexical gate, the Pelevin
# joint claim (run 2, c1) scores 0.333 against a SINGLE author edge but 0.500 on
# the 2-hop shared-author path. With the cascade's first-match-wins order, a tau
# below 0.333 would resolve c1 as RETRIEVED/DIRECT_TRIPLE and the demo would lose
# its only REASONED_SUPPORTABLE. tau=0.4 sits in (0.333, 0.500): the single edge
# is rejected, the 2-hop path passes, and every other intended status is
# unaffected (the RETRIEVED claims score 0.71-1.00 and the FABRICATED claims
# score 0.0). See the run-2 comment for the paired phrasing adjustment.
# NOTE: 0.4 is calibrated to the LEXICAL gate's exact scores for these demo
# fixtures; the model-gate sweep (GR11) selects its own tau independently and
# must NOT inherit 0.4.
_CONFIG = GroundingConfig(
    k_hops=2,
    tau=0.4,
    entailment="lexical",
    linker="label_alias",
    extractor="rule_based",
)


def build_slice_examples() -> list[GroundingRun]:
    """Build and ground the 3 canned books slice examples.

    Returns a list of 3 GroundingRun objects in deterministic order.
    """
    snapshot = load_snapshot(_SNAPSHOT_DIR)

    # -----------------------------------------------------------------------
    # Example 1: The Glass Menagerie
    # Exercises: RETRIEVED/DIRECT_TRIPLE, RETRIEVED/TEXT_CONTENT, FABRICATED
    # -----------------------------------------------------------------------
    ref1 = assemble_reference(
        snapshot,
        author_books_content_labels([
            (
                "Q678832",
                "The Glass Menagerie is set in a small apartment in St Louis during the Great Depression",
                "description",
            ),
        ]),
    )
    # Canned answer (no generator call); grounded by the real GR9 pipeline.
    answer1 = (
        "Tennessee Williams wrote The Glass Menagerie. "
        "The Glass Menagerie is set in a small apartment during the Great Depression. "
        "The Glass Menagerie had its world premiere in New York in 1960."
    )
    run1 = ground_response(
        "Tell me about The Glass Menagerie.",
        answer1,
        ref1,
        active_perturbations=[],
        config=_CONFIG,
    )
    # Override run_id with a stable deterministic id
    run1 = run1.model_copy(update={"run_id": _RUN_IDS[0]})

    # -----------------------------------------------------------------------
    # Example 2: Pelevin shared-author (Blue Lantern & DTP(NN))
    # Exercises: REASONED_SUPPORTABLE/MULTI_HOP_PATH, RETRIEVED/TEXT_CONTENT, FABRICATED
    # Multi-hop path: Blue Lantern --[author]--> Victor Pelevin <--[author]-- DTP(NN)
    # -----------------------------------------------------------------------
    ref2 = assemble_reference(
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
    # c1: REASONED_SUPPORTABLE/MULTI_HOP_PATH -- 2-hop shared-author path
    #     Blue Lantern --[author]--> Victor Pelevin <--[author]-- DTP(NN).
    # c2: RETRIEVED/TEXT_CONTENT -- content label directly matches.
    # c3: FABRICATED -- wrong publisher (HarperCollins) and location (New York).
    #
    # AUTHORED-INPUT adjustment (GR9): the slice's c1 read "Blue Lantern and DTP
    # were both written by Pelevin." Under the real rule-based extractor +
    # label-alias linker that phrasing fails the demo two ways: the bare title
    # "DTP" does not link to the canonical node "DTP(NN)", so only ONE endpoint
    # resolves and the multi-hop stage is skipped; and the cue "were" captures the
    # tail "both written by Pelevin", tripping the value-absent spurious detector.
    # The phrasing below uses both canonical titles (so both endpoints link) and
    # the cue "were written by" (so the tail is just "Victor Pelevin", which IS on
    # the path premise) -- yielding a clean, non-spurious REASONED_SUPPORTABLE.
    # Paired with tau=0.4 (see _CONFIG) so the single author edge does not pre-empt
    # the 2-hop path.
    answer2 = (
        "Blue Lantern and DTP(NN) were written by Victor Pelevin. "
        "DTP(NN) is a novel by Victor Pelevin published in 2003 by Eksmo. "
        "Blue Lantern was published by HarperCollins in New York."
    )
    run2 = ground_response(
        "Tell me about Pelevin books.",
        answer2,
        ref2,
        active_perturbations=["pert-text-q105485274"],
        config=_CONFIG,
    )
    run2 = run2.model_copy(update={"run_id": _RUN_IDS[1]})

    # -----------------------------------------------------------------------
    # Example 3: Principles of Economics (Carl Menger)
    # Exercises: RETRIEVED/DIRECT_TRIPLE, RETRIEVED/TEXT_CONTENT, FABRICATED
    # FABRICATED: wrong city (Berlin instead of Vienna) and wrong year (1850 not 1871)
    # -----------------------------------------------------------------------
    ref3 = assemble_reference(
        snapshot,
        author_books_content_labels([
            (
                "Q4338113",
                "Principles of Economics introduced the concept of marginal utility and founded the Austrian School",
                "description",
            ),
        ]),
    )
    # c1: RETRIEVED/DIRECT_TRIPLE -- author edge (Carl Menger).
    # c2: RETRIEVED/TEXT_CONTENT -- marginal utility content label.
    # c3: FABRICATED -- Berlin (wrong; should be Vienna) and 1850 (wrong; should be 1871).
    answer3 = (
        "Carl Menger wrote Principles of Economics. "
        "Principles of Economics introduced the concept of marginal utility and founded the Austrian School. "
        "Principles of Economics was published in Berlin in 1850."
    )
    run3 = ground_response(
        "Tell me about Principles of Economics.",
        answer3,
        ref3,
        active_perturbations=[],
        config=_CONFIG,
    )
    run3 = run3.model_copy(update={"run_id": _RUN_IDS[2]})

    return [run1, run2, run3]


def emit_slice_runs(output_dir: Path | None = None) -> list[Path]:
    """Write the 3 slice GroundingRuns to output_dir (default: data/runs/).

    Returns the list of paths written.
    """
    out = output_dir or _RUNS_DIR
    out.mkdir(parents=True, exist_ok=True)

    runs = build_slice_examples()
    written: list[Path] = []
    for run in runs:
        path = out / f"{run.run_id}.json"
        path.write_text(run.model_dump_json(), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    paths = emit_slice_runs()
    for p in paths:
        print(f"Wrote {p}")
