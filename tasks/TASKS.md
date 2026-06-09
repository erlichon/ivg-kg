# TASKS — text/books build (the M-BOOKS spine)

> The **books** (text-content vs knowledge) build, decomposed into deliverable tasks. This is the
> guaranteed core and the only plan the build executes **first**. The science is in
> `../project_statement.md`; the build target is `../spec/SPEC-text.md` (§ refs point there).
> The **gated image axis is OUT of this file** — it lives in `TASKS-image-artwork.md` (primary)
> and `TASKS-image-taxa.md` (fallback) and is not opened until milestone **M-BOOKS**.
>
> Phase tags: P0/P1/P2 (build). Each task lists **Delivers** (acceptance), **SPEC**, **deps**.

---

## Execution protocol — `/subagent-driven-development`

This plan is executed with a **hybrid** of `superpowers:subagent-driven-development` (the code
build) and the **Workflow** harness (the data-parallel sweep). **Read this section before
dispatching anything.** It encodes the mechanism split, the models, the per-task review loop, the
**review-intensity tiers**, and the **Invariants kit** that the cold implementer agents do not
otherwise know.

### Execution mechanism by phase (hybrid)
**Rule of thumb:** writes source into the shared `src/ivg_kg` / `app` package →
`/subagent-driven-development` (sequential, file-safe, gated, interactive). Fans out over
independent units producing separate artifacts, or read-only → **Workflow** (parallel, resumable).

| Phase / task | Mechanism | Why |
| --- | --- | --- |
| **All code build** — S1–S2, DA1–DA4, PT1, UI1–UI5, GR1, GR3–GR11, TS1–TS2, EX3, authoring EX1/EX2 | **subagent-driven-development** | coupled multi-file package; needs interactive clarification, file-safe sequential commits, human P0/M-BOOKS gates. Never parallel-dispatch implementers. |
| **Experiment sweep — running EX4** | **Workflow** `pipeline()` | grounding *(question × manifest-entry)* is embarrassingly parallel; each run writes its own `data/runs/<id>.json`; resumable. The sweep *code* (GR11) is built by the skill; the *run* is the Workflow. |
| **Phase-boundary review panels** — P0 gate, M-BOOKS, final | **Workflow** (optional) | fan out parallel Opus reviewers (architecture ‖ simplicity ‖ alignment ‖ correctness) → synthesize. Read-only. |
| **Per-task review checkpoint** | **skill loop (below)** | implement→review→fix mutates the same files → sequential. |

### Roles & models
| Role | Model | What it does |
| --- | --- | --- |
| **Controller / orchestrator** | (the build session — capable model) | Reads this plan, dispatches one task at a time, curates each brief, tracks TodoWrite. Writes no code itself. |
| **Implementer / fixer** | **Sonnet 4.6** | One task via TDD, commits, self-reviews; later applies findings. **No access to our conversation** — gets only the curated brief. |
| **Reviewer (the checkpoint)** | **Opus 4.8** | Reviews each task: architecture, simplicity, alignment with the docs + Invariants kit, logical correctness. |

> ⚠️ **Implementer agents are Sonnet 4.6 and start cold.** Every brief MUST embed the relevant
> SPEC/statement sections **and the Invariants kit**, verbatim — never "read the plan and figure it
> out." Curate; do not delegate the curation.

### Per-task loop (with the Opus review checkpoint)
One implementer at a time (never two in parallel — file conflicts):
1. **Dispatch Sonnet 4.6 implementer** with the brief. It may ask questions first — answer fully.
   It works **test-first**, runs ruff+pytest, commits, self-reviews, reports
   `DONE`/`DONE_WITH_CONCERNS`/`NEEDS_CONTEXT`/`BLOCKED`.
2. **✦ Review checkpoint (Opus 4.8), looped ✦** — `APPROVED` or `CHANGES-REQUESTED` + findings.
   `CHANGES-REQUESTED` → fresh Sonnet fixer (findings verbatim) → re-review. Loop until `APPROVED`,
   no must-fix findings; **cap 4 rounds**, then escalate to the human.
3. Mark complete in TodoWrite; next task.

