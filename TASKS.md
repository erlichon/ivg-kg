# TASKS — project plan decomposed from `SPEC.md`

> The full `ivg-kg` build, divided into deliverable tasks with dependencies, parallel tracks,
> and the critical path. Derived from `SPEC.md` (§ refs point there); the scientific intent is
> in `project_statement.md`. Each task lists **delivers** (acceptance), **SPEC**, **deps**.
> IDs are stable handles for wiring; phase tags are P0/P1/P2 (build) and A/B (experiment).
>
> **Tracks** (run concurrently): **SCAFFOLD**, **DATA**, **PERTURB**, **UI**, **GROUND**,
> **TEST**, **EXP** (experiment), **RES** (research). The hard serialization is small; most
> work fans out into 3–4 parallel tracks after the schema exists.

---

## Execution protocol — `/subagent-driven-development`

This plan is executed with a **hybrid** of `superpowers:subagent-driven-development` (the code
build) and the **Workflow** harness (the data-parallel sweep + review panels). **Read this section
before dispatching anything.** It encodes the mechanism split, the models, the per-task review
loop, and — most importantly — the **Invariants kit** that the implementer agents *do not
otherwise know*.

### Execution mechanism by phase (hybrid)

**Rule of thumb:** if a task **writes source into the shared `src/ivg_kg` / `app` package →
`/subagent-driven-development`** (sequential, file-safe, gated, interactive). If it **fans out over
independent units producing separate artifacts, or is read-only → Workflow** (parallel, resumable).

| Phase / task | Mechanism | Why |
| --- | --- | --- |
| **All code build** — S1–S2, DA1–DA6, PT1, UI1–UI5, GR1–GR11, TS1–TS2, EX3 (RepairSession), and authoring EX1/EX2 | **subagent-driven-development** | coupled multi-file package; needs interactive clarification, file-safe sequential commits, and the human P0/M-BOOKS gates. Never parallel-dispatch implementers. |
| **Experiment sweep — running EX4 (and EX5)** | **Workflow** `pipeline()` | grounding *(question × manifest-entry)* is embarrassingly parallel; each run writes its own `data/runs/<id>.json` (no shared mutable state); resumable. *Note:* the sweep **code** (GR11) is built by the skill; the **run** is the Workflow. |
| **Phase-boundary review panels** — P0 gate, M-BOOKS, final | **Workflow** (optional) | fan out parallel Opus reviewers across the four axes (architecture ‖ simplicity ‖ alignment ‖ correctness) → synthesize. Read-only, no file conflicts. |
| **Per-task review checkpoint** (every task) | **skill loop (below)** | implement→review→fix mutates the same files → inherently sequential; no parallelism to harvest. |

The Workflow phases inherit the **same Invariants kit and the same Opus-4.8 / Sonnet-4.6 split**
(reviewer/synthesis agents Opus; any fix agents Sonnet). The books-first gate still applies: the
**taxa portion of the EX4/EX5 sweep does not run until M-BOOKS**.

### Roles & models

| Role | Model | What it does |
| --- | --- | --- |
| **Controller / orchestrator** | (this session — capable model) | Reads this plan, dispatches one task at a time in a dependency-respecting order, curates each subagent's brief, tracks state in TodoWrite. Does **not** write code itself. |
| **Implementer / fixer** | **Sonnet 4.6** | Implements one task via TDD, commits, self-reviews; later applies reviewer findings. Has **no access to our conversation** — gets only the brief the controller hands it. |
| **Reviewer (the checkpoint)** | **Opus 4.8** | Reviews each task in a loop (below). Focus: **architecture, simplicity, alignment with `SPEC.md` / `TASKS.md` / `project_statement.md`, and logical correctness.** |

> ⚠️ **The implementer agents are Sonnet 4.6 and start cold.** They have none of the reasoning,
> trade-offs, or rejected alternatives behind this design. Every brief MUST embed the relevant
> SPEC/statement sections **and the Invariants kit below**, verbatim — never "read the plan and
> figure it out." Curate; do not delegate the curation.

