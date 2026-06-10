# SPEC-text — Books spine (text-content vs knowledge) · `ivg-kg`

> **Core implementation spec** — the guaranteed deliverable, built and fully measured first
> (milestone **M-BOOKS**). The scientific source of truth is `../project_statement.md` (§ refs point
> there). The **gated image axis** is specified separately and built only post-M-BOOKS:
> `SPEC-image-artwork.md` (primary) and `SPEC-image-taxa.md` (fallback). This document holds the
> **shared, multimodal-ready schema** (§4.2) those specs reference — they never redefine it.
>
> One spec family, three files: **SPEC-text (this)** = books + all shared infrastructure;
> **SPEC-image-artwork** / **SPEC-image-taxa** = the gated image slices.

## 0. How to read this
- §1–§2 scope/phasing + reuse reality-check. §3 architecture + the three seams + repo layout.
- §4 component specs (the build target). §5 question bank. §6 validation & controls.
- §7–§13 stack, data flow, build order, reproducibility, risks, decisions, reuse dossier.

---

## 1. Scope and phasing

The project fully measures **one comparison — text-content-absence vs. knowledge-absence on
books** — then, gated behind M-BOOKS and curtailable, adds an **image-content axis** (artwork-first,
taxa-fallback; see the image specs).

| Build phase | Goal | Components |
| --- | --- | --- |
| **P0 — Foundation** | Books data layer + skeleton UI on mock, joined by the typed schema. No real grounding. | data layer (§4.1), schema (§4.2), perturbation interface (§4.4), UI skeleton (§4.5), grounding **stub**. |
| **P1 — Grounding** | Real in-context generation + three-way classifier + entailment gate; books error accounting. | grounding backend (§4.3), classifier-error (§4.7), §6 controls. |
| **P2 — Experiment (books) = M-BOOKS** | Books question bank, ablation runs, controls pass, repair loop + leverage. | question bank (§5), repair loop (§4.6), analytics. |

**M-BOOKS** = books validated end-to-end through P2 with the §6 controls **passing**. Only then is
the image axis opened (artwork → taxa-fallback → books-only). **Dates:** personal M-BOOKS target
**2026-06-12**; real course backstops **demo 2026-06-23**, **report 2026-06-25**, **presentation
2026-06-27**. The ~2-week real runway makes the image axis a realistic gated target; books-first
still governs.

---

## 2. Reuse reality-check
The cited "backends" mostly lack reusable code; we reimplement methods and adopt permissive OSS.

| Ref | Status | Verdict | We take |
| --- | --- | --- | --- |
| **GraphEval** [4] (Sansford 2407.10793) | no public code; document/NLI-grounded, not KG-grounded; cited `xz-liu/GraphEval` is a *different* paper (2404.00942) | reference-only | the two-stage idea; not a backend |
| **VeGraph** [6] (MIT) | Wikipedia-text + Elasticsearch; "graph" is a string; no Wikidata | vendor *prompts* | claim→triplet / hidden-entity / subclaim-verification prompts |
| **CogMG** [5] | unlicensed; Chinese; old LangChain; KoPL | reference *pattern* | the repair-loop shape only |
| **KGR** [1] | no public code | reimplement | the 5-stage pipeline (extract→detect→select→verify→[drop retrofit]) |
| **VISA** [2] | document-region attribution | reference framing | the "attribution analogue" idea (esp. multi-layer attribution on the image axis) |

**Adopted OSS (text/core):** WikibaseIntegrator (MIT) + SPARQLWrapper (W3C) for the pull;
**QLever** (`qlever.dev/api/wikidata`) as the SPARQL fallback (verified working during a WDQS
outage; no label service → resolve via `rdfs:label`/`schema:description`); NetworkX (BSD-3);
RefChecker `LLMExtractor` (Apache-2.0) or vendored prompts; ReFinED (Apache-2.0, optional EL);
**MiniCheck** (Apache-2.0) text NLI gate; dash-cytoscape (MIT). CogMG (unlicensed) / GENRE
(non-commercial) are **not** vendored. *(VLM + visual probe for the image axis: see the image specs.)*

---

## 3. Architecture and the three seams

### 3.1 Seams (statement §7)
1. **Perturbation-as-interface** — pipeline consumes `(evidence, Perturbation)`; the perturbation
   withholds evidence from the **generation context**. New axes = new `Perturbation` subclasses.
2. **Uniform per-claim log** — every claim is a `ClaimRecord`; every axis writes the same shape.
3. **Controls-from-registry UI** — perturbation controls render from the registered types.