**Phase-boundary reviews (heavier):** whole-deliverable Opus review at **end of P0** (stop-and-review
gate), **at M-BOOKS**, and a **final** review before `superpowers:finishing-a-development-branch`.
**Worktree:** isolated branch/worktree (`superpowers:using-git-worktrees`); never on `main`.

### Review intensity tiers (put the loop where correctness lives)
Not applied uniformly — that would review scaffold as hard as the entailment gate.
- **Tier 1 — full adversarial loop (≤4 rounds):** **S2** (schema), **DA4** (grading reference),
  **PT1** (withhold semantics), **GR3** (the only place ablation happens), **GR7** (value-sensitive
  entailment), **GR8** (classifier), **GR9** (grade-against-reference wiring), **GR10**, **TS1**,
  **TS2**, **EX3** (deterministic leverage), **EX4** (the §6 controls must *pass*).
- **Tier 2 — single Opus review, fix-and-confirm if must-fix:** DA1, DA2, DA3, GR1, GR4, GR5, GR6,
  GR11, UI2, UI3, EX1, EX2.
- **Tier 3 — light single pass (Invariants + acceptance):** S1, UI1, UI4 charts, UI5.

Every task still gets **≥1 Opus pass** against the Invariants kit. The critical path
(`S1→S2→DA2→DA4→GR3→GR9→GR11→EX4`) is almost entirely Tier 1 — care where the schedule has no slack.

### Invariants kit — paste into EVERY implementer and reviewer brief
Non-obvious load-bearing decisions a cold agent will otherwise violate (from `SPEC-text.md` /
`project_statement.md`). If code contradicts one, it is wrong even if tests pass.

1. **Evidence vs. grading-reference split (the correctness spine, SPEC-text §3.2).** A
   `Perturbation` withholds evidence from the **generation context only**. Classification **always**
   grades against the full **grading reference** (KG-full triples + curated content labels),
   **never** the ablated context. A fact hidden from the generator must remain gradable.
2. **`RETRIEVED` = grounded in a *single* evidence item — a triple OR a content fact**
   (description / curated content label), `support_source` records which. Not triples-only. This is
   what lets content-only true claims grade grounded and flip RETRIEVED→FABRICATED under
   content-absence.
3. **Entailment gate is value-sensitive.** Premise = serialized reference evidence; hypothesis =
   claim (MiniCheck is **asymmetric — do not invert**). A claim asserting a value the evidence
   contradicts/omits **fails** → `FABRICATED` + `spurious_path=True`. Entity-match is not support.
4. **Path search is UNDIRECTED** (undirected view; `all_simple_paths`, 2..k hops), **excludes
   literal nodes as intermediate waypoints**, picks the **highest-entailment** path (not shortest).
   Retain stored edge direction in `PathEdge.traversed_forward`.
5. **Naming: `reasoned-supportable`, never `reasoned`.** We measure *supportability*, not cognition.
6. **No provider SDK in business logic.** All LLM access via `BaseAIClient`; local/open model is the
   POC default. Entity linker (`BaseEntityLinker`) and entailment gate (`BaseEntailmentGate`) are
   ABCs — program to them.
7. **Books-first hard gate.** Do **not** create, scaffold, or import any image-axis code or open the
   image task files (`TASKS-image-artwork.md`, `TASKS-image-taxa.md`) until **M-BOOKS** is validated.
8. **Demo-safety & determinism.** Live SPARQL is build-time only (cached, deterministic order,
   QLever fallback). Answers/claims/groundings precomputed + cached by input hash; only the repair
   loop makes a live call. Repair-leverage primary metric is **deterministic**.
9. **Schema discipline.** Pydantic v2, JSON-serializable (`dcc.Store`); NetworkX **rebuilt from
   JSON** (no pickle). `active_perturbations` is a **list**. `unresolved_entities` distinct from
   `FABRICATED`. Manifest fixed before inspection. The schema is **multimodal-ready** (image fields
   exist) but the text build does not populate them.
10. **Licensing.** Do **not** vendor CogMG (unlicensed) or GENRE (non-commercial); vendoring is
    limited to MIT VeGraph prompts; KGR reimplemented from the paper.
