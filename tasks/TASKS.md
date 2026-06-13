# TASKS — text/books build (the M-BOOKS spine)

> The **books** (text-content vs knowledge) build, decomposed into deliverable tasks. This is the
> guaranteed core and the only plan the build executes **first**. The science is in
> `../project_statement.md`; the build target is `../spec/SPEC-text.md` (§ refs point there).
> The **committed image axis is OUT of this file** — it is **sequenced** (not curtailable) after
> M-BOOKS and lives in `TASKS-image-artwork.md` (primary) and `TASKS-image-taxa.md` (verified floor);
> those files are not OPENED until milestone **M-BOOKS** (sequencing, not optionality).
>
> Phase tags: P0/P1/P2 (build). Each task lists **Delivers** (acceptance), **SPEC**, **deps**.

---

## MMA4AI framing & priorities (read first; SPEC-text §0 framing, FOCUS)

This is an **MMA4AI instrument** (*probing, not prompting*; one main action = **analyze**), built by
Worring's recipe (purpose+audience -> architecture -> **define scores** -> visualize -> coordinate
views). The instrument's **scores** are **STATUS** (retrieved / Supportable / fabricated),
**support-frequency**, **repair_leverage**, and **verifier-error**; the §4 components render them. Two
agents (statement §6): the sampled LLM/VLM is the **Generate/Analyze agent**; the deterministic
verifier is the **Analysis VA-Agent** whose contract is a faithful rationale = the **Provenance Card**
(GR9/§4.9b). Guidance posture: **Orienting + Directing, NOT Prescriptive**.

**Requirements skeleton (R1/R2/R3 = the Overview -> Inspection -> Repair state machine; FOCUS report-fix #1).**
- **R1 — Overview.** Take in a whole answer's grounding at a glance: the status distribution + the
  support-frequency map as the overview surface (no projection — see UI4 DEFER). Tasks: UI2, UI4, EX5.
- **R2 — Inspection.** Drill into a single claim's verdict and *why* it rests on what it rests on:
  support-path highlight, Provenance Card, Trust strip, epistemic glyphs. Tasks: UI2, UI4, UI5, GR8/GR9.
- **R3 — Repair.** Close the loop — add the missing fact, re-run, measure `repair_leverage`. Tasks:
  UI5, EX3.

**Contribution priority (build in this order; FOCUS C1/C2/C3).**
- **C1 — the instrument (robust; build FIRST; earns the grade even if the sweep finds nothing).**
  Grounding + deterministic verifier + Overview->Inspection->Repair loop + the **honesty layer**
  (Trust strip, Provenance Card, `fabricated != false` overlay, epistemic glyph grammar; §4.9). The
  honesty layer is part of C1, not an add-on. Built against MOCK fixtures first (stub-first; see below).
- **C2 — the absence finding (the science; medium risk; needs the offline sweep).** RQ2 distribution
  shift across {full, content-withheld, knowledge-withheld}; **within-modality** claim is promised, the
  **cross-modality CONTRAST is quarantined** as future upside. Tasks: GR11, EX4.
- **C3 — the agreement quadrant (upside; highest risk; must NOT drive the schedule).** Observational
  support-frequency vs interventional absence-shift. The **delivered novelty** (instrument +
  taxonomy-as-a-lens + **repair_leverage** standalone) ships regardless; the **populated quadrant** is
  the cuttable empirical finding — delivered only as a capped **pilot** (EX5). 

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
| **All code build** — S1–S2, DA1–DA4, PT1, UI1–UI6, GR1, GR3–GR11, TS1–TS2, EX3, EX5, authoring EX1/EX2 | **subagent-driven-development** | coupled multi-file package; needs interactive clarification, file-safe sequential commits, human P0/M-BOOKS gates. Never parallel-dispatch implementers. |
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
  entailment), **GR8** (classifier), **GR9** (grade-against-reference wiring), **GR10** (gold QA set +
  reliability curve), **TS1**, **TS2**, **EX3** (repair-leverage = semantic-matched flip count net of
  the no-repair baseline), **EX5** (two-mode diagnostics: single-run status %, multi-run status
  mean+/-SE, support-frequency semantics, epistemic_level tagging), **EX4** (the §6 controls must
  *pass*; verifier-error noise floor; hard-entity control), **UI6** (the honesty layer — C1's defining
  property: Provenance Card faithful/no-LLM-narration, hue=STATUS-only orthogonal channels, the 3-glyph
  grammar, two-tier trust wording).
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
7. **Books-first hard gate.** Do **not** scaffold, implement, or import any image-axis **code/modules**
   until **M-BOOKS** is validated. **Reading/planning the image task docs**
   (`TASKS-image-artwork.md`, `TASKS-image-taxa.md`) and the already-filed IA0 preliminary
   non-redundancy result (`decisions/2026-06-12-artwork-nonredundancy-gate.md`) **is explicitly
   allowed** — the gate is on building image code, not on reading the plan.
8. **Demo-safety & determinism.** Live SPARQL is build-time only (cached, deterministic order,
   QLever fallback). Answers/claims/groundings precomputed + cached by input hash; live calls are the
   repair loop (edit-the-KG + re-run) and opt-in live multi-run. **Verification (the gate) is
   deterministic given a fixed answer text**; reported figures come from frozen scenarios.
9. **Schema discipline.** Pydantic v2, JSON-serializable (`dcc.Store`); NetworkX **rebuilt from
   JSON** (no pickle). `active_perturbations` is a **list**. `unresolved_entities` distinct from
   `FABRICATED`. Manifest fixed before inspection. The schema is **multimodal-ready** (image fields
   exist) but the text build does not populate them.
10. **Licensing.** Do **not** vendor CogMG (unlicensed) or GENRE (non-commercial); vendoring is
    limited to MIT VeGraph prompts; KGR reimplemented from the paper.