### 3.2 The load-bearing invariant (statement §5.3/§5.6)
```
 full evidence (KG-full triples + description [+ image, image axis only])
        │  Perturbation.withhold(...)            [generation only]
        ▼
 GENERATION CONTEXT ──► generate_answer (LLM; VLM on the image axis) ──► answer_text
                                                                          │
 GRADING REFERENCE  ◄── never ablated ──┐                                 ▼
 (KG-full triples + curated content labels)   ground_response: extract → link → classify
        └──────────── claims graded against the REFERENCE, not the ablated context ───┘
```
A fact hidden from the generator stays in the grading reference, so it remains gradable; ablation
changes only the *answer*, never the grader. **This is the correctness spine.**

### 3.3 Repository layout
```
ivg-kg/
  project_statement.md  STATEMENT-CHANGES.md
  spec/   SPEC-text.md  SPEC-image-artwork.md  SPEC-image-taxa.md
  tasks/  TASKS.md  TASKS-image-artwork.md  TASKS-image-taxa.md
  course/ COURSE-DISTILLATION.md  DELIVERABLE-RUBRICS.md  MMA-MODEL.md
  data/
    cache/                         # SPARQL cache (gitignored)
    frozen/books/<id>/             # snapshot.json (+parquet), manifest.json
    frozen/<image-slice>/<id>/     # image-axis slices (see image specs)
    runs/<run_id>.json             # precomputed GroundingRun store
  src/ivg_kg/
    schema.py                      # §4.2 (multimodal-ready)
    config.py
    data/        wikidata.py  graph_store.py  reference.py  pipeline.py   # books; image slices in image specs
    perturbation/ base.py  text_content_absence.py  knowledge_absence.py  image_content_absence.py
    grounding/   clients/{base,local,cloud}.py  context.py  generate.py  extract.py  link.py
                 classify.py  entailment.py  backend.py                   # clients/vlm.py: image spec
    mock/fixtures.py
  app/   app.py  layout.py  callbacks.py  panels/{answer,subgraph,analytics}.py
         charts/{status_dist,repair_history,coverage,support_frequency}.py
  tests/
```

---

## 4. Component specifications

### 4.1 Data layer (books; P0)
**Books (`Q571`)** — text-content axis. Pull label, description (CONTENT) + outgoing triples with
human-readable property/value labels (STRUCTURE). Sitelink band default **5–40**.
**Pull (`wikidata.py`).** `query.wikidata.org/sparql`, no key; descriptive UA, rate-limit, 429/5xx
backoff, disk cache by query hash; **QLever fallback** when WDQS is degraded. Property-type filter
keeps WikibaseItem/Time/Quantity/Monolingualtext/String; drops ExternalId/Url/CommonsMedia/etc.
**`sitelink_band_filter`** — pure, inclusive, drops missing counts; server-side *and* re-checked in
Python (unit-tested).
**Freeze (`graph_store.py`).** Canonical JSON `snapshot.json` (+optional parquet); NetworkX
**rebuilt from JSON** (no pickle); `nx_to_cyto_elements` adapter.
**Grading reference (`reference.py`).** `GradingReference = KGSnapshot (KG-full) + list[ContentLabel]`;
`ContentLabel(entity_id, modality∈{text,image}, fact, source)` holds **content-only** facts the
triples omit (books: content-only textual facts). **Never ablated.** *(Image labels: image specs.)*