11. **UI correctness (SPEC-text §4.5).** Highlight the support path by **appending** stylesheet
    selectors — **never mutate the global stylesheet**. Panels read `dcc.Store` independently (**no
    circular callbacks**); `modified_timestamp` for initial-load reads.

### Brief templates
**Implementer (Sonnet 4.6):** paste the task entry + the exact SPEC-text excerpts it cites +
(if science matters) the statement excerpt + the **full Invariants kit**. Demand test-first, scope
discipline ("implement exactly this task; if the spec seems wrong, STOP/BLOCKED — don't 'fix' it"),
report a status + commit SHA(s).
**Reviewer (Opus 4.8):** review the diff on four axes (architecture / simplicity / alignment with
docs+kit / logical correctness); output `APPROVED` or `CHANGES-REQUESTED` with severity-tagged,
located, doc-referenced findings + concrete fixes; don't rewrite the code.
**Fixer:** fresh Sonnet 4.6 with task + kit + reviewer findings verbatim; minimal changes; re-run
tests; new SHA → re-review until `APPROVED`.

---

## Hard scheduling gate — books-first (enforced, not just intended)

**M-BOOKS (milestone):** books text-content-vs-knowledge is validated **end-to-end through P2** —
EX4's books runs complete *and* the §6 negative / false-claim / manipulation controls **PASS** (not
merely run; the **false-claim control** is the one that catches a broken entailment gate — a hard
gate criterion, not a checkbox).

**Rule:** **the image axis does not start before M-BOOKS.** It lives entirely in the separate files
`TASKS-image-artwork.md` (primary) and `TASKS-image-taxa.md` (fallback); do not open them until
M-BOOKS. This protects *schedule* — depth-first books, not breadth-first both-slices.

**Image-axis fallback chain (post-M-BOOKS, all curtailable):** **artwork first** → if its validity
gate fails *and* time remains, **taxa fallback** → else **books-only** (no core loss). See the image
task files + `../spec/SPEC-image-artwork.md` / `SPEC-image-taxa.md`.

**Dates.** **Personal target:** M-BOOKS by **2026-06-12** (early, self-imposed). **Real course
backstops:** demo + 5-min recording **2026-06-23**, scientific report **2026-06-25**, live
presentation **2026-06-27**. The ~2-week real runway makes the image axis a realistic gated target,
not an assumed drop — but books-first still governs; if M-BOOKS slips toward the real backstop, the
image axis is curtailed (artwork→taxa→drop) to protect the demo + write-up.

---

## Tasks (text/books)

### SCAFFOLD
- **S1 — Repo scaffold & tooling** · P0 · deps: — (root)
  *Delivers:* `pyproject.toml` (uv, py≥3.11, deps pinned by track), repo layout (SPEC-text §3.3),
  `.gitignore`, `ruff`+`pytest` config, `config.py` (band, k, tau, model ids, WDQS/QLever
  endpoints), CI lint+tests. *SPEC:* §3.3, §7, §9(P0-a).
- **S2 — Typed schema `schema.py`** · P0 · deps: S1
  *Delivers:* all pydantic v2 contracts in SPEC-text §4.2 — **the full multimodal-ready schema**
  (enums incl. Modality/SupportSource, KG shape incl. `image_path`, `GradingReference`,
  `GenerationContext`, `GroundingConfig`, per-claim log, `GroundingRun`); JSON round-trip test.
  Image fields exist but are unexercised by the text build. **Central contract.** *SPEC:* §4.2.

### DATA (books)
- **DA1 — Wikidata pull client `wikidata.py`** · P0 · deps: S1
  *Delivers:* WDQS client (UA, rate-limit, 429/5xx backoff, disk cache by query hash) + **QLever
  fallback**; property-type filter; `sitelink_band_filter` (pure, unit-tested). *SPEC:* §4.1.
- **DA2 — Graph store `graph_store.py`** · P0 · deps: S2, DA1
  *Delivers:* `build_snapshot(rows)→KGSnapshot`, JSON freeze/load (no pickle), NetworkX build,
  `nx_to_cyto_elements` adapter. *SPEC:* §4.1.