11. **UI correctness (SPEC-text §4.5).** Highlight the support path by **appending** stylesheet
    selectors — **never mutate the global stylesheet**. Panels read `dcc.Store` independently (**no
    circular callbacks**); `modified_timestamp` for initial-load reads.
12. **Encoding (SPEC-text §4.5).** **Hue encodes STATUS** — one fixed 3-grade palette
    (Retrieved / Supportable / Fabricated; long term `reasoned-supportable`) used identically in every
    panel. Multiple selected claims are distinguished by **outline + numeric badge, never by hue**.
    The status filter is over the **three grades**; "proposed" is the input universe, not a fourth grade.
13. **Two modes; claims NOT aligned across runs (SPEC-text §4.5/§4.8).** **Single-run** = one
    answer's status %/counts, **no SE** (one sample), + per-claim support-path highlight + per-claim
    status, **plus two interactive demos: REMOVE-from-context → re-run → fabricate (qualitative RQ2);
    ADD-to-KG → re-run → flip-to-grounded + repair_leverage (RQ3)**. **Multi-run** (N=20 default, N
    selectable, **FULL condition only — NO condition selector**) = (a) FULL-condition status
    **mean +/- SE** of the **answer-level per-run fraction** (computed per run, then mean+SE across
    runs; reproducibility of grounding); (b) **support-frequency** per KG node/triplet = fraction of N
    runs the item was **used** (lies on the support path of >=1 grounded claim) — **observational, NOT
    causal**. The content-vs-knowledge contrast (RQ2) is the **offline bank aggregate** (a report
    figure), NOT an interactive toggle. **Claims are NOT aligned across runs; only stable KG-item IDs
    are** — that is why this design is simpler. `repair_leverage`
    (RQ3, EX3) = **count** of claims flipping FABRICATED→grounded on restore (edit-the-KG) + **re-run**,
    paired **within one answer's before/after by claim-TEXT SEMANTIC matching** (fuzzy/normalized dedup,
    **NOT raw `claim_id`** — regeneration rewrites the answer), reported **net of a matched no-repair
    re-run baseline** (regeneration-based, not deterministic re-grounding; see #21).
    Classification is **deterministic given a fixed answer text**; **reported figures
    come from frozen scenarios**, live multi-run is opt-in and never the source of reported numbers.
14. **Generator vs verifier roles (SPEC-text §4.3).** The **generator is stochastic & seeded**
    (sampled, temp ~0.7, `seed=f(question_id,condition,sample_index)`, N runs/condition); the
    **verifier is deterministic & a DIFFERENT model family** (no self-verification — correlated blind
    spots otherwise). Every verifier-side LLM stage (extraction) is **pinned greedy (temp 0)**;
    persist the **raw `entailment_score`** (margin to `tau` = confidence); float32 + fixed batch order
    on MPS. **Never describe per-run variance as "verifier runs"** — all per-run variance is
    *generation* variance. Verifier choice is **accuracy-first**: **DeBERTa-v3-large on the LIVE path**
    (the live path DOES verify live), **MiniCheck-7B for offline precompute/calibration**; **cache
    verification by distinct evidence-pair**.
15. **Two perturbation operations only, distinct grading (SPEC-text §4.4/§4.8).** **REMOVE** (a
    description or a triplet) = withhold from the **GENERATION CONTEXT only**; the verifier / grading
    reference is **ALWAYS the full reference and is NEVER ablated**. **ADD** (a true missing fact) = to
    the **KG** (changes both generation context and grading reference) → repair / `repair_leverage`.
    **We NEVER remove from the verifier; there is no per-edit SCOPE contrast and no "generation-only
    add".** REMOVE tests whether the model NEEDS the evidence; ADD REPAIRS the KB. The
    withhold-from-context MECHANISM (`TextContentAbsence`/`KnowledgeAbsence`) is **retained for the
    offline sweep** — only the interactive per-question condition selector and the SCOPE contrast were
    removed. **RQ2 is quantified via the offline bank aggregate** (question bank x N runs x {full,
    content-withheld, knowledge-withheld}, graded vs full reference; a report figure); **the
    interactive tool shows RQ2 only qualitatively (the single-run REMOVE demo)**. There is **no
    `absence_leverage` / `fabrication_induction` scalar** and **no per-claim stability / slot / variant
    machinery** — these are dropped. Multi-run proportions carry `SE=sqrt(p(1-p)/N)` (not the ~0.5
    Bernoulli std); **N=20 is a floor**.
16. **Support-frequency is observational, not causal (SPEC-text §4.8).** `support_frequency[id]` =
    fraction of N runs a KG node/triplet was **used** (lies on the support path of >=1 grounded
    claim). It measures "how often grounding routes through this item", **NOT** causal leverage.
    Never describe it as a causal/leverage metric.
17. **Hue = STATUS only; the honesty marks ride ORTHOGONAL channels (SPEC-text §4.5, §4.9).** The
    new honesty-layer marks **never recolor**: `fabricated != false` rides the **pattern (hatch)**
    channel (out-of-slice claims only), the epistemic glyphs ride the **shape** channel, borderline/
    margin rides the **border** channel, and the per-claim badge owns **one glyph slot** (priority:
    repaired-evidence wrench > spurious-reason > none). Status keeps the hue channel exclusively.
18. **Trust strip is ALWAYS-ON; two-tier, data-agnostic (SPEC-text §4.7, §4.9a).** The
    **instrument-level** read = NLI gate published benchmark accuracy (an **uncalibrated reliability
    prior**) + per-claim **margin to `tau`** (a confidence proxy, **NOT** calibration); the
    **deployment-level** read = error **calibrated on the curated gold QA set** for the loaded slice
    (computed for books). Reserve the word **"calibrated" for the deployment tier only**. BYO-KG with
    no labels degrades gracefully to the instrument prior + a "not calibrated to your KG" caveat.
19. **Provenance Card is FAITHFUL — no LLM narration (SPEC-text §4.9b).** Every sentence is a typed
    trace field over the verifier's deterministic proof chain (extraction -> link outcome -> cascade
    rung -> winning premise -> score/`tau`/margin -> KG revision graded against). It is shown BESIDE
    the generator CoT, which is labelled **"stated, not necessarily faithful"**. Never generate the
    rationale with an LLM; faithfulness is by construction.