### Per-task loop (with the Opus review checkpoint)

For each task, in dependency order (one implementer at a time — never dispatch two implementers in
parallel; they conflict on files):

1. **Dispatch the Sonnet 4.6 implementer** with the **Implementer brief** (template below). It may
   ask clarifying questions first — answer fully before it proceeds. It implements **test-first**
   (`superpowers:test-driven-development`), runs lint+tests, commits, self-reviews, and reports a
   status: `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`.
2. **✦ Review checkpoint (Opus 4.8), looped ✦** — dispatch the **Reviewer brief**. The reviewer
   returns `APPROVED` or `CHANGES-REQUESTED` + findings (severity-tagged).
   - If `CHANGES-REQUESTED`: dispatch a **Sonnet 4.6 fixer** (same task, the reviewer's findings
     verbatim) → re-dispatch the **same Opus reviewer** → repeat.
   - **Loop until the reviewer returns `APPROVED` with no remaining must-fix findings** (its four
     focus areas). Pure style nits are optional and must not block. **Cap: 4 rounds**, then the
     controller escalates to the human rather than looping forever.
3. **Only then** mark the task complete in TodoWrite and move to the next.

**Phase-boundary reviews (heavier):** in addition to per-task review, run a whole-deliverable Opus
review at each gate — **end of P0** (the stop-and-review gate), **at M-BOOKS** (books validated
end-to-end before any taxa work), and a **final whole-implementation review** before
`superpowers:finishing-a-development-branch`.

**Worktree:** run on an isolated branch/worktree (`superpowers:using-git-worktrees`), never
straight on `main`.

### Review intensity tiers (put the loop where correctness lives)

The per-task Opus loop is **not applied uniformly** — that would review scaffold as hard as the
entailment gate and let the apparatus consume the time the research needs. Tier each task:

- **Tier 1 — full adversarial loop (up to 4 rounds):** the correctness spine, where the Invariants
  live and passing tests do **not** prove correctness — **S2** (schema; everything depends on it),
  **DA4** (grading reference), **PT1** (withhold-from-context semantics), **GR3** (the only place
  ablation happens), **GR7** (value-sensitive entailment), **GR8** (decision order / undirected /
  literal-exclusion), **GR9** (grade-against-reference wiring), **GR10**, **TS1**, **TS2** (the
  controls + invariant tests themselves), **EX3** (deterministic leverage), **EX4** (the §6 controls
  must *pass*). Post-gate, **GR10T / DA6 / EX4T** are Tier 1 *if the image axis runs*.
- **Tier 2 — single Opus review, fix-and-confirm only if it finds must-fix:** integration/medium —
  DA1, DA2, DA3, GR1, GR4, GR5, GR6, GR11, UI2, UI3, DA5, GR2, EX1/EX1T, EX2/EX2T.
- **Tier 3 — light single pass (Invariants-kit + acceptance, no loop):** mechanical/cosmetic —
  S1, UI1, UI4 charts, UI5.

