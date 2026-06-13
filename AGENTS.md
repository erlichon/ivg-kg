# AGENTS.md — ivg-kg project index

> Auto-loaded into Claude Code via a one-line `CLAUDE.md` containing `@AGENTS.md` (Claude Code reads
> CLAUDE.md, not AGENTS.md directly). **Agents may maintain THIS file**; `CLAUDE.md` is a guard-protected
> one-line import (do not write it). Read **FOCUS.md** first, then this file. Keep this index current.

## What this is

**ivg-kg** — an **MMA4AI instrument** (UvA MSc *Multimedia Analytics* course project, IEEE-VIS short-paper
framing). An interactive Plotly/Dash visual-analytics tool that grounds each LLM claim against a **frozen
local Wikidata slice**, classifies it **retrieved / reasoned-supportable ("Supportable") / fabricated** with
a **deterministic verifier**, and drives an **Overview -> Inspection -> Repair** loop. The *instrument* is the
contribution, not an ML result ("probing, not prompting"). Scientific spine: **absence-induced hallucination**.

**Contributions, built in this order (decreasing robustness):**
- **C1 — the instrument** (robust; build first; earns the grade even if the sweep finds nothing).
- **C2 — the absence finding** (offline sweep; distribution shift by withheld-evidence modality).
- **C3 — the agreement quadrant** (observational support-frequency vs causal absence-shift at KG-triple grain; upside).

## Source of truth & read order

1. **FOCUS.md** — the one-page contribution/focus/cut-list. The fastest orientation.
2. **project_statement.md** — the LOCKED scientific source of truth. **Never edit without explicit user
   approval**; propose changes as redlines in **STATEMENT-CHANGES.md**.