20. **Epistemic glyph grammar: exactly 3 glyphs, 1 legend (SPEC-text §4.9d).** **open circle** =
    observational (support-frequency); **filled triangle + interval** = interventional aggregate (the
    offline sweep); **outlined "n=1" triangle** = single-sample demo (single-run REMOVE/ADD delta).
    Schema-enforced: `SingleRunStatusSummary.epistemic_level = SINGLE_SAMPLE`,
    `AnswerDiagnostics.epistemic_level = OBSERVATIONAL`, the sweep figure stamped `INTERVENTIONAL_AGGREGATE`.
    No per-view variants; causal/quadrant language only past the uncertainty gate.
21. **repair_leverage is paired by SEMANTIC claim-text match + NET of the no-repair baseline
    (SPEC-text §4.6/§4.8).** The FABRICATED->grounded flip count is paired within one answer's
    before/after by **claim-TEXT semantic matching** (fuzzy/normalized dedup), **NOT raw `claim_id`**
    (the ADD re-run regenerates the answer). The reported figure is **net of a matched no-repair
    re-run baseline** (re-run without the edit), so flips from re-sampling alone are subtracted.
    `claim_id` stays a within-run opaque id everywhere else.
22. **Reported numbers come from the OFFLINE precompute (SPEC-text §4.3, §10).** Verifier =
    **DeBERTa-v3-large on the LIVE path / MiniCheck-7B offline**; **ALL reported/figure numbers come
    from the offline precompute (MiniCheck-7B)**. The live path verifies live but is never the source
    of reported numbers, so the verifier-model choice does not affect reproducibility.
23. **Image axis is COMMITTED, sequenced post-M-BOOKS (SPEC-text §1; image specs).** The image axis is
    a **commitment, not curtailable**: its validity gate **routes the image DOMAIN (artwork -> taxa),
    never abandons the modality**. **Only the cross-modality CONTRAST is quarantined** as future
    upside. Do not frame the image axis as "drop to books-only". (Invariant #7 still holds: do not
    OPEN the image files before M-BOOKS — committed, but still sequenced second.)

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

**Rule:** **the image axis does not start before M-BOOKS** — but it is **committed, not curtailable**
(SPEC-text §1; image specs). It lives entirely in the separate files `TASKS-image-artwork.md`
(primary) and `TASKS-image-taxa.md` (verified floor); do **not** scaffold, implement, or import any
image-axis **code/modules** until M-BOOKS — but **reading/planning those docs and the filed IA0 result
(`decisions/2026-06-12-artwork-nonredundancy-gate.md`) is allowed** (the gate is on building image code,
not on reading the plan). This is **sequencing** (depth-first books, then image), not optionality — the
modality is delivered either way.

**Image-axis DOMAIN-routing chain (post-M-BOOKS; the gate routes the domain, never drops the axis):**
**artwork first** → if its **pre-registered non-redundancy gate** fails, **route to the verified taxa
floor**, which guarantees an image axis by construction. **Only the cross-modality CONTRAST is
quarantined** as future upside — the image axis itself is never abandoned. See the image task files +
`../spec/SPEC-image-artwork.md` / `SPEC-image-taxa.md`.

**Dates.** **Personal target:** M-BOOKS by **2026-06-12** (early, self-imposed). **Real course
backstops:** demo + 5-min recording **2026-06-23**, scientific report **2026-06-25**, live
presentation **2026-06-27**. The ~2-week real runway makes the committed image axis a realistic
sequenced second phase; books-first still governs the *order*. If M-BOOKS slips toward the real
backstop, the gate routes the image **domain** (artwork → taxa-verified-floor) rather than dropping
the modality, protecting both the image commitment and the demo + write-up.

---

## Tasks (text/books)

### SCAFFOLD
- **S1 — Repo scaffold & tooling** · P0 · deps: — (root)
  *Delivers:* `pyproject.toml` (uv, py≥3.11, deps pinned by track), repo layout (SPEC-text §3.3),
  `.gitignore`, `ruff`+`pytest` config, `config.py` (band, k, tau, model ids — separate generator vs
  verifier model ids, the verifier a **different family**; **verifier is accuracy-first: DeBERTa-v3-large
  live / MiniCheck-7B offline** — WDQS/QLever endpoints), CI lint+tests.
  *SPEC:* §3.3, §7, §9(P0-a).
- **S2 — Typed schema `schema.py`** · P0 · deps: S1
  *Delivers:* all pydantic v2 contracts in SPEC-text §4.2 — **the full multimodal-ready schema**
  (enums incl. Modality/SupportSource/**Condition**/**`EpistemicLevel`** {OBSERVATIONAL,
  INTERVENTIONAL_AGGREGATE, SINGLE_SAMPLE}, KG shape incl. `image_path`, `GradingReference`,
  `GenerationContext`, `GroundingConfig`, per-claim log with **`spurious_reason`** (within-run
  `claim_id`; **no slot_key/claim_key**), `GroundingRun` with **`condition`/`sample_index`** and
  **`baseline_run_id: str|None`** (a perturbed run points at its pre-perturbation baseline — the
  durable before/after pairing for the single-run REMOVE/ADD delta, §4.5/CHANGE-2), and the
  two-mode diagnostics **`SingleRunStatusSummary`** (with **`epistemic_level = SINGLE_SAMPLE`**) /
  **`StatusMeanSE`** / **`AnswerDiagnostics`** (with **`epistemic_level = OBSERVATIONAL`**) +
  **`RepairResult`** (`restored_item`, `repair_leverage: int`)); the `epistemic_level` fields are the
  **schema-enforced glyph contract** (§4.9d). JSON round-trip test. Image/diagnostics fields exist but
  the diagnostics aggregates are populated in P2 (EX5); the text build leaves image fields unexercised.
  **Central contract.**
  *SPEC:* §4.2, §4.8, §4.9d.

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
> **STUB-FIRST SEQUENCING (de-risk — read before the UI wave).** The UI is built against the existing
> **MOCK fixtures FIRST** (UI1): the **schema (S2) is the contract**, so the whole instrument (C1) —
> three panels, honesty layer, both analytics modes — is demoable on mock **before the real backend
> (GR9) exists**. The real runs (GR11) are swapped in later at UI3. Consequence for scheduling: the UI
> track (UI1 -> UI2 -> UI6) can **start and progress in parallel with the grounding track** and does
> **not** block on GR9 — so **C1 (the instrument) is demoable even if the grounding pipeline slips**.
> Only UI3 onward needs real runs. This is reflected in the dependency graph + waves below.