### 4.2 Typed schema — the contract (P0; multimodal-ready)
Pydantic v2; JSON-serializable for `dcc.Store`. **This is the single shared contract; the image
specs reference it, never redefine it.**
```python
class ClaimStatus(str, Enum):
    RETRIEVED = "retrieved"            # directly grounded in ONE evidence item (triple OR content fact)
    REASONED_SUPPORTABLE = "reasoned-supportable"   # grounded only via a multi-hop path; UI label: "Supportable"
    FABRICATED = "fabricated"
# UI short labels (the long term stays in prose/contract): Retrieved / Supportable / Fabricated.
# Colour encodes STATUS (one fixed 3-grade palette, used identically in every panel); multiple
# selected claims are distinguished by an outline + numeric badge, NOT by hue (§4.5).
class Condition(str, Enum):           # the generation-context condition a run was produced under
    FULL = "full"
    KNOWLEDGE_ABSENT = "knowledge-absent"
    CONTENT_ABSENT = "content-absent"
    IMAGE_ABSENT = "image-absent"     # image axis only
class SupportSource(str, Enum): DIRECT_TRIPLE; MULTI_HOP_PATH; TEXT_CONTENT; IMAGE_CONTENT; NONE
class Modality(str, Enum): STRUCTURE; TEXT; IMAGE
class ValueType(str, Enum): ITEM; TIME; QUANTITY; MONOLINGUAL; STRING
class TripleRef(BaseModel): subject_id; property_id; object_id: str|None = None

class KGNode(BaseModel):  id; label; description: str|None; sitelinks: int|None
                          image_path: str|None; kind="entity"     # image_path: image-axis slices / entity-image display
class KGEdge(BaseModel):  subject_id; property_id; property_label; object_id: str|None
                          object_label; value_type: ValueType
class KGSnapshot(BaseModel): snapshot_id; slice: str; domain_qid; nodes; edges; meta: dict
class ContentLabel(BaseModel): entity_id; modality: Modality; fact: str; source: str
class GradingReference(BaseModel): snapshot: KGSnapshot; content_labels: list[ContentLabel]

class GenerationContext(BaseModel): entity_id; triples: list[KGEdge]; description: str|None; image_path: str|None
class GroundingConfig(BaseModel): k_hops: int = 2; tau: float = 0.5; linker="label_alias"; entailment="minicheck"

class LinkedEntity(BaseModel): id; label; description: str|None; link_score: float|None
class PathEdge(BaseModel): subject_id; subject_label; property_id; property_label
                           object_id: str|None; object_label; traversed_forward: bool
class GroundingPath(BaseModel): edges: list[PathEdge]; node_ids: list[str]
class ClaimRecord(BaseModel):
    claim_id; text; status: ClaimStatus; support_source: SupportSource  # claim_id is WITHIN-RUN only; claims are NOT aligned across runs (§4.8)
    linked_entities: list[LinkedEntity]; grounding_path: GroundingPath
    active_perturbations: list[str] = []
    entailment_score: float|None       # persist the RAW entailment score; margin to tau = a deterministic confidence (§4.3)
    spurious_path: bool = False; spurious_reason: str|None = None       # reason code when spurious_path (§4.8)
    unresolved_entities: list[str] = []
class GroundingRun(BaseModel):
    run_id; question; answer_text; slice: str; phase: str
    condition: Condition = Condition.FULL; sample_index: int = 0        # which condition + which of the N runs (multi-run mode); claims NOT aligned across runs (§4.8)
    claims: list[ClaimRecord]; active_perturbations: list[str] = []
    grading_reference_id: str|None; error_rates: dict[str,float] = {}   # per modality path
    def status_counts(self)->dict[str,int]: ...
    def fabrication_rate(self)->float: ...

# ---- Diagnostics (§4.8). Claims are NOT aligned across runs; only STABLE KG-ITEM IDs are. ----
# SINGLE-RUN: per-run status counts/percentages only — NO SE (it is one sample).
class SingleRunStatusSummary(BaseModel):   # the single-run analytics view
    status_counts: dict[str, int]          # {status: count} for THIS one run
    status_percentages: dict[str, float]   # {status: fraction} for THIS one run — no SE
# MULTI-RUN: answer-level per-run fractions, aggregated to mean+SE across the N runs.
class StatusMeanSE(BaseModel):
    mean: float; se: float                 # SE of a PROPORTION: sqrt(p(1-p)/N); §4.8
class AnswerDiagnostics(BaseModel):        # the multi-run analytics view (#5)
    question: str; n_runs: int
    status_distribution: dict[str, StatusMeanSE]   # status -> mean +/- SE of the per-run answer-level fraction over N runs
    support_frequency: dict[str, float]            # KG-item id (entity_id OR triplet_id, triplet key = "<subject_id>|<property_id>|<object_id>" per §4.8) -> fraction of N runs it was USED to ground a claim (observational, NOT causal); §4.8
class RepairResult(BaseModel):             # the gap-repair before/after result (§4.6)
    restored_item: str                     # the triple/content restored to the KG
    repair_leverage: int                   # count of claims that flipped FABRICATED->grounded on restore + re-run (aligned by claim_id within this one answer's before/after); §4.6
```
> **Taxonomy note (statement §5.5):** `RETRIEVED` = directly grounded in a single evidence item — a
> triple OR a content fact (description/image); `support_source` records which. This lets content-only
> true claims grade grounded and flip RETRIEVED→FABRICATED under content-absence (the RQ2 signal).

### 4.3 Grounding backend (P1; stub in P0)
```python
def generate_answer(question: str, context: GenerationContext, client: BaseAIClient) -> str: ...
def ground_response(question: str, answer_text: str, reference: GradingReference,
                    *, active_perturbations: list[str], config: GroundingConfig) -> GroundingRun: ...
```
P0: both raise `NotImplementedError`; UI uses `mock/fixtures.py`.

**Generator vs verifier (design principle).** The GENERATOR and the VERIFIER are two different
systems with opposite goals; do not blur them.
- **Generator** (system under test): `generate_answer` is **stochastic on purpose** — sampled,
  temp ~0.7, drawn N times per condition. It is **seeded** for reproducibility:
  `seed = f(question_id, condition, sample_index)`. All per-draw variance is GENERATION variance.