**Every task still gets ≥1 Opus pass against the Invariants kit** — a cold Sonnet agent can violate
an invariant even in "mechanical" code (a provider-SDK import in S1's deps, a pickled graph in DA2).
Tiering changes loop *depth*, never drops review to zero. Note the critical path
(`S1→S2→DA2→DA4→GR3→GR9→GR11→EX4`) is almost entirely Tier 1 by construction — care concentrates
exactly where the schedule has no slack.

### Invariants kit — paste into EVERY implementer and reviewer brief

These are the non-obvious, load-bearing decisions a cold Sonnet agent will otherwise violate. They
are derived from `SPEC.md`/`project_statement.md`; if code contradicts one, it is wrong even if
tests pass.

1. **Evidence vs. grading-reference split (the correctness spine, SPEC §3.2).** A `Perturbation`
   withholds evidence from the **generation context only**. Classification **always** grades
   against the full **grading reference** (KG-full triples + curated content labels), **never** the
   ablated context. A fact hidden from the generator must remain gradable.
2. **`RETRIEVED` = grounded in a *single* evidence item — a triple OR a content fact**
   (description / curated image label), with `support_source` recording which. Not triples-only.
   This is what lets content-only true claims grade grounded and flip RETRIEVED→FABRICATED under
   content-absence.
3. **Entailment gate is value-sensitive.** Premise = serialized reference evidence; hypothesis =
   claim (MiniCheck is **asymmetric — do not invert**). A claim asserting a value the evidence
   contradicts or omits **fails** the gate → `FABRICATED` + `spurious_path=True`. Entity-match is
   not support.
4. **Path search is UNDIRECTED** (run on an undirected view; `all_simple_paths`, 2..k hops),
   **excludes literal nodes as intermediate waypoints**, and picks the **highest-entailment** path
   (not the shortest). Retain stored edge direction in `PathEdge.traversed_forward`.
5. **Naming: `reasoned-supportable`, never `reasoned`.** We measure *supportability* (evidence
   exists in the graph), not the model's cognition. Do not reintroduce "reasoned".
6. **Image-content claims are graded by text NLI against the curated label — not the raster.** The
   fixed-template **visual probe is for constructing/verifying labels only**, never per-claim
   grading. Free-form **VLM-as-judge is rejected**.
7. **No provider SDK in business logic.** All LLM/VLM access goes through `BaseAIClient`; the
   local/open model is the POC default. Same for the entity linker (`BaseEntityLinker`) and
   entailment gate (`BaseEntailmentGate`) — program to the ABC.
8. **Books-first hard gate.** Do **not** create, scaffold, or import any taxa/image code
   (`taxa.py`, `clients/vlm.py`, image labels, EX5) until the books spine is validated end-to-end
   (M-BOOKS). If a task is tagged `post-M-BOOKS`, it does not start early — no exceptions.
9. **Demo-safety & determinism.** Live SPARQL is build-time only (cached, deterministic order,
   QLever fallback). Answers/claims/groundings are precomputed and cached by input hash; only the
   repair loop makes a live call. Repair-leverage primary metric is **deterministic**.
10. **Schema discipline.** Pydantic v2, JSON-serializable (for `dcc.Store`); NetworkX is **rebuilt
    from JSON** on load (no pickle). `active_perturbations` is a **list**. `unresolved_entities`
    (out-of-slice) is distinct from `FABRICATED`. The manifest is fixed before inspection.
11. **Licensing.** Do **not** vendor CogMG (unlicensed) or GENRE (non-commercial). Vendoring is
    limited to MIT VeGraph prompts; KGR is reimplemented from the paper.
12. **UI correctness (SPEC §4.5).** Highlight the support path by **appending** stylesheet
    selectors to the base stylesheet — **never mutate the global/default stylesheet**. Panels read
    the `dcc.Store` independently (**no circular callbacks**); use `modified_timestamp` for
    initial-load reads.

### Implementer brief — template (Sonnet 4.6)

```
You are implementing ONE task in the ivg-kg project. You have no prior context; everything you
need is here. Work test-first (write failing tests, then code), run ruff + pytest, commit, then
self-review. Ask any clarifying question BEFORE coding.

TASK: <paste the task's full entry from TASKS.md — id, Delivers/acceptance, SPEC refs, deps>

WHERE IT FITS: <1–3 sentences of scene-setting: what exists already, what depends on this>

READ (excerpts pasted below, do not go hunting): 
  - SPEC.md <the exact §sections this task cites>  [paste them]
  - project_statement.md <relevant §>              [paste if the science matters here]

INVARIANTS YOU MUST NOT VIOLATE: <paste the Invariants kit above>

SCOPE DISCIPLINE: implement exactly this task. Do NOT build other tasks' files, do NOT add
features not in the acceptance, do NOT widen interfaces. If you think the spec is wrong, STOP and
report (status BLOCKED) — do not "fix" it.

DELIVERABLE: the files named in the task + their tests, all green. Report status
DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED with a short summary and the commit SHA(s).
```

### Reviewer brief — template (Opus 4.8, the checkpoint)

```
You are the review checkpoint for ONE just-completed ivg-kg task. Independent, skeptical; you did
not write this code. Review the diff (commit SHAs: <…>) against four axes ONLY:
  1. ARCHITECTURE — does it fit the seams in SPEC §3 (ABCs, evidence-vs-reference split, registry)?
     No leaky abstractions, no provider SDK in business logic, no scope creep.
  2. SIMPLICITY — is this the simplest thing that satisfies the spec? Flag over-engineering,
     needless indirection, premature generality.
  3. ALIGNMENT — does it match SPEC.md / TASKS.md / project_statement.md AND the Invariants kit
     (pasted below)? Name any divergence with the doc section it violates.
  4. LOGICAL CORRECTNESS — does it actually do what the acceptance says? Trace the load-bearing
     paths (esp. the §3.2 grading-against-reference invariant and value-sensitive entailment).

TASK + ACCEPTANCE: <paste task entry>   SPEC excerpts: <paste>   INVARIANTS: <paste the kit>

OUTPUT: `APPROVED` (no must-fix findings) or `CHANGES-REQUESTED` with a numbered list, each tagged
[Critical|Major|Minor] + exact location + the doc section it violates + a concrete fix. Pure style
nits → tag [Nit] and do not block on them. Be concrete; do not rewrite the code yourself.
```

### Fixer dispatch

Re-dispatch the **same task** to a fresh Sonnet 4.6 agent with: the original task entry + the
Invariants kit + **the reviewer's findings verbatim** + "address every Critical/Major/Minor; keep
changes minimal; re-run tests; report the new SHA." Then re-dispatch the Opus reviewer. Repeat
until `APPROVED`.

### Ordering note

The dependency graph and waves below give *valid orderings*, not a license to dispatch implementers
concurrently. Execute **one implementer at a time** in any topological order consistent with
`deps` + the books-first gate. (True parallelism is possible only via separate worktrees per track;
default to sequential.)

---

## How to read the dependency graph

- A task can start when **all** its `deps` are done.
- Tasks with no path between them are **parallelizable**.
- `gated` = produced/reported only if the image-axis validity gate holds (SPEC §1, §4.7, §6);
  `curtailable` = first to cut under schedule pressure (Phase B).

---

## Hard scheduling gate — books-first (enforced, not just intended)

**M-BOOKS (milestone):** books text-content-vs-knowledge is validated **end-to-end through P2** —
EX4's books runs complete *and* the §6 negative / false-claim / manipulation controls **PASS** (not
merely run; the **false-claim control** is the one that catches a broken entailment gate, so it is a
hard gate criterion, not a checkbox).

