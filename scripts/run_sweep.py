"""Run a tiny offline precompute sweep (GR11) over the frozen books slice.

This is a deterministic, OFFLINE demonstration of the sweep harness
(src/ivg_kg/experiment/sweep.py). It:

  1. loads the frozen books-p0-v1 snapshot + the committed question_bank.stub.json,
  2. builds the FULL GradingReference (snapshot + a couple of TEXT content labels),
  3. runs a small sweep (n_runs=2) over {full, content-absent, knowledge-absent}
     plus the matched no-repair baseline, using a CANNED stub generator (no model
     download, no network) and the LEXICAL entailment gate, and
  4. writes the runs to data/runs/.

The sweep output files use the '<item_id>--<condition>--sN.json' naming, which is
NOT 'slice-*', so they are correctly gitignored and must NOT be committed (only the
committed data/runs/slice-*.json fixtures are tracked).

Determinism: the seed scheme + the canned (seed-varying) stub + the deterministic
lexical verifier mean two runs of this script produce byte-identical output.

Usage:
    uv run python scripts/run_sweep.py
"""

from __future__ import annotations

from pathlib import Path

from ivg_kg.data.graph_store import load_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.experiment.question_bank import load_question_bank
from ivg_kg.experiment.sweep import run_sweep, write_runset
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.schema import Condition, GenerationContext, GroundingConfig

_SNAPSHOT_DIR = Path(__file__).parent.parent / "data" / "frozen" / "books" / "books-p0-v1"
_BANK_PATH = _SNAPSHOT_DIR / "question_bank.stub.json"
_RUNS_DIR = Path(__file__).parent.parent / "data" / "runs"

# LEXICAL gate: the OFFLINE deterministic verifier (no torch, no download). The
# model-gate sweep would select its own tau; tau=0.4 here is only a demo value.
_CONFIG = GroundingConfig(
    k_hops=2,
    tau=0.4,
    entailment="lexical",
    linker="label_alias",
    extractor="rule_based",
)


class CannedStubClient(BaseAIClient):
    """Offline canned generator: a fixed grounded answer with a seed-varying tail.

    The grounded sentence is stable so claims are deterministic; only an inert
    bracketed suffix varies by seed, which keeps the sweep honest about seeding
    without requiring any real model.
    """

    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        answer = (
            "The Glass Menagerie author Tennessee Williams. "
            "The Glass Menagerie genre drama. "
            f"[draw seed={seed}]"
        )
        return GenerationResult(answer=answer)


def main() -> None:
    snapshot = load_snapshot(_SNAPSHOT_DIR)
    reference = assemble_reference(
        snapshot,
        author_books_content_labels(
            [
                ("Q678832", "The Glass Menagerie is a memory play", "description"),
            ]
        ),
    )
    bank = load_question_bank(_BANK_PATH)
    client = CannedStubClient()

    runset = run_sweep(
        bank,
        reference,
        client,
        conditions=[
            Condition.FULL,
            Condition.CONTENT_ABSENT,
            Condition.KNOWLEDGE_ABSENT,
        ],
        n_runs=2,
        config=_CONFIG,
    )
    paths = write_runset(runset, out_dir=_RUNS_DIR)
    print(
        f"Swept {len(bank.items)} questions x {len(runset.conditions)} conditions "
        f"x n_runs={runset.n_runs} (+ no-repair baselines) -> {len(paths)} runs"
    )
    print(
        f"Wrote {len(paths)} run files to {_RUNS_DIR} "
        "(gitignored '<item_id>--<condition>--sN.json'; do not commit)"
    )


if __name__ == "__main__":
    main()