- **Verifier** (measurement instrument): `ground_response` and every verifier-side LLM stage are
  **deterministic on purpose**, and always grade against the **FULL grading reference (full KG)**,
  never the ablated context. Every verifier-side LLM stage (claim extraction) is **pinned
  temperature 0 / greedy**. Persist the **raw entailment score** (its margin to `tau` = a
  deterministic confidence). On MPS, suppress float jitter via **float32 + fixed batch order** so the
  gate is bit-stable.
- **No self-verification (hard rule).** The verifier must be a **different model family from the
  generator** — a verifier sharing the generator's family inherits correlated blind spots and would
  pass the generator's own hallucinations.
- **KGR deviation.** KGR uses the LLM itself as the verifier; we **replace that stage with a
  deterministic entailment gate over symbolically selected evidence**, so that **generation is the
  only stochastic stage** and classifier error is calibrated separately (§4.7).
- **Accuracy, not latency (verifier model choice — FINALIZED).** Verification is mostly precompute,
  so verifier per-pair latency is second-order; prioritize verifier **accuracy**. **Decision:**
  **DeBERTa-v3-large on the LIVE path** (the live path DOES verify live — confirmed), and
  **MiniCheck-7B for OFFLINE precompute / calibration**. **Cache verification by distinct
  evidence-pair** so repeated pairs are not re-run.

- **Context (`context.py`):** build `GenerationContext` from full evidence, then apply active
  `Perturbation.withhold`. The **only** place ablation happens.
- **Generation (`generate.py`):** `BaseAIClient` ABC; `LocalModelClient` (POC default) + `CloudAIClient`.
  No provider SDK in business logic. Cached by `hash(question, context)`. *(VLM client for image
  generation: `SPEC-image-artwork.md`.)*
- **A — extraction (`extract.py`):** RefChecker `LLMExtractor` → structured **`(h,r,t)` triplets**
  (not free text); vendored KGR/VeGraph fallback; **pinned greedy (temperature 0)** — it is a
  verifier-side stage; cached.
- **B — linking (`link.py`):** `BaseEntityLinker`: `LabelAliasIndex` (default) / `ReFinEDLinker` (opt);
  out-of-slice → `unresolved_entities`. Maintains a **property-alias table + canonical orientation
  for inverse pairs** (e.g. father/P22 vs child/P40 → one canonical relation) as a **named,
  slice-specific data artifact** so that **stable KG-item IDs (entities, triplets) are keyed
  identically** regardless of surface phrasing or relation direction — this is what lets
  support-frequency (§4.8) aggregate the same triplet across runs. Linking aligns **KG-item IDs**,
  not claims.
- **C — classification (`classify.py`):** decision order — (1) direct triple entailing → RETRIEVED/
  DIRECT_TRIPLE; (2) content fact (description / curated label) entailing → RETRIEVED/TEXT_CONTENT
  (IMAGE_CONTENT on the image axis); (3) **undirected** multi-hop path 2..k (`all_simple_paths`,
  **literal nodes excluded as waypoints**, **highest-entailment** path) entailing → REASONED_SUPPORTABLE/
  MULTI_HOP_PATH; (4) else FABRICATED/NONE, `spurious_path=True` if evidence existed but failed entailment.
- **Entailment gate (`entailment.py`):** `BaseEntailmentGate.entails(premise, hypothesis)`. Text NLI
  (**DeBERTa-v3-large live / MiniCheck-7B offline**, per the verifier-model decision above): premise =
  serialized reference evidence, hypothesis = claim (asymmetric — do not invert). **Value-sensitive**:
  a claim whose asserted value the evidence contradicts/omits fails → FABRICATED. Tunes `tau`/`k` on a
  **disjoint fold**. **Cache by distinct evidence-pair.** *(Image-content claims grade by text NLI
  against the curated label, not the raster; the visual probe constructs/verifies labels — image spec.)*
Classification always reads the **grading reference**, never the ablated context.

### 4.4 Perturbation interface (P0)
**Two perturbation layers, distinct grading semantics (load-bearing).**
- **(a) Withhold-from-context** (RQ2 absence experiment) — hide content (description) or structural
  (triplet) evidence from the **generation context only**. The item **STAYS in the grading
  reference**; classification grades against the **FULL** reference. This is the controlled
  absence-induced-hallucination manipulation; it is a **multi-run** operation and its result is the
  **shift in the claim-status distribution** across conditions {full, content-withheld,
  knowledge-withheld}. There is **no `absence_leverage` / `fabrication_induction` scalar** — report
  the distribution shift (the report may state the difference of means).