**Rule (blocks regardless of technical deps):** **no taxa/image task may *start* before M-BOOKS.**
This gates the entire taxa/image track — **DA5, GR2, GR10T, DA6, EX1T, EX2T, EX4T, EX5**. (The
books/taxa task split means these are now *separate tasks* with `+M-BOOKS` deps, so the gate is
acyclic: no books-spine task depends on a `…T` task.) **M-BOOKS is a *scheduling* prerequisite**
that forces the safe spine to completion first — depth-first books, not breadth-first both-slices.
This is the single rule that protects *schedule* (the `gated`/`curtailable` tags only protect
*claims*).

**Dated backstop:** the deadline is **2026-06-14** (5-day runway from 2026-06-09). If M-BOOKS is not
met by **2026-06-12 (T-2)**, the image axis is **dropped to future work** (statement §10 fallback —
no loss to the books core), leaving the final two days for EX6 (write-up + demo video). This
converts the documented "curtail first" option into a triggered action. *Reality note: a 5-day
runway makes the image axis a stretch; assume it drops and treat any taxa work as bonus.*

**Relaxation (conscious only):** the gate assumes a single focused track. It may be relaxed *only*
if a **dedicated second contributor** owns the taxa branch end-to-end without touching the books
spine — not by default, and never by letting taxa scaffolding into the books critical path.