- **DA3 — Books slice pipeline + freeze `pipeline.py`** · P0 · deps: DA1, DA2
  *Delivers:* orchestrated pull→band-filter→build→freeze of **books KG-full** to
  `data/frozen/books/<id>/`; re-run content/structure-overlap check report. *SPEC:* §4.1, §8.
- **DA4 — Grading-reference assembly `reference.py`** · P0 · deps: S2, DA2
  *Delivers:* `GradingReference = KGSnapshot + list[ContentLabel]`; books content-only-label
  authoring helper; reference is never-ablated. *SPEC:* §4.1, §3.2.

### PERTURB
- **PT1 — Perturbation interface + manifest** · P0 · deps: S2
  *Delivers:* `Perturbation` ABC + registry + `AblationManifest`; `TextContentAbsence`,
  `KnowledgeAbsence`, and the `ImageContentAbsence` **class** (the generic withhold-the-image seam;
  its data/grading is the image axis, not built here); all `withhold` from the **generation
  context**; per-claim attribution by linked entity. *SPEC:* §4.4.

### UI
- **UI1 — Mock fixtures `mock/fixtures.py`** · P0 · deps: S2
  *Delivers:* a hardcoded `GroundingRun` (+ mock subgraph elements) covering all three statuses and
  a support path. *SPEC:* §3.3, §4.5.
- **UI2 — Dash three-panel skeleton** · P0 · deps: S2, UI1, PT1
  *Delivers:* `app/{app,layout,callbacks}.py` + `app/panels/{answer,subgraph,analytics}.py` (one
  `get_*_panel()` each); `dcc.Store(selected_claim)`; CB1 click→store, CB2 store→cytoscape path
  highlight, CB3 store→analytics; **controls from the perturbation registry**; **entity-detail pane
  shows the entity image when present** (P18; demo-visual even though not evidence — books covers /
  author images); fed by mock; **P0 grounding stub** (`backend.ground_response` raises
  `NotImplementedError`). *SPEC:* §4.5, §3.1(seam 3).
- **UI3 — Wire app to precomputed runs** · P1 · deps: UI2, GR11
  *Delivers:* app loads `data/runs/*.json`; question/condition selector. *SPEC:* §8, §4.5.
- **UI4 — Analytics panel (full) + Trust indicator** · P2 · deps: UI3, EX4, EX3
  *Delivers:* `app/charts/{status_dist,repair_history,coverage}.py` (one `make_*_figure()` each) —
  claim-status distributions, modality-coverage, repair-history + **leverage**; **a Trust-pillar
  indicator rendering `GroundingRun.error_rates`** (per-modality classifier error, always visible);
  bars start at y=0; node sizing by area. *SPEC:* §4.5, §4.6, §4.7.
- **UI5 — Repair-loop UI (CB4)** · P2 · deps: UI3, EX3
  *Delivers:* spot-fabricated→restore-evidence→regenerate→diff; the single live call. *SPEC:* §4.5, §4.6.

### GROUND (text/structure)
- **GR1 — LLM client abstraction `clients/`** · P1 · deps: S2
  *Delivers:* `BaseAIClient` ABC + `LocalModelClient` (open LLM, POC default) + `CloudAIClient`. No
  provider SDK in business logic. *SPEC:* §4.3. *(The VLM adapter is image-axis — `clients/vlm.py`
  is specced in `SPEC-image-artwork.md`, built post-M-BOOKS.)*
- **GR3 — Context assembly `context.py`** · P1 · deps: S2, PT1, DA4
  *Delivers:* build `GenerationContext` from full evidence, then apply `Perturbation.withhold` (the
  **only** place ablation happens). *SPEC:* §4.3, §3.2.
- **GR4 — Answer generation `generate.py`** · P1 · deps: GR1, GR3
  *Delivers:* `generate_answer(question, context, client)` + cache by `hash(question, context)`.
  *SPEC:* §4.3.
- **GR5 — Claim extraction `extract.py`** · P1 · deps: GR1
  *Delivers:* RefChecker `LLMExtractor` (offline) → atomic claims/triplets; vendored KGR/VeGraph
  prompt fallback; cached. *SPEC:* §4.3(A).