3. **spec/** — the implementation contract:
   - `SPEC-text.md` — books core + the shared typed schema (§4.2) + grounding (§4.3) + perturbation (§4.4) +
     interface (§4.5) + classifier-error (§4.7) + diagnostics (§4.8) + honesty layer (§4.9). **§4.2 schema is
     THE contract between backend and UI.**
   - `SPEC-image-artwork.md`, `SPEC-image-taxa.md` — the committed image axis (built post-M-BOOKS).
4. **tasks/** — the build plan: `TASKS.md` (books core; task IDs, deps, dependency graph, waves, Invariants
   kit), `TASKS-image-artwork.md`, `TASKS-image-taxa.md`.
5. **decisions/** — dated rationale records (deep-research, focus-decision panel, trust-views, novelty
   fact-check, course-grounding, MMA review, artwork non-redundancy gate). The "why" behind the design.
6. **course/** — `MMA-MODEL.md` (the Worring MMA model the interface maps onto), `COURSE-DISTILLATION.md`
   (lectures), `DELIVERABLE-RUBRICS.md` (what's graded), `INSPIRATION-2024-25.md` (prior-year takeaways).

## Code map (P0 is built; real backend is a stub)

- `src/ivg_kg/` — `schema.py` (pydantic v2 — the contract), `config.py`, `diagnostics.py`,
  `data/` (code: graph_store / pipeline / reference / wikidata), `grounding/` (backend; **real grounding
  is a NotImplementedError stub — filled by task GR9**), `mock/` (fixtures the UI is built against),
  `perturbation/`.
- `data/frozen/books/books-p0-v1/` — the **frozen local Wikidata slice** the project grounds against
  (`snapshot.json` + `overlap_report.json`); `data/runs/` and `data/cache/` are gitkeeped outputs.
- `app/` — Dash app: `app.py` (entry), `layout.py`, `callbacks.py`, `theme.py`, `assets/`,
  `panels/{answer,subgraph,analytics,repair}.py`, `charts/{status_dist,support_frequency}.py`.
- `tests/` (schema, perturbation, pipeline, graph_store, reference, wikidata, fixtures, app, config,
  §6 controls) + `conftest.py`; CI runs on push (`.github/workflows/ci.yml`).
- `pyproject.toml` (uv), `Taskfile.yml`, `README.md` (prereqs + run instructions); `MOCKUP-WALKTHROUGH.md`
  + `screenshots/` (the running P0 mock UI). Run/dev/test via the Taskfile.

## LOCKED invariants — DO NOT VIOLATE

- **Encoding:** **hue encodes STATUS only** (3-grade palette, used identically everywhere). New marks use
  ORTHOGONAL channels — pattern (fabricated!=false hatch), shape (epistemic glyphs), border, size, position.
- **Generator vs verifier:** generator = sampled local LLM (stochastic, produces a CoT draft). Verifier =
  **DETERMINISTIC** (NLI gate **DeBERTa-v3-large live / MiniCheck-7B offline** + symbolic multi-hop path
  search), a **different model family**, **not an LLM, no chain-of-thought**, and **always grades vs the FULL
  reference**. The verifier's "reasoning" is a faithful proof chain (Provenance Card), not a narration.
- **Two perturbation layers (distinct grading):** *withhold-from-context* (RQ2 absence experiment — hide from
  the generation context only; the item STAYS in the grading reference; grade vs FULL) vs *edit-the-KG*
  (gap-repair — changes the ground truth; grade vs the CURRENT KG). Never conflate.
- **Two analysis modes:** single-run (one answer; per-claim status; **NO SE** — one sample) and multi-run
  (N=20 default; status **mean +/- SE** over runs; per-KG-item **support-frequency** = OBSERVATIONAL, not
  causal). Claims are NOT aligned across runs; only KG-item IDs are.
- **repair_leverage** = deterministic COUNT of claims flipping fabricated->grounded on restore + re-run,
  paired by claim-text SEMANTIC matching (NOT raw claim_id), reported NET of the no-repair re-run baseline.
- **Honesty layer (the trust contribution):** two-tier **data-agnostic trust** (instrument-level = NLI
  benchmark accuracy + per-claim margin-to-tau, an "uncalibrated reliability prior"; deployment-level = error
  CALIBRATED on a curated gold QA set — reserve "calibrated" for this tier); "fabricated != false" overlay;
  Provenance Card; epistemic glyph grammar (observed / intervened / n=1). Trust strip is ALWAYS-ON.
- **Reported numbers** come from the **offline precompute** (never the live path).
- **Novelty = the composition, NOT the primitives.** We do not invent causal attribution (ContextCite) nor
  the cited!=relied phenomenon (Attention-is-not-Explanation); the novelty is the KG-triple-grain
  observational-vs-causal agreement taxonomy + deterministic verifier + interactive + repair, as one instrument.
- **Multimodal is COMMITTED** (sequenced after the books core); only the cross-modality *contrast* is upside.
  The image validity gate ROUTES the domain (artwork -> verified-taxa floor), it never drops the modality.
- **Books-first hard gate:** do NOT scaffold/implement/import any image-axis CODE until M-BOOKS is validated.
  (Reading/planning the image specs/tasks + the filed artwork-gate result is allowed.)

## Build conventions

- Python 3.11+, **uv**; Dash 2.x + dash-cytoscape; NetworkX; pydantic v2. CPU/MPS-friendly; local models only;
  demo is offline-reproducible (precomputed). Hardware target: Apple Silicon, 48 GB, MPS.
- **The §4.2 schema is the contract.** Backend and UI build to it independently and meet there.
- **Stub-first:** build/extend the UI against `src/ivg_kg/mock/` fixtures FIRST (off the backend's critical
  path), swap in the real backend (GR9) later — so C1 is demoable regardless of pipeline timing.
- **LLM abstraction:** all answer GENERATION goes through one ABC (`BaseAIClient`) with no provider SDK in
  business logic; concrete backends are config-selected (local / Ollama / API), and the interface is designed
  so a future `ClaudeCodeClient` (with an optional evidence trace) can slot in. The VERIFIER is a SEPARATE,
  deterministic, different-family abstraction — never the generator verifying itself.
- **Strictly ASCII** in code, comments, and academic prose (no emoji / unicode artifacts) — anti-AI-artifact
  rule. Terse, technical comments.
- Separation: data / layout / callbacks; one `get_*_panel()` / `make_*_figure()`; no circular callbacks;
  cytoscape path-highlight by APPENDING stylesheet selectors (never mutate the global stylesheet).

## Process & git

- **Commits:** human contributor as author; **NO AI/Claude co-author trailer** (AI use is disclosed in the
  report's appendix per course rules, not in commit messages). Do NOT stage `.claude/`, `.claire/`, `.DS_Store`.
  Push to `main` is authorized (SSH remote `github.com-erlichon`); rebase onto `origin/main` if it has moved.
- **project_statement.md is locked** — redlines go in STATEMENT-CHANGES.md; edit only on explicit approval.
- Significant design decisions get a dated record in **decisions/**; the Invariants kit in TASKS.md is pasted
  into implementer briefs.

## Status & timeline

- P0 (mock UI + schema + stubs) is built and on `main`. Real grounding backend = GR9 (pending).
- The intermediate report has been submitted; **final report due 2026-06-25**, **demo 2026-06-23**,
  **presentation 2026-06-27**. The report (TASKS EX6) is **co-authored** — per-stream sections, not one person.
- 4-person team; work is divided across four streams (backend / data+experiments / UI / report+eval+image),
  with the report sections spread across all four. See TASKS.md waves + the stub-first parallelization.

## Where to start a build session

Read FOCUS.md -> the relevant SPEC section -> the task entry (TASKS.md) for your task ID -> build to the
§4.2 schema. Honor the LOCKED invariants above. UI work starts on `src/ivg_kg/mock/` fixtures.