---

## Tasks

### SCAFFOLD
- **S1 — Repo scaffold & tooling** · P0 · deps: — (root)
  *Delivers:* `pyproject.toml` (uv, py≥3.11, deps pinned by track), repo layout (SPEC §3.3),
  `.gitignore`, `ruff`+`pytest` config, `config.py` (band, k, tau, model ids, WDQS/QLever
  endpoints), CI runs lint+tests. *SPEC:* §3.3, §7, §9(P0-a).
- **S2 — Typed schema `schema.py`** · P0 · deps: S1
  *Delivers:* all pydantic v2 contracts in SPEC §4.2 (enums, KG shape, `GradingReference`,
  `GenerationContext`, `GroundingConfig`, per-claim log, `GroundingRun`), JSON round-trip test.
  **Central contract — most tracks depend on this.** *SPEC:* §4.2.

### DATA
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
- **DA5 — Taxa slice pull + freeze `taxa.py`** · post-M-BOOKS · `gated` · deps: DA1, DA2, **+M-BOOKS (books-first gate)**
  *Delivers:* `P31=Q16521 + P181` enumeration, **non-redundancy filter** (drop taxa with
  `P9714`/`P183`/`P2341`), image fetch + **SVG→PNG rasterize**, freeze to `data/frozen/taxa/<id>/`.
  *SPEC:* §4.1. (Parallel with DA3.)
- **DA6 — Taxa image-fact labels (curated)** · post-M-BOOKS · `gated` · deps: DA5, GR2(VLM), GR7(probe), **+M-BOOKS**
  *Delivers:* `content_labels.json` for taxa — image facts turned into text labels (visual-probe
  assist) then **double-labelled / spot-checked**; IAA reported. *SPEC:* §4.7, §4.1.

### PERTURB
- **PT1 — Perturbation interface + manifest** · P0 · deps: S2
  *Delivers:* `Perturbation` ABC + registry + `AblationManifest` (serialize/`from_json`);
  `TextContentAbsence`, `KnowledgeAbsence`, `ImageContentAbsence`; all `withhold` from the
  **generation context**; per-claim attribution by linked entity. *SPEC:* §4.4.

### UI
- **UI1 — Mock fixtures `mock/fixtures.py`** · P0 · deps: S2
  *Delivers:* a hardcoded `GroundingRun` (+ mock subgraph elements) covering all three statuses
  and a support path, for skeleton development. *SPEC:* §3.3, §4.5.
- **UI2 — Dash three-panel skeleton** · P0 · deps: S2, UI1, PT1
  *Delivers:* `app/{app,layout,callbacks}.py` + `app/panels/{answer,subgraph,analytics}.py` (one
  `get_*_panel()` each); `dcc.Store(selected_claim)`; CB1 click→store, CB2 store→cytoscape path
  highlight, CB3 store→analytics; **controls from the perturbation registry**; fed by mock. Also
  the **P0 grounding stub** (`backend.ground_response` raises `NotImplementedError`).
  *SPEC:* §4.5, §3.1(seam 3).
- **UI3 — Wire app to precomputed runs** · P1 · deps: UI2, GR11
  *Delivers:* app loads `data/runs/*.json` (real `GroundingRun`s) instead of mock; question/
  condition selector. *SPEC:* §8, §4.5.