- **GR6 — Entity linking `link.py`** · P1 · deps: S2, DA2
  *Delivers:* `BaseEntityLinker`; `LabelAliasIndex` (default, offline) + `ReFinEDLinker` (opt);
  out-of-slice → `unresolved_entities`. *SPEC:* §4.3(B).
- **GR7 — Entailment gate `entailment.py`** · P1 · deps: S2
  *Delivers:* `BaseEntailmentGate`; **MiniCheck** text gate (premise=evidence, hypothesis=claim;
  **value-sensitive**). *(The visual probe for the image axis is specced in `SPEC-image-artwork.md`.)*
  *SPEC:* §4.3, §4.7.
- **GR8 — Classifier `classify.py`** · P1 · deps: S2, DA2, GR6, GR7
  *Delivers:* decision order (direct triple → content fact → **undirected** multi-hop path →
  fabricated); `all_simple_paths`, **literal-node exclusion**, **max-entailment** path; sets
  `status` + `support_source` + `spurious_path`. *SPEC:* §4.3(C).
- **GR9 — Grounding backend `backend.py` (real)** · P1 · deps: GR3, GR5, GR6, GR8, DA4
  *Delivers:* `ground_response(answer, reference, …)` wiring extract→link→classify into a
  `GroundingRun`, grading against the **reference (never the ablated context)**; replaces the P0
  stub. *SPEC:* §4.3, §3.2.
- **GR10 — Classifier-error accounting (books paths)** · P1 · deps: GR9, DA4
  *Delivers:* per-modality error for the **text-NLI** and **structure-path** gates on a held-out
  books sample; **`tau`/`k` tuned on a disjoint fold**. *(Image/label error is in the image axis.)*
  *SPEC:* §4.7.
- **GR11 — Precompute pipeline + runs store** · P1 · deps: GR4, GR9
  *Delivers:* batch script: (question × {full, manifest entry}) assemble→generate→ground →
  `data/runs/<run_id>.json`; deterministic, cached. *SPEC:* §8, §10.

### TEST
- **TS1 — §6 mechanical tests (P0 subset)** · P0 · deps: S2, DA1, PT1
  *Delivers:* sitelink-band filter test, composed-manifest attribution test, schema round-trip,
  grade-against-reference invariant scaffold. *SPEC:* §6.
- **TS2 — Classifier invariant tests + §6 controls wiring** · P1 · deps: GR8, GR9
  *Delivers:* undirected-path regression (`book→author←book`), spurious-shared-literal rejection,
  value-sensitive **false-claim rejection**, deterministic-leverage identity, **grade-against-
  reference invariant (full, vs the real backend)**; control harness callable from the precompute.
  *SPEC:* §6.

### EXP (books experiment)
- **EX1 — Question bank (books) · Phase A** · P2 · deps: DA3
  *Delivers:* fixed books bank — content-only questions (genre/form, tradition, scope, role) +
  knowledge questions; KGR-style tiers. *SPEC:* §5; statement §5.2.
- **EX2 — Ablation manifests (books) · Phase A** · P2 · deps: PT1, DA3
  *Delivers:* fixed `manifest.json` — text-content-absence + knowledge-absence; fixed before
  inspection. *SPEC:* §4.4, §5.1.
- **EX3 — Repair loop + leverage `RepairSession`** · P2 · deps: GR9, GR3
  *Delivers:* restore withheld evidence → re-ground; **deterministic** leverage (fabricated→grounded
  per atomic restore, aligned by `claim_id`); live-regen secondary (temp 0, N runs ±CI). *SPEC:* §4.6.
- **EX4 — Phase A BOOKS runs + controls + pilot (= M-BOOKS)** · P2 · deps: GR11, GR10, TS2, EX1, EX2
  *Delivers:* run precompute over books bank×manifests; **negative / false-claim / manipulation /
  modality-strength controls** on real data; empirical pilot (~10 q); per-slice claim-status
  distributions + fabrication shifts. **M-BOOKS is declared ONLY when these controls PASS — not
  merely run** (false-claim control non-negotiable). *SPEC:* §5, §6, §8.