- **UI1 — Mock fixtures `mock/fixtures.py`** · P0 · deps: S2
  *Delivers:* a hardcoded `GroundingRun` (+ mock subgraph elements) covering all three statuses and
  a support path; **plus mock honesty-layer fields** so the C1 UI is demoable pre-GR9: an
  out-of-slice claim (`unresolved_entities` set, for the `fabricated != false` hatch), a borderline
  claim (`entailment_score` near `tau`), a `spurious_path`+`spurious_reason` claim, a multi-hop
  Supportable claim with a `grounding_path`, a populated `error_rates`, and a `baseline_run_id`-paired
  before/after run pair (mock REMOVE delta). *SPEC:* §3.3, §4.5, §4.9.
- **UI2 — Dash three-panel skeleton** · P0 · deps: S2, UI1, PT1
  *Delivers:* `app/{app,layout,callbacks}.py` + `app/panels/{answer,subgraph,analytics}.py` (one
  `get_*_panel()` each); `dcc.Store(selected_claim)`; CB1 click→store, CB2 store→cytoscape path
  highlight, CB3 store→analytics; **status filter over the three grades** (#1) and **multi-claim
  select with outline+badge** (#2); **hue=status, identity=outline+badge** (never overload hue);
  **controls from the perturbation registry**; subgraph shows **1st-degree neighbourhood under a node
  cap** (#3/#8) and **node-tap → zoom + entity-detail bottom pane** (#7) (P18; demo-visual even though
  not evidence — book covers / author images) **which is also the host slot for the per-claim
  Provenance Card** (built in UI6); fed by mock; **P0 grounding stub**
  (`backend.ground_response` raises `NotImplementedError`).
  - *Also (orthogonal-channel scaffolding, §4.5/§4.9, all against mock):* an **always-on Trust strip
    slot** in the Analytics column (filled out in UI6); the **`fabricated != false` hatch overlay**
    on out-of-slice claims (claims with `unresolved_entities` — **pattern channel**, keeps the
    fabricated hue, tooltip "unsupported by this KG slice — entities not in slice; may be true in the
    world"); the **border channel** for the borderline/margin chip; and **one glyph slot** per claim
    badge (priority: repaired-evidence wrench > spurious-reason > none). **Hue stays STATUS** — every
    new mark rides pattern/shape/border (Invariants #17).
  *SPEC:* §4.5, §4.9, §3.1(seam 3).
- **UI3 — Wire app to precomputed runs** · P1 · deps: UI2, GR11
  *Delivers:* app loads `data/runs/*.json`; **question selector** (FULL-condition runs for the
  interactive modes — no per-question condition toggle; the {content-withheld, knowledge-withheld}
  runs feed the offline RQ2 aggregate, not an interactive selector). *SPEC:* §8, §4.5.
- **UI4 — Analytics panel (two modes) + Trust indicator** · P2 · deps: UI3, EX4, EX3, EX5
  *Delivers:* `app/charts/{status_dist,repair_history,coverage,support_frequency}.py` (one
  `make_*_figure()` each), with a **single-run / multi-run mode toggle**. **Single-run:** the one
  run's **status %/counts** (no SE) + per-claim support-path highlight + per-claim status + **two
  interactive demos: (a) REMOVE a description/triplet from the generation context → re-run → watch
  the answer fabricate (qualitative RQ2); (b) ADD a true missing fact to the KG → re-run → watch the
  claim flip to grounded + show the repair_leverage count (RQ3)**.
  The single-run REMOVE/ADD demos must show a **BEFORE → AFTER status delta** (do NOT re-render in
  place; pairing via `baseline_run_id`) — wired in UI5; the delta is stamped the **n=1 outlined-triangle
  glyph** and `repair_leverage` rides a **size/glyph channel** (CHANGE-4), never prose.
  **Multi-run (#5, N selectable, default 20, FULL condition):** the **FULL-condition status
  distribution as mean +/- SE** column chart (answer-level per-run fractions; reproducibility of
  grounding) + **support-frequency** rendered as **node-size/edge-weight** on the subgraph
  (observational, NOT causal) **stamped with the open-circle epistemic glyph**; modality-coverage;
  repair-history + the **repair-leverage count** (size/glyph channel). **(#CHANGE-3) The
  support-frequency LIST is the SELECTOR into inspection** — render a ranked support-frequency list
  whose items, when clicked, load that run/item into single-run inspection
  (projection-that-is-a-selector); this list also **serves the Overview role** (no projection — see
  DEFER below). **Drop the multi-run condition selector** {full / content-withheld /
  knowledge-withheld} — the modality contrast (RQ2) is the offline sweep aggregate (EX4), reported as a
  figure, NOT an interactive toggle. **Prominent small-N caveat** (SE of a proportion; N=20 a floor).
  Bars start at y=0; node sizing by area. **Drop slot-anchored card / variant list / stability /
  per-condition stacked-bar.** The full two-tier **Trust strip**, the **gate-coverage gauge**, and the
  **3-glyph epistemic legend** are built in **UI6** and hosted in this panel (always-on).
  - **DEFER-WITH-DEFENSE — NO projection overview (NON-TASK; SPEC-text §4.5, FOCUS CUT list).** Do
    **NOT** build a t-SNE/UMAP claim-embedding projection overview: grounding status is a *relational*,
    not *semantic*, property, so claim embeddings do not separate by status — it would be decorative.
    The **support-frequency map/list serves the Overview role** instead. Record its absence with the
    one-line report defense; cut nothing else.
  *SPEC:* §4.5, §4.6, §4.7, §4.8.

- **UI6 — Honesty layer (Trust strip + Provenance Card + epistemic glyphs)** · P2 · deps: UI2, GR9, GR10, EX5
  *Delivers:* the §4.9 honesty layer — **C1's defining property** (the instrument shows its own error
  first; correlation never reads as causation). Data-agnostic by design (renders for any loaded KG).
  - **(a) Always-on, two-tier Trust strip (§4.9a, §4.7).** **Instrument-level** (shown for **any** KG,
    always): the NLI gate's **published benchmark accuracy** = an **uncalibrated reliability prior** +
    the per-claim **margin to `tau`** (`|entailment_score - tau|`, a **confidence proxy, NOT
    calibration**) with a borderline dashed-border + "borderline" chip (border channel) and an optional
    read-only **τ-sweep** what-if lens. **Deployment-level** (shown **when labels exist**): error
    **calibrated on the curated gold QA set** for the slice (books: computed; from GR10
    `error_rates`). **Reserve the word "calibrated" for the deployment tier only.** BYO-KG with no
    labels **degrades gracefully** to the instrument prior + "not calibrated to your KG" + a "label N
    claims to calibrate" affordance.
  - **(b) Provenance Card — FAITHFUL, NO LLM narration (§4.9b).** A per-claim collapsible card in the
    entity-detail sub-pane (UI2 host slot), **shown BESIDE the generator CoT** (the CoT labelled
    **"stated, not necessarily faithful"**). Every sentence is a **typed trace field** over the
    verifier's deterministic proof chain: extraction → entity-link outcome (incl. "unresolved → never
    reached the gate") → cascade **rung** → **winning premise** → **score / `tau` / margin** → **KG
    revision graded against**. Carries the **why-fabricated slot-diff** (VALUE-mismatch vs MISSING-fact
    → "add this fact?" link into the §4.6 repair flow) and propagates two badges to Answer/Subgraph
    (one glyph slot): a **wrench** on any claim whose support path traverses an analyst-ADDed triplet,
    and **spurious-reason glyphs** (verbatim `spurious_reason`).
  - **(c) `fabricated != false` overlay + gate-coverage gauge (§4.9c).** Promote the UI2 hatch overlay
    (pattern channel, out-of-slice only) to its final form + tooltip; render the §4.7
    **alignment/linking coverage** as a **gate-coverage gauge** in the Trust strip, visually distinct
    from gate error (coverage = did the claim reach the gate; error = how it was graded).
  - **(d) Epistemic glyph grammar — exactly 3 glyphs, 1 legend (§4.9d).** **open circle** =
    observational (support-frequency); **filled triangle + interval** = interventional aggregate (the
    sweep); **outlined "n=1" triangle** = single-sample demo. Driven by the schema `epistemic_level`
    fields (S2); legend lives in the Trust strip; no per-view variants. This disciplined encoding (NOT
    a new causal method) is the project's causality contribution.
  **Hue stays STATUS** throughout; every mark rides pattern/shape/border (Invariants #17–#20).
  *SPEC:* §4.5, §4.7, §4.9.
- **UI5 — Repair-loop UI (CB4) + before/after delta + live multi-run** · P2 · deps: UI3, EX3
  *Delivers:* spot-fabricated→restore-evidence (edit-the-KG)→re-run→diff (the repair live call). **(#CHANGE-2)
  Single-run REMOVE/ADD must persist a BEFORE → AFTER status DELTA side-by-side — do NOT re-render in
  place.** The pairing is durable via **`baseline_run_id`** (S2/§4.2): the perturbed run points at its
  pre-perturbation baseline run, and the delta pairs current vs `baseline_run_id` (the ablation's
  *effect* is the evidence). The delta is stamped the **n=1 outlined-triangle glyph** (single-sample;
  never an effect size). **(#CHANGE-4) `repair_leverage` rides a size/glyph channel** on the repaired
  claim/node, not prose "+1". **Plus the optional live multi-run path for a new question** (N runs,
  aggregate to the multi-run diagnostics) — gated behind a control, with a "minutes" cost notice; the
  canned demo uses frozen scenarios. *SPEC:* §4.5, §4.6.

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
  *Delivers:* RefChecker `LLMExtractor` (offline) → **pinned-greedy (temp 0) STRUCTURED `(h,r,t)`
  triplets** (not free text — it is a verifier-side stage); vendored KGR/VeGraph prompt fallback;
  cached. *SPEC:* §4.3(A).
- **GR6 — Entity linking `link.py`** · P1 · deps: S2, DA2
  *Delivers:* `BaseEntityLinker`; `LabelAliasIndex` (default, offline) + `ReFinEDLinker` (opt);
  out-of-slice → `unresolved_entities`. *SPEC:* §4.3(B).
  - *Also:* a **property-alias table + inverse-pair canonicalization** (e.g. father/P22 vs child/P40
    → one canonical relation) as a **named owned, slice-specific data artifact**, so **stable KG-item
    IDs (entities, triplets) key identically** regardless of phrasing/direction — this is what lets
    support-frequency (§4.8) aggregate the same triplet across runs. Aligns KG-item IDs, **not
    claims** (no cross-run claim alignment).
- **GR7 — Entailment gate `entailment.py`** · P1 · deps: S2
  *Delivers:* `BaseEntailmentGate`; text NLI gate (premise=evidence, hypothesis=claim;
  **value-sensitive**). **Verifier (accuracy-first, finalized): DeBERTa-v3-large on the LIVE path
  (live path DOES verify live), MiniCheck-7B for offline precompute/calibration; cache by distinct
  evidence-pair.** **ALL reported / figure numbers come from the OFFLINE precompute (MiniCheck-7B)** —
  the live path never sources reported numbers, so the verifier-model choice does not affect
  reproducibility (Invariant #22). *(The visual probe for the image axis is specced in
  `SPEC-image-artwork.md`.)* *SPEC:* §4.3, §4.7.
- **GR8 — Classifier `classify.py`** · P1 · deps: S2, DA2, GR6, GR7
  *Delivers:* decision order (direct triple → content fact → **undirected** multi-hop path →
  fabricated); `all_simple_paths`, **literal-node exclusion**, **max-entailment** path; sets
  `status` + `support_source` (+ within-run `claim_id`); **persists `entailment_score`** (raw score;
  margin to `tau` = deterministic confidence) + **`spurious_path` + `spurious_reason`** via the §4.8
  detectors (1) relation/value illegitimacy and (2) hub/length fragility. **No slot_key/claim_key and
  no cross-run claim alignment** — only stable KG-item IDs are aligned (for support-frequency, §4.8),
  via the property-alias/inverse table from GR6. *SPEC:* §4.3(C), §4.8.
- **GR9 — Grounding backend `backend.py` (real)** · P1 · deps: GR3, GR5, GR6, GR8, DA4
  *Delivers:* `ground_response(answer, reference, …)` wiring extract→link→classify into a
  `GroundingRun`, grading against the **reference (never the ablated context)**; replaces the P0
  stub. *SPEC:* §4.3, §3.2.
- **GR10 — Gold QA set, classifier error + reliability curve** · P1 · deps: GR9, DA4
  *Delivers:* the **curated gold QA set** that does **DOUBLE DUTY** (§4.7, FOCUS): it **calibrates the
  verifier** (the deployment trust tier — the only tier that earns the word "calibrated") **AND anchors
  the RQ2 sweep** (C2: "how big a sweep?" is answered by a good curated QA set, not "the whole
  dataset"). Reuses the EX1 gold subset, keeping the disjoint-fold rule. **Per-modality error** for the
  **text-NLI** and **structure-path** gates separately, **including adversarial wrong-value
  negatives**. **Hand-validate the reasoned-supportable bucket SEPARATELY** (the thorniest grade) and
  **report NLI-accepted-path multiplicity** (how many distinct paths the gate accepts per claim — a
  spurious-path exposure metric). Reports **alignment/linking coverage** (fraction of claims that link
  to an in-slice KG item and reach the gate; distinct from gate error). **Produces the RELIABILITY
  CURVE** — margin-bin (`|entailment_score - tau|`) vs empirical accuracy on the gold set — which
  **converts trust from asserted to demonstrated** (the per-claim margin is shown to track accuracy;
  feeds the UI6 Trust strip). **`tau`/`k` frozen after calibration on a disjoint fold, never tuned
  post-hoc**. *(Image/label error is in the image axis.)*
  *SPEC:* §4.7, §4.9a.
- **GR11 — Precompute pipeline + runs store** · P1 · deps: GR4, GR9
  *Delivers:* batch script: (question × **{full, content-withheld, knowledge-withheld}** × **N runs**)
  assemble→generate→ground → `data/runs/<run_id>.json` (the N runs per question/condition;
  `condition`/`sample_index`/`baseline_run_id` set — each perturbed run points at its matched FULL
  baseline run). withhold-from-context, **graded vs the full reference**. This sweep IS the **RQ2
  modality-contrast aggregate source** (the claim-status distribution shift across conditions, reported
  as a figure — not an interactive toggle). Records the **generator seeding scheme `seed =
  f(question_id, condition, sample_index)`**; cached by input hash; **deterministic given the seeds**
  (generator) and given fixed answer texts (verifier). **Also emits the matched NO-REPAIR re-run
  baseline** so EX3's `repair_leverage` can be reported **net of generator variance**. **Storage/keying
  convention:** the baseline is a synthetic re-run of the **FULL question with NO edit**, stored as its
  **own `GroundingRun`** with a distinct condition marker (`condition` tag `"full-no-edit-rerun"`) and a
  **`baseline_run_id` pointing at the original FULL run** it re-runs, so EX3 can consume it by that key
  to subtract generator variance. *SPEC:* §8, §10, §4.8, §4.3, §4.6.

### TEST
- **TS1 — §6 mechanical tests (P0 subset)** · P0 · deps: S2, DA1, PT1
  *Delivers:* sitelink-band filter test, composed-manifest attribution test, schema round-trip,
  grade-against-reference invariant scaffold. *SPEC:* §6.
- **TS2 — Classifier invariant tests + §6 controls wiring** · P1 · deps: GR8, GR9
  *Delivers:* undirected-path regression (`book→author←book`), spurious-shared-literal rejection,
  value-sensitive **false-claim rejection**, **grade-against-reference invariant (full, vs the real
  backend)**; control harness callable from the precompute. **Invariant:** **"same answer text =>
  bit-identical `claims` list (the grading output), excluding metadata fields run_id/condition/sample_index"** (verifier determinism). *SPEC:* §6, §4.8.

### EXP (books experiment)
- **EX1 — Question bank (books) · Phase A** · P2 · deps: DA3
  *Delivers:* fixed books bank — content-only questions (genre/form, tradition, scope, role) +
  knowledge questions; KGR-style tiers. *SPEC:* §5; statement §5.2.
- **EX2 — Ablation manifests (books) · Phase A** · P2 · deps: PT1, DA3
  *Delivers:* fixed `manifest.json` — text-content-absence + knowledge-absence; fixed before
  inspection. *SPEC:* §4.4, §5.1.
- **EX3 — Repair loop + repair-leverage `RepairSession`** · P2 · deps: GR9, GR3, GR11
  *Delivers:* the **edit-the-KG** layer — restore the missing evidence to the KG/reference, **re-run**
  (regenerate), grade against the **current (edited)** reference. **`repair_leverage` = COUNT** of
  claims that flip FABRICATED→grounded on restore + re-run (`RepairResult.repair_leverage`), paired
  **within that one answer's before/after by claim-TEXT SEMANTIC matching** (fuzzy/normalized dedup),
  **NOT raw `claim_id`** — because the ADD re-run **regenerates the answer**, so before/after claims
  carry different within-run `claim_id`s (Invariant #21; the gap-repair flow: true claim fabricated due
  to KG gap → add triplet → re-run → grounded). The reported figure is **net of the matched no-repair
  re-run baseline** consumed from GR11 by its convention — the synthetic `GroundingRun` with `condition`
  tag `"full-no-edit-rerun"` and `baseline_run_id` pointing at the original FULL run — so the flip count
  is reported above flips from re-sampling alone (an analysis-plan requirement for the reported figure,
  not an interactive feature). *SPEC:* §4.6, §4.8.
- **EX5 — Diagnostics aggregation `diagnostics.py`** · P2 · deps: GR11
  *Delivers:* the two-mode **per-question** diagnostics (§4.8). **Single-run:** `SingleRunStatusSummary`
  — one run's status counts/percentages, **no SE**, tagged `epistemic_level = SINGLE_SAMPLE` (the n=1
  outlined-triangle glyph contract, §4.9d). **Multi-run (N runs, FULL condition):** `AnswerDiagnostics`
  — **FULL-condition answer-level status mean +/- SE** (per-run fraction of claims that are
  retrieved/reasoned-supportable/fabricated, computed per run, then mean+SE across the N runs) +
  **support-frequency** (per KG node/triplet = fraction of N runs the item was **used** = lies on the
  support path of >=1 grounded claim; **observational, NOT causal**, **open-circle glyph**, aligned by
  stable KG-item ID), tagged `epistemic_level = OBSERVATIONAL`. **`AnswerDiagnostics` carries ONLY
  `status_distribution` + `support_frequency` (SPEC-text §4.2) — it does NOT carry `repair_leverage`.**
  `repair_leverage` lives on **`RepairResult`** (produced by **EX3**); the analytics panel surfaces it
  from `RepairResult` **SEPARATELY** from `AnswerDiagnostics`, never as a diagnostics field.
  **Claims are NOT aligned across runs.** Report **SE/CI of the proportion** (`SE=sqrt(p(1-p)/N)`) with
  a **prominent small-N caveat** (N=20 is a floor). The **modality-condition aggregation** {full,
  content-withheld, knowledge-withheld} (the RQ2 contrast) belongs to the **offline experiment (EX4)**,
  NOT the per-question diagnostics.
  - *Also — the C3 agreement-quadrant PILOT (upside; must NOT drive schedule; FOCUS C3).* On a
    **capped ~5-8 questions**, cross plot **observational support-frequency** (open circle) vs the
    **interventional absence-shift** (filled triangle + interval, from EX4) at KG-triplet grain →
    load-bearing / redundant-scaffold / hidden-dependency / inert. This is a **qualitative
    existence-proof, NOT a powered finding**; the populated quadrant is the cuttable empirical result,
    the taxonomy-as-a-lens + `repair_leverage` are the delivered novelty (they ship regardless).
  **Drop slot/variant, leverage/induction scalars, per-claim stability.** *SPEC:* §4.8, §4.9d.
- **EX4 — Phase A BOOKS runs + controls + pilot (= M-BOOKS)** · P2 · deps: GR11, GR10, TS2, EX1, EX2
  *Delivers:* run precompute over books bank × **{full, content-withheld, knowledge-withheld}** (the
  RQ2 sweep, GR11); the **RQ2 modality-contrast aggregate** — the claim-status distribution shift
  across conditions, reported as a **REPORT figure** stamped **`INTERVENTIONAL_AGGREGATE`** (filled
  triangle + interval; this aggregate, not an interactive toggle, IS the RQ2 result). **The stamp is
  applied as the figure's caption / label / legend context (a static report figure), NOT via the UI6
  Dash glyph components — so EX4 is NOT gated on UI6** (an implementer must still ship the stamp on the
  figure, but must not add a UI6 dependency to do it); **negative / false-claim /
  manipulation / modality-strength controls** on real data; empirical pilot (~10 q); per-slice
  claim-status distributions + fabrication shifts. **PROPAGATE verifier error as a NOISE FLOOR on the
  C2 distribution-shift** — the per-modality classifier error (GR10) is carried onto the RQ2 figure so
  an absence-induced shift is only read as real when it clears the gate's own error floor. **HARD-ENTITY
  control** — use the **knowledge-withheld** condition as the **intrinsic-difficulty control** for the
  content-absence / obscurity confound (an entity hard because content is genuinely thin vs. hard
  because evidence was withheld), so a fabrication shift is attributable to *absence*, not to baseline
  entity difficulty. **M-BOOKS is declared ONLY when these controls PASS — not merely run**
  (false-claim control non-negotiable). *SPEC:* §5, §6, §8, §4.7.
- **EX6 — Case studies + write-up + deliverables (PER-STREAM CO-AUTHORED)** · P2 · deps: EX4 (+ image results if produced)
  *Delivers:* 2–3 end-to-end repair walkthroughs; the **IEEE-VIS intermediate + scientific reports**.
  **RESTRUCTURED as PER-STREAM CO-AUTHORED SECTIONS** — the writeup is NOT one monolithic task; it
  spreads across all four people, each owning a section that mirrors their build stream. The mandated
  deliverable elements are **assigned to the owning section** (not dropped):
  - **EX6a — Method / backend (owner: backend stream).** Generator-vs-verifier methodology, the
    deterministic-verifier defense (L6 "guidance → bias"), the grounding cascade, **three explicit
    contribution bullets**, the **Sacha 2014** knowledge-generation cycle + **MMA-model mapping** in
    related work. *SPEC:* §4.3, §4.9.
  - **EX6b — Data + experiments / results (owner: data/experiments stream).** The RQ2 sweep + the
    **RQ1/RQ2/RQ3 question framing**, the absence-shift figure (`INTERVENTIONAL_AGGREGATE`), §6 control
    results, the C3 agreement-quadrant pilot, the **work plan**, the **GitHub link**. *SPEC:* §5, §6, §8.
  - **EX6c — Interface / design (owner: design stream).** The **teaser figure**, the
    **interaction-design figure as a simplified MMA-model Fig 1** (3 zones → ivg-kg), **Pike 2009**
    framing of the interaction section, the **R1/R2/R3 requirements skeleton** (Overview → Inspection →
    Repair), the no-projection DEFER defense (one sentence), the **5-min demo recording showing all
    features** (due 23 Jun). **Note:** the recording needs a **demoable UI** (the mock-driven UI6 build
    OR the real UI), so EX6c is **not scheduled before the UI is demoable**. *SPEC:* §4.5.
  - **EX6d — Evaluation + trust (owner: evaluation stream).** The honesty layer writeup, the **two-tier
    trust** account (instrument-level uncalibrated prior vs deployment-level calibrated), the
    **reliability curve** (trust demonstrated, not asserted), per-modality error, the epistemic glyph
    grammar as the causality contribution, **novelty honesty** (claim the composition, not the
    primitives — cite *Graphing the Truth* [9], VISA [2], VDGD [22]/M3ID, MCiteBench [23], ContextCite,
    "Attention is not Explanation"). *SPEC:* §4.7, §4.9.
  - **Shared (any owner):** ≥10 refs (≥5 from lecture slides); the **per-member-contribution +
    AI-tool-attribution appendix**. *SPEC:* §8; statement §8, §11; `../course/DELIVERABLE-RUBRICS.md`.

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
GR3,GR5,GR6,GR8,DA4 ─► GR9 ─► GR10, GR11, TS2        │
GR9, GR11 ─► EX3 ; GR11 ─► UI3 ─► UI4, UI5 ; GR11 ─► EX5 ─► UI4 ; EX3 ─► UI4, UI5   │
UI2, GR9, GR10, EX5 ─► UI6 (honesty layer)            │
GR10, TS2, EX1, EX2, GR11 ─► EX4 (= M-BOOKS) ─► UI4, EX6
RES1 (independent)                                    ┘
         ═══ after M-BOOKS (COMMITTED, sequenced): open TASKS-image-artwork.md (gate routes → -taxa floor) ═══
```
> **Stub-first parallelization (de-risk).** The UI track (UI1 → UI2 → UI6 on mock) does **NOT** block
> on GR9: S2 is the contract, so the instrument is demoable on mock first; real runs swap in at UI3.
> UI6's `GR9/GR10/EX5` deps are for the *final* (real-data) honesty layer — a **mock-driven UI6 can
> start right after UI2** (against UI1 fixtures), so C1 is demoable even if grounding slips.

## Parallel execution waves (earliest-start)
- **Wave 0:** S1.
- **Wave 1:** S2 ‖ DA1 ‖ RES1.
- **Wave 2:** GR1 ‖ PT1 ‖ UI1 ‖ GR7 ‖ GR5 ‖ DA2.
- **Wave 3:** DA3 ‖ DA4 ‖ GR6 ‖ GR3 ‖ UI2 ‖ TS1.  → **P0 closes** when {S1,S2,DA1,DA2,DA3,DA4,PT1,UI1,UI2,TS1} done — **review gate**.
- **Wave 4 (P1):** GR4 ‖ GR8 → GR9 → {GR10 ‖ GR11 ‖ TS2}.  *(GR4 needs GR3 from Wave 3.)*
  - **Stub-first UI sidecar (parallel, off the grounding track):** a **mock-driven UI6** (honesty
    layer against UI1 fixtures) can run here, alongside Wave 4, so the **whole C1 instrument is
    demoable on mock before GR9 lands**. Its real-data finalization waits for {GR9, GR10, EX5}.
- **Wave 5:** UI3 ‖ EX1 ‖ EX2 ‖ EX3 ‖ EX5.
- **Wave 6 (P2):** EX4 (books runs + §6 controls + pilot) → **✦ M-BOOKS ✦** → {UI4 ‖ UI5 ‖ UI6 (real-data finalize) ‖ EX6}.
- **After M-BOOKS (separate files):** the **committed** image axis — artwork first; the gate routes
  the domain to the taxa **verified floor** on failure (never books-only).

## Critical path
```
S1 → S2 → DA2 → DA4 → GR3 → GR9 → GR11 → EX4 → EX6
                         ▲ (GR6,GR7 → GR8 → GR9 parallel sub-spine)
```
The UI track runs on mock (UI1→UI2→mock-UI6) in parallel with the grounding track and is **not on the
critical path** (stub-first: the schema is the contract, so C1 is demoable even if grounding slips).
The image axis is off this path by construction (separate, post-M-BOOKS) — **committed but sequenced**;
the gate routes the domain, it never drops the modality.

## Notes
- **P0 is the stop-and-review deliverable.** Do not start real grounding (GR9) before that review.
- **Stub-first:** UI builds against MOCK fixtures (UI1) first; real runs swap in at UI3; this de-risks
  C1 against a slipping pipeline.
- **RES1** blocks nothing in code; it lifts the statement's provisional flag.
- **Image axis (committed, sequenced):** after M-BOOKS, see `TASKS-image-artwork.md`; on
  non-redundancy-gate failure, the gate **routes the domain** to `TASKS-image-taxa.md` (verified
  floor) — the image modality ships either way; only the cross-modality contrast is quarantined.