- **UI4 — Analytics panel (full)** · P2 · deps: UI3, EX4, EX3
  *Delivers:* `app/charts/{status_dist,repair_history,coverage}.py` (one `make_*_figure()` each)
  feeding the analytics panel — claim-status distributions, modality-coverage, repair-history +
  **leverage** — on real runs. *SPEC:* §4.5, §4.6.
- **UI5 — Repair-loop UI (CB4)** · P2 · deps: UI3, EX3
  *Delivers:* spot-fabricated→restore-evidence→regenerate→diff interaction; the single live call.
  *SPEC:* §4.5, §4.6.

### GROUND
- **GR1 — LLM client abstraction `clients/`** · P1 · deps: S2
  *Delivers:* `BaseAIClient` ABC + `LocalModelClient` (open LLM, POC default) + `CloudAIClient`
  (generic). No provider SDK in business logic. *SPEC:* §4.3.
- **GR2 — VLM client `clients/vlm.py`** · post-M-BOOKS · `gated` · deps: GR1, **+M-BOOKS (books-first gate)**
  *Delivers:* `VLMClient` (Qwen2.5-VL via MLX) for image-grounded generation + visual-probe assist.
  *SPEC:* §4.3, §2.2.
- **GR3 — Context assembly `context.py`** · P1 · deps: S2, PT1, DA4
  *Delivers:* build `GenerationContext` from full evidence, then apply `Perturbation.withhold`
  (the **only** place ablation happens). *SPEC:* §4.3, §3.2.
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
  **value-sensitive**); fixed-template **visual probe** for label QA (not per-claim grading).
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
  books sample; **`tau`/`k` tuned on a disjoint fold**. (Image/label error is GR10T, post-M-BOOKS —
  split out so the books spine does not depend on taxa labels.) *SPEC:* §4.7.
- **GR10T — Image error & reference-label accounting** · post-M-BOOKS · `gated` · deps: GR10, DA6, **+M-BOOKS**
  *Delivers:* visual-probe error vs hand labels; taxa image-label **double-labelling + IAA**.
  *SPEC:* §4.7.
- **GR11 — Precompute pipeline + runs store** · P1 · deps: GR4, GR9
  *Delivers:* batch script: for (question × {full, manifest entry}) assemble→generate→ground →
  `data/runs/<run_id>.json`; deterministic, cached. *SPEC:* §8, §10.

### TEST
- **TS1 — §6 mechanical tests (P0 subset)** · P0 · deps: S2, DA1, PT1
  *Delivers:* sitelink-band filter test, composed-manifest attribution test, schema round-trip,
  grade-against-reference invariant scaffold. *SPEC:* §6.
- **TS2 — Classifier invariant tests + §6 controls wiring** · P1 · deps: GR8, GR9
  *Delivers:* undirected-path regression (`book→author←book`), spurious-shared-literal rejection,
  value-sensitive **false-claim rejection**, deterministic-leverage identity, **grade-against-
  reference invariant (full, vs the real backend — closes the TS1 scaffold)**; control harness
  callable from the precompute. *SPEC:* §6.

### EXP (experiment)

> **Books/taxa split (resolves the gate cycle):** the Phase-A bank, manifests, error accounting,
> and runs are split into a **books** half (pre-gate, feeds M-BOOKS) and a **taxa-image** half
> (`…T`, post-M-BOOKS). Nothing on the books spine may depend on a `…T` task or on DA5/DA6/GR2.

- **EX1 — Question bank (books) · Phase A** · P2/A · deps: DA3
  *Delivers:* fixed books bank — content-only questions (genre/form, tradition, scope, role) +
  knowledge questions; KGR-style tiers. *SPEC:* §5, statement §5.2.
- **EX1T — Question bank (taxa image) · Phase A** · post-M-BOOKS · `gated` · deps: DA5, **+M-BOOKS**
  *Delivers:* taxa range/distribution questions answerable only from the map + knowledge questions.
  *SPEC:* §5.