- **EX6 — Case studies + write-up + deliverables** · P2 · deps: EX4 (+ image results if produced)
  *Delivers:* 2–3 end-to-end repair walkthroughs; **IEEE-VIS intermediate + scientific reports**
  including the mandated elements — teaser figure, three explicit contribution bullets, the
  **interaction-design figure as a simplified MMA-model Fig 1** (3 zones → ivg-kg), **Pike 2009**
  framing of the interaction section, **MMA-model mapping** + **Sacha 2014** knowledge-generation
  cycle in related work, ≥10 refs (≥5 from lecture slides); **5-min demo recording showing all
  features** (due 23 Jun); **GitHub link**; **per-member-contribution + AI-tool-attribution
  appendix**. *SPEC:* §8; statement §8, §11; `../course/DELIVERABLE-RUBRICS.md`.

### RES (research / external)
- **RES1 — Verify reference [7] (arXiv:2605.26362)** · any · deps: — · *owner: user*
  *Delivers:* confirm the PDF supports the §2 mechanism claim; lift the provisional flag (F6).
  *SPEC:* §12; statement §2.

---

## Dependency graph (adjacency) — text/books only (no gate cycle: image is external)
```
S1 ──► S2 ───────────────────────────────────────────┐
 │      ├─► GR1 ─► GR4, GR5                            │
 │      ├─► PT1 ─► GR3, UI2, EX2, TS1                  │
 │      ├─► UI1 ─► UI2                                 │
 │      └─► GR6 ─► GR8 ◄─ GR7                          │
 ├─► DA1 ─► DA2 ─► DA3 ─► EX1, EX2                     │
 │            └─► DA4 ─► GR3 ─► GR4, GR9               │
GR3,GR5,GR6,GR8,DA4 ─► GR9 ─► GR10, GR11, TS2, EX3    │
GR11 ─► UI3 ─► UI4, UI5 ;  EX3 ─► UI4, UI5            │
GR10, TS2, EX1, EX2, GR11 ─► EX4 (= M-BOOKS) ─► UI4, EX6
RES1 (independent)                                    ┘
         ═══ after M-BOOKS: open TASKS-image-artwork.md (then -taxa fallback) ═══
```

## Parallel execution waves (earliest-start)
- **Wave 0:** S1.
- **Wave 1:** S2 ‖ DA1 ‖ RES1.
- **Wave 2:** GR1 ‖ PT1 ‖ UI1 ‖ GR7 ‖ GR5 ‖ DA2.
- **Wave 3:** DA3 ‖ DA4 ‖ GR6 ‖ GR3 ‖ UI2 ‖ TS1.  → **P0 closes** when {S1,S2,DA1,DA2,DA3,DA4,PT1,UI1,UI2,TS1} done — **review gate**.
- **Wave 4 (P1):** GR4 ‖ GR8 → GR9 → {GR10 ‖ GR11 ‖ TS2}.  *(GR4 needs GR3 from Wave 3.)*
- **Wave 5:** UI3 ‖ EX1 ‖ EX2 ‖ EX3.
- **Wave 6 (P2):** EX4 (books runs + §6 controls + pilot) → **✦ M-BOOKS ✦** → {UI4 ‖ UI5 ‖ EX6}.
- **After M-BOOKS (separate files):** the gated image axis — artwork first, taxa fallback.

## Critical path
```
S1 → S2 → DA2 → DA4 → GR3 → GR9 → GR11 → EX4 → EX6
                         ▲ (GR6,GR7 → GR8 → GR9 parallel sub-spine)
```
The UI track runs entirely on mock (UI1→UI2) in parallel with the grounding track. The image axis
is off this path by construction (separate, post-M-BOOKS, curtailable).

## Notes
- **P0 is the stop-and-review deliverable.** Do not start real grounding (GR9) before that review.
- **RES1** blocks nothing in code; it lifts the statement's provisional flag.
- **Image axis:** after M-BOOKS, see `TASKS-image-artwork.md`; only on failure+time, `TASKS-image-taxa.md`.