- **(b) Edit-the-KG** (gap-repair / free exploration) — genuinely **add/remove** a triplet or node
  content from the KG itself, **changing the ground truth**. Classification then grades against the
  **CURRENT (edited)** KG. This powers the gap-repair demo (a true claim is fabricated because the KG
  lacks the triplet → analyst adds it → re-run → claim becomes grounded).

**Withhold-from-context NEVER changes the grading reference; edit-the-KG DELIBERATELY changes it.**
Both are graded against the current reference; the difference is whether the edit touched the
reference.

`Perturbation` ABC (`type_name`, `id`, `modality`, `withhold(ctx)->ctx`, `manifest_entry()`,
`control_spec()`) + registry + `AblationManifest` (serialize/`from_json`, fixed before inspection).
The withhold-from-context classes are: `TextContentAbsence(entity_id)`,
`KnowledgeAbsence(triples: list[TripleRef])`, `ImageContentAbsence(entity_id)` (generic
withhold-the-image seam; its *data/grading* is the image axis). All withhold from the **generation
context**, not the frozen KG. (Edit-the-KG is the §4.6 repair layer — it mutates the KG/reference.)
A claim's `active_perturbations` lists entries touching its linked entities (composed-manifest
attributable; caveat: ambiguous if one claim links two entities under different perturbations — fine
for Phase-A single-axis runs).

### 4.5 Interface — three panels (P0 skeleton; P2 full)
dash-cytoscape; Dash 2.x; data/layout/callbacks separation; one `get_*_panel()` / `make_*_figure()`.
**Panels are named by function (Answer / Subgraph / Analytics); the MMA-model UI pillars
(Outputs / Process / Knowledge / Trust) are a cross-cutting lens, not a 1:1 panel mapping** — the
*Process* pillar is the verification trace in the Answer column, *Trust* is the always-visible
per-modality error strip hosted in Analytics.

**Encoding decision (load-bearing, do not violate):** **hue encodes claim STATUS** — one fixed
3-grade palette (Retrieved / Supportable / Fabricated; long term `reasoned-supportable`) used
**identically** in every panel. When multiple claims are selected, they are distinguished by a
**highlight outline + numeric badge** (Claim 1, Claim 2…), never by re-using hue for identity.

