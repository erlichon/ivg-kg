# M-BOOKS Run Book

One-command offline precompute path for the M-BOOKS experiment.
All reported numbers come from this path (Invariant #22).
The lexical gate is for CI and fixture smoke tests ONLY -- it must NEVER
source a reported number.

---

## Prerequisites

### 1. Install Ollama and pull Qwen2.5 (the generator)

    brew install ollama          # or https://ollama.com/download
    ollama serve &               # start the local server
    ollama pull qwen2.5          # Qwen2.5-7B-Instruct (~4.7 GB)

### 2. Install grounding extras (torch + transformers for MiniCheck-7B)

    uv sync --extra grounding

MiniCheck-7B (bespokelabs/Bespoke-MiniCheck-7B, ~15 GB) downloads automatically
on the first verifier call in Step 1 below.
Requires Apple-Silicon (MPS), ~48 GB RAM.

---

## Step 1 -- Calibrate (deployment trust tier)

Runs the lexical-calibrated gold QA set through the real MiniCheck-7B verifier,
sweeps tau on the calibration fold, freezes the operating point, and writes the
calibrated reliability_report.json.  The frozen_tau this produces is the
M-BOOKS operating tau used in Step 2.

    uv run python scripts/emit_calibration_report.py --gate minicheck

Output: data/frozen/books/books-p0-v1/reliability_report.json
        (calibrated=true, gate="minicheck", frozen_tau=<value>)

Reserve "calibrated" for this tier only -- the lexical default produces
calibrated=false and is the committed demo artifact for CI.

---

## Step 2 -- Run the sweep

Runs the full M-BOOKS offline precompute sweep:
  - Generator: Qwen2.5 via Ollama (seeded, stochastic generator).
  - Verifier:  MiniCheck-7B offline (deterministic, different model family).
  - Questions: the frozen question_bank.json (all 3 conditions: full,
    content-absent, knowledge-absent) + the no-repair baseline.
  - Grading:   ALWAYS against the FULL GradingReference (Invariant #1).
  - tau:       read from reliability_report.json (the calibrated operating point
    produced in Step 1; override with --tau if needed).

    uv run python scripts/run_books_sweep.py --n-runs 20

Output: data/runs/<item_id>--<condition>--sN.json  (gitignored, do not commit)

Note: this takes minutes to hours on a local model depending on hardware.
The reported numbers in the paper come from THIS offline path.

---

## Step 3 -- RQ2 figure

Produces the modality-contrast aggregate figure (INTERVENTIONAL_AGGREGATE stamp
plus noise floor from the calibration report).

    uv run python scripts/emit_rq2_figure.py

Output: data/figures/rq2_modality_contrast.*

---

## Step 4 -- Section-6 controls (the gate)

Runs the false-claim non-negotiable gate.  Must print OVERALL: PASS.
Exits non-zero on failure.

    uv run python scripts/run_section6_controls.py

M-BOOKS is declared DONE when this step PASSES.

---

## Smoke path (no models required -- offline/CI)

Validates wiring without Ollama or MiniCheck.
Uses the CannedStubClient and the lexical gate.

    uv run python scripts/run_books_sweep.py --stub --gate lexical --n-runs 1

This path is also exercised by the test suite:

    uv run pytest tests/test_run_books_sweep.py -q

---

## Full command sequence summary

    # Prerequisites (one-time)
    ollama serve &
    ollama pull qwen2.5
    uv sync --extra grounding

    # Step 1: calibrate
    uv run python scripts/emit_calibration_report.py --gate minicheck

    # Step 2: sweep
    uv run python scripts/run_books_sweep.py --n-runs 20

    # Step 3: figure
    uv run python scripts/emit_rq2_figure.py

    # Step 4: gate (must pass)
    uv run python scripts/run_section6_controls.py

---

## Invariants

- Invariant #1: grading ALWAYS uses the full GradingReference; perturbations
  withhold only from the generation context.
- Invariant #14: generator (Qwen2.5/Ollama) and verifier (MiniCheck-7B) are
  different model families; the generator never verifies its own output.
- Invariant #22: ALL reported numbers come from the offline MiniCheck-7B
  precompute (Step 2).  The lexical gate is for CI/fixtures only.