- **EX2 — Ablation manifests (books) · Phase A** · P2/A · deps: PT1, DA3
  *Delivers:* fixed `manifest.json` for books — text-content-absence + knowledge-absence; fixed
  before inspection. *SPEC:* §4.4, §5.1.
- **EX2T — Ablation manifests (taxa image) · Phase A** · post-M-BOOKS · `gated` · deps: PT1, DA5, **+M-BOOKS**
  *Delivers:* fixed `manifest.json` for taxa — image-content-absence + knowledge-absence; fixed
  before inspection. *SPEC:* §4.4, §5.1.
- **EX3 — Repair loop + leverage `RepairSession`** · P2 · deps: GR9, GR3
  *Delivers:* restore withheld evidence → re-ground; **deterministic** leverage (fabricated→
  grounded per atomic restore, aligned by `claim_id`); live-regen secondary (temp 0, N runs ±CI).
  *SPEC:* §4.6.
- **EX4 — Phase A BOOKS runs + controls + pilot (= M-BOOKS)** · P2/A · deps: GR11, GR10, TS2, EX1, EX2
  *Delivers:* run precompute over the books bank×manifests; **negative / false-claim / manipulation
  / modality-strength controls** on real data; empirical pilot (~10 q); per-slice claim-status
  distributions + fabrication shifts. **M-BOOKS is declared ONLY when these controls PASS — not
  merely run.** The **false-claim control especially** is non-negotiable: it is the one that catches
  a broken value-sensitive entailment gate that would pass every other test. "Runs finished" ≠
  M-BOOKS. *SPEC:* §5, §6, §8.
- **EX4T — Phase A TAXA image runs + validity gate** · post-M-BOOKS · `gated` · deps: EX4, EX1T, EX2T, DA6, GR10T, GR2, **+M-BOOKS**
  *Delivers:* run precompute over the taxa image bank×manifests; image-content-vs-knowledge
  per-slice results; **evaluate the image validity gate** (non-redundancy + visual-probe error) —
  pass ⇒ report; fail ⇒ drop the image axis. *SPEC:* §5, §6, §8.
- **EX5 — Phase B: within-taxa three-way** · P2/B · `gated`,`curtailable` · deps: EX4T, EX3, EX1T, EX2T
  *Delivers:* same-entity image/text/structure ablations on taxa → unconfounded cross-modality
  contrast; modality-strength caveat reported. **Cut first if time is short.** *SPEC:* §1, §5.
- **EX6 — Case studies + write-up + demo video** · P2 · deps: EX4 (+EX4T/EX5 if done)
  *Delivers:* 2–3 end-to-end repair walkthroughs; IEEE-VIS report; 5-min backup video.
  *SPEC:* §8; statement §8, §11.

### RES (research / external)
- **RES1 — Verify reference [7] (arXiv:2605.26362)** · any · deps: — · *owner: user*
  *Delivers:* confirm the PDF exists and supports the §2 mechanism claim; lift the "provisional"
  flag (the open **F6**). *SPEC:* §12; statement §2.

---

## Dependency graph (adjacency)

```
PRE-GATE (books spine + shared infra):
S1 ──► S2 ─────────────────────────────────────────────┐
 │      ├─► GR1 ─► GR4, GR5                              │
 │      ├─► PT1 ─► GR3, UI2, EX2, TS1                    │
 │      ├─► UI1 ─► UI2                                   │
 │      └─► GR6 ─► GR8 ◄─ GR7                            │
 ├─► DA1 ─► DA2 ─► DA3 ─► EX1, EX2                       │
 │            └─► DA4 ─► GR3 ─► GR4, GR9                 │
GR3,GR5,GR6,GR8,DA4 ─► GR9 ─► GR10, GR11, TS2, EX3      │
GR11 ─► UI3 ─► UI4, UI5                                  │
GR10, TS2, EX1, EX2, GR11 ─► EX4  (= M-BOOKS)            │
EX3 ─► UI4, UI5 ;  EX4 ─► UI4, EX6                       │
RES1 (independent)                                       │
                                                         │
══ books-first gate — nothing below STARTS before M-BOOKS ══
DA5 ─► EX1T, EX2T, DA6 ;  GR2, GR7 ─► DA6 ;  GR10T ◄─ GR10, DA6 │
EX4, EX1T, EX2T, DA6, GR10T, GR2 ─► EX4T ─► EX5 ◄─ EX3  ─┘
(image VALIDITY gate evaluated inside EX4T; fail ⇒ drop DA5/GR2/GR10T/DA6/EX1T/EX2T/EX4T/EX5)
```