- **Answer panel** (Outputs + Process) — the answer with each claim coloured by status; the
  `>>PROPOSED → >>VERIFY → status` verification trace is the Process pillar. Interactions:
  **(#1) status filter** over the **three grades** (Yi07 Filter; "proposed" = the input universe,
  *not* a fourth grade — clearing the filter shows all); **(#2) multi-select claims** to brush
  several onto the subgraph at once (Yi07 Select+Connect; outline+badge per claim); click a claim →
  `dcc.Store(selected_claim)`.
- **Subgraph panel** (Knowledge) — `nx.ego_graph` around the selected claim's linked entities;
  support path highlighted by **appending stylesheet selectors** (never mutate the global
  stylesheet). **(#3/#8)** show the **1st-degree neighbourhood** of claim nodes, de-emphasised, under
  a **node cap** (skip neighbour expansion above the cap); the full-answer view renders all claim
  nodes + their 1st-degree neighbours (the **Overview** state). **(#7)** tapping a node **zooms to it
  + its 1st-degree neighbours** and opens an **entity-detail sub-pane (bottom-middle)** showing the
  entity image when present (P18 — demo-visual even though not grounding evidence: book covers /
  author portraits; the **multimodal surface** where the image axis later attaches). *(On the image
  axis the pane also shows the slice image + claim→region/visual attribution — image spec.)*
- **Analytics panel** (Knowledge + Trust) — operates in **two modes** (a mode toggle), plus the
  always-visible Trust strip:
  - **SINGLE-RUN mode** — one generated answer. Shows **that one run's status percentages** (and raw
    counts) with **NO SE** (it is a single sample), driven by `SingleRunStatusSummary` (§4.2). The
    per-claim **support-path highlight** ("what this verdict rests on") and per-claim status live with
    this mode (Answer + Subgraph panels). No N selector here.
  - **MULTI-RUN mode (#5)** — re-runs the query **N times** (N selectable, **default 20**) and shows:
    **(a)** the **status distribution as mean +/- SE** of the per-run answer-level fraction of claims
    that are retrieved / reasoned-supportable / fabricated (`AnswerDiagnostics.status_distribution`,
    §4.8) as a column chart with error bars; **(b)** **support-frequency** — for each KG node and each
    triplet, the fraction of the N runs in which it was **used** to ground a claim
    (`AnswerDiagnostics.support_frequency`), visualised as **node-size / edge-weight on the subgraph**.
    Support-frequency is **observational importance**, explicitly **NOT** causal leverage. Plus
    **modality coverage** and **repair history + the repair-leverage count** (§4.6).
    **Small-N caveat (prominent):** the error bars are the **SE of a proportion** (`sqrt(p(1-p)/N)`),
    **not** the ~0.5 Bernoulli per-draw std; **N=20 is a FLOOR, not a target** — the caveat must be
    prominent in the view and its meaning pinned in the caption.
  - **Trust indicator** — always-visible, rendering `GroundingRun.error_rates` (per-modality
    classifier error — the MMA-model Trust pillar). Bars start at y=0; node sizing by area.
- **Coordination:** `dcc.Store(selected_claim)` written by Answer-click; Subgraph + Analytics read it
  independently (no circular callbacks); `modified_timestamp` for initial-load reads. The interaction
  set realises the **Overview → Inspection → Repair** state machine (Yi07 operators on the
  transitions): Overview (#8/#5) → Inspection (#1–#3, #7, single-run support-path) → Repair (§4.6
  edit-the-KG + re-run) → Overview.
- **Controls-from-registry:** iterate `available_perturbations()`/`control_spec()`.

### 4.6 Repair loop & repair-leverage (P2)
`RepairSession` is the **edit-the-KG** layer (§4.4(b)): the analyst genuinely restores the missing
evidence to the **KG / grading reference**, then **re-runs** (regenerates). The gap-repair flow: a
true claim is fabricated because the KG lacks the triplet → analyst adds the triplet → re-run →
the claim becomes grounded.

**`repair_leverage` (RQ3) — a COUNT (`RepairResult.repair_leverage`, §4.2):** the number of claims
that flip **FABRICATED → grounded** when the analyst restores the missing evidence and **re-runs**.
It is **regeneration-based**, aligned by `claim_id` **within that one answer's before/after** pair.
This is the gap-repair flow with a count on it; it preserves RQ3, contribution 3, and the CogMG
differentiation. **It is NOT a deterministic re-grounding leverage** (which was dropped): because
regeneration rewrites wrong values, the FABRICATED → grounded flips are real.

**N runs (multi-run mode, the instrument).** For a question, the tool re-runs the query **N times**
(N selectable, default 20) and aggregates the per-run answer-level fractions into the §4.8
diagnostics (status mean +/- SE; support-frequency over KG-item IDs). The live path verifies live
(DeBERTa-v3-large; §4.3). Cost is roughly N generations + grounding per question (minutes on a small
local model — too slow for a *new* question on stage). So the demo also ships a small set of **frozen
scenarios** (cached run-sets, e.g. the Chopin example) for instant, reproducible presentation and for
the reported figures; live runs serve new questions, frozen serves the canned story. *(Demo-safety:
§10.)*

### 4.7 Classifier-error & label accounting (P1)
Error rate on a **curated QA set per slice** (a held-out gold set, **including adversarial
value-swapped negatives** so an entity-match-only grader is caught), **per modality path** —
text-NLI gate and structure path search separately → `GroundingRun.error_rates`. This QA set is
**conceptually separate** from the image-label reference (do not conflate the two). Report
**alignment/linking COVERAGE** (the fraction of extracted claims that link to an in-slice KG item and
reach the gate) as a **pipeline metric distinct from the grading-gate error** — coverage measures
whether claims reach the gate; gate error measures how it grades them. Content labels
double-labelled / spot-checked (IAA reported). `tau`/`k` are **frozen after calibration on a
disjoint fold** and **never tuned post-hoc**. *(Image visual-probe error + image-label IAA: image
spec.)*

### 4.8 Single-run & multi-run diagnostics (P2) — exact definitions
Two modes (§4.5). **Claims are NOT aligned across runs.** The design aligns only **stable KG-item IDs**
(entities, triplets — canonicalized via the §4.3(B) property-alias / inverse-orientation table) for
support-frequency, and aggregates claims **only as answer-level fractions**. **Not aligning claims
across runs is WHY this design is simpler** than a per-claim cross-run scheme. Within a single run,
`claim_id` is the only claim identifier; it does not carry meaning across runs.

- **Single-run status % (no SE).** For one generated answer, report the **status counts and
  percentages** over that run's claims (`SingleRunStatusSummary`, §4.2). It is a **single sample** —
  **no SE/STD**. The per-claim support-path highlight (the support path of each grounded claim,
  "what this verdict rests on") and per-claim status accompany it.
- **Multi-run status mean +/- SE (ANSWER-LEVEL).** Re-run the query **N times** (default 20). For
  each run compute the **answer-level fraction** of claims that are retrieved / reasoned-supportable /
  fabricated; then report, per status, the **mean and SE across the N runs**
  (`AnswerDiagnostics.status_distribution: dict[status, StatusMeanSE]`). The fraction is computed
  per-run first, then aggregated across runs — never pooled.
- **Support-frequency (observational, NOT causal).** For each KG **node** and each **triplet**,
  `support_frequency[id]` = the **fraction of the N runs in which that item was USED to ground a
  claim**. **Definition of "used":** the item **lies on the support path of >= 1 grounded claim in
  that run** (a direct triple/content item supporting a RETRIEVED claim, or any node/edge on the
  multi-hop path of a REASONED_SUPPORTABLE claim). This is **observational importance** — "how often
  grounding routes through this item" — explicitly **NOT** causal leverage. Visualised as **node-size
  / edge-weight** on the subgraph (§4.5). **Triplet key format.** A triplet KG-item ID is the string
  `"<subject_id>|<property_id>|<object_id>"` produced by the canonicalization step in `link.py`
  (§4.3(B)); this is the key under which `support_frequency` aggregates the same triplet across runs.
- **Repair-leverage (RQ3) — a COUNT, defined in §4.6.** The number of claims that flip FABRICATED →
  grounded when the analyst restores missing evidence (edit-the-KG) and **re-runs**, aligned by
  `claim_id` within that one answer's before/after pair (`RepairResult.repair_leverage`). Cross-ref
  §4.6; this is the **only** place claims are aligned (within a single before/after, not across the N
  runs).
- **Two-layer perturbation grading (cross-ref §4.4).** **Withhold-from-context** (RQ2) hides evidence
  from the generation context only and **grades against the FULL reference**; its result is the
  multi-run **shift in the claim-status distribution** across {full, content-withheld,
  knowledge-withheld} — there is **no `absence_leverage` / `fabrication_induction` scalar**.
  **Edit-the-KG** (repair) changes the reference and **grades against the current (edited)** reference.
- **Statistical honesty (small-N; prominent).** A proportion `p` over N runs carries uncertainty
  `SE = sqrt(p(1-p)/N)` — the SE **of the proportion**, NOT the Bernoulli per-draw std (~0.5).
  **`N=20` is a FLOOR, not a target.** Error bars MUST be the **SE/CI of the proportion** with their
  meaning pinned in the caption, and the **small-N caveat must be prominent** in the analytics view.
- **`spurious_path`** (boolean + `spurious_reason`; only on Supportable claims). A multi-hop path
  passed the value-sensitive entailment gate but is **not legitimate support**. Detectors, priority
  order: **(1)** *relation/value illegitimacy* (primary, deterministic) — no path edge predicate is in
  the claim-relation's allowlist, or the path entails the claim's structure but not its asserted value;
  **(2)** *hub/length fragility* — path length ≥ k through a high-degree hub node with NLI margin just
  above `tau`; **(3)** *route non-robustness* (strongest, reuses the edit-the-KG runs) — after removing
  the single most-relevant triple, a *different* path still "entails" the claim ⇒ coincidental
  connectivity. Primary = (1)+(2); (3) is the cross-check where edit-the-KG runs already exist.

---

## 5. Question bank (books; P2)
Fixed set (statement §5.2): one-hop (retrieval), multi-hop (reasoning), ablated-entity questions;
KGR-style tiers. **Books:** content-only fact types descriptions carry but triples omit (genre/form,
tradition/affiliation, scope, descriptive role) + knowledge-absence questions. Authored against the
frozen slice; out-of-slice mentions → `unresolved_entities`.

---

## 6. Validation & controls (how we know the instrument is correct)
**Falsifiable controls (run before trusting any result):**
- **Negative control:** no-ablation fabrication must sit at the classifier-error floor; high ⇒ broken.
- **False-claim rejection:** a wrong-value claim about an in-reference entity must grade FABRICATED
  (`spurious_path=True`) under full context — catches an entity-match-only grader (verifies §4.3
  value-sensitivity). The one control whose absence lets a broken gate pass everything else.
- **Manipulation check:** ablating a content-only fact raises fabrication on questions targeting it
  and leaves structure-answerable claims unchanged (and symmetrically for knowledge-absence); a
  perturbation that flips claims it shouldn't ⇒ the generation/grading separation is leaking.
- **Modality-strength check:** report when a content axis is weak *because* the content is thin, not
  as a modality result.

**Mechanical-invariant tests (TDD):** sitelink-band filter; undirected path on `book→author←book`;
spurious shared-literal rejected; composed-manifest attribution; **bit-identical verification** (same
answer text => bit-identical `claims` list (the grading output), excluding metadata fields run_id/condition/sample_index); grade-against-reference invariant. **Adversarial
re-review** each phase; **empirical pilot** (~10 q on a small real slice) before locking.

---

## 7. Tech stack & licenses
Python 3.11+, `uv`; CPU/MPS-friendly. **Runtime:** dash, dash-cytoscape, plotly (MIT); networkx
(BSD-3); pydantic, pandas (BSD-3); pyarrow (Apache-2.0). **Build-time:** requests (Apache-2.0),
SPARQLWrapper (W3C), WikibaseIntegrator (MIT); QLever (public fallback). **Grounding:** RefChecker
(Apache-2.0) or vendored VeGraph/FActScore prompts (MIT); ReFinED (Apache-2.0, opt); MiniCheck
(Apache-2.0)+transformers/torch; LLM clients behind `BaseAIClient`. **Dev:** pytest, ruff (MIT).
*(VLM/MLX is image-axis — image spec.)*

## 8. End-to-end data flow
**Build (online, once):** `pipeline.py` → enumerate (band) + filter → fetch triples/description →
freeze `frozen/books/...`; author manifests + question bank + content labels. **Precompute
(offline-capable):** (question × {full, manifest entry} × **N runs**) assemble→`generate_answer`→
`ground_response` → `data/runs/<id>.json` (the N runs per question/condition), aggregated to
`AnswerDiagnostics` (§4.8: answer-level status mean+/-SE + support-frequency over KG-item IDs);
per-modality error. **Runtime (demo):** load frozen slice + the **frozen scenario** run-sets → render
panels → coordinated interactions are store/stylesheet updates. **Two live paths:** the repair loop
(edit-the-KG + re-run), and **live multi-run for a new question** (§4.6, N runs — minutes on the
local model; not used for the canned on-stage story).

## 9. Build sequence
P0-a scaffold/schema/config → P0-b books data layer + freeze + overlap check → P0-c perturbation +
mechanical tests → P0-d UI skeleton on mock + grounding stub → **P0 stop-and-review** → P1 grounding
+ entailment gate + per-modality error + §6 controls → **P2 books = M-BOOKS** (runs + controls PASS +
repair loop) → EX6 reports/recording. **After M-BOOKS:** open the image specs/tasks (artwork→taxa).

## 10. Reproducibility & demo safety
Live SPARQL build-time only (cached, deterministic order, QLever fallback). Answers/claims/groundings
precomputed + cached by input hash; manifest fixed before inspection; fixed model ids + `tau`. The
**reported figures and the on-stage demo run off frozen scenario run-sets** (reproducible, offline).
Live calls are (a) the repair loop (edit-the-KG + re-run) and (b) opt-in live multi-run for a *new*
question (temp > 0 for the across-run variance) — never the source of reported numbers. Classification
is deterministic given a fixed answer text, so a frozen scenario re-renders identically.

## 11. Risks & mitigations
Content/structure redundancy → books overlap check + content-only questions. "reasoned-supportable"
thorniest → path + entailment gate + `spurious_path` + per-modality error. Directed-path
false-negatives → undirected traversal + test. Spurious shared-literal paths → literal exclusion +
test. Small-N status mean/SE → SE of the proportion + prominent caveat, N=20 a floor. Cited backend
doesn't exist → reimplement KGR; vendor MIT prompts. Entity out of slice → `unresolved_entities`.
*(Image-axis risks: image specs.)*

## 12. Decisions & open assumptions
Generic `BaseAIClient` (local/open default + cloud); pluggable entity linker (`LabelAliasIndex`
default, ReFinED optional); classification = path search **+ entailment gate**; outgoing triples
collected but path search **undirected**; English labels; JSON store; `k`≈2–3, `tau`≈0.5 on a disjoint
fold. **G-TAX applied** (statement §5.5: content-inclusive RETRIEVED + `support_source`). **Open:**
RES1 (verify ref [7]).

## 13. Reuse dossier (condensed, text/core)
GraphEval — no code; idea only; `xz-liu/GraphEval` is a different paper. VeGraph (MIT) — vendor
prompts, replace its retrieval with our KG; don't import. CogMG (unlicensed) — repair-loop *pattern*
only. KGR (no code) — reimplement stages 1–4; drop retrofit; split supported→retrieved/
reasoned-supportable. RefChecker — `LLMExtractor` for Stage A. ReFinED — optional Wikidata EL.
MiniCheck — asymmetric NLI text gate. dash-cytoscape — stylesheet-selector highlighting; `nx.cytoscape_data`
+ adapter. QLever — independent SPARQL fallback. *(Image-axis reuse: VLM/MLX, visual probe, VISA
multi-layer-attribution framing — image specs.)*