## Parallel execution waves (earliest-start)

- **Wave 0:** S1.
- **Wave 1 (after S1):** S2 ‖ DA1 ‖ RES1.
- **Wave 2 (after S2):** GR1 ‖ PT1 ‖ UI1 ‖ GR7 ‖ GR5 ‖ DA2(needs DA1). *(GROUND, UI, DATA, PERTURB fan out here.)*
- **Wave 3:** DA3 ‖ DA4 ‖ GR6 ‖ GR3 ‖ UI2 ‖ TS1.  → **P0 closes** when {S1,S2,DA1,DA2,DA3,DA4,PT1,UI1,UI2,TS1} done — **review gate**.
- **Wave 4 (P1):** GR4 ‖ GR8 → GR9 → {GR10 ‖ GR11 ‖ TS2}.  *(GR4 needs GR3 from Wave 3.)*
- **Wave 5:** UI3 ‖ EX1 ‖ EX2 ‖ EX3.
- **Wave 6 (P2/A — books spine):** EX4 (books runs + §6 controls + pilot) → **✦ M-BOOKS ✦** → {UI4 ‖ UI5 ‖ EX6 may begin}.
- **Wave 7 (post-M-BOOKS — gated, curtailable taxa/image):** DA5 ‖ GR2 → {EX1T ‖ EX2T ‖ DA6} → GR10T → EX4T → EX5. **Dropped wholesale if M-BOOKS misses its dated backstop, or if the image validity gate fails inside EX4T.**

*(DA5/GR2 are technically startable earlier but are **held to Wave 7 by the books-first gate**.)*

## Critical path (longest chain)

```
S1 → S2 → DA2 → DA4 → GR3 → GR9 → GR11 → EX4 → EX6
                         ▲
        (GR6,GR7 → GR8 → GR9 is the parallel grounding sub-spine)
```
Everything else (UI track, taxa/image track, extraction, clients) has slack against this spine —
so a second contributor on UI or the image axis does not extend the critical path.

## Notes & seams

- **Hard serialization is only S1→S2→(DA2|GR-spine)→GR9→EX4.** With the schema (S2) fixed, the
  **UI track runs entirely on mock** (UI1→UI2) in parallel with the whole grounding track; the
  **image/taxa track** (DA5/GR2 → EX1T/EX2T/DA6 → GR10T → EX4T → EX5) is an isolated, gated,
  curtailable branch with no edge into the books spine.
- **Two distinct gates:** (1) the **books-first *start* gate (M-BOOKS)** — no taxa task starts
  until books is validated end-to-end through P2 (Hard scheduling gate above); (2) the **image
  *validity* gate** — evaluated inside **EX4T** (non-redundancy + visual-probe error); if it fails,
  drop DA5/GR2/GR10T/DA6/EX1T/EX2T/EX4T/EX5. Either gate failing leaves the books text-vs-knowledge
  spine complete (fallback, no core loss).
- **P0 is the stop-and-review deliverable** (SPEC §9). Do not start GR-track real grounding (GR9)
  before that review.
- **RES1 (verify [7])** blocks nothing in code; it only lifts the statement's provisional flag.
