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
         charts/{status_dist,repair_history,coverage}.py
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
    REASONED_SUPPORTABLE = "reasoned-supportable"   # grounded only via a multi-hop path
    FABRICATED = "fabricated"
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
    claim_id; text; status: ClaimStatus; support_source: SupportSource
    linked_entities: list[LinkedEntity]; grounding_path: GroundingPath
    active_perturbations: list[str] = []; entailment_score: float|None
    spurious_path: bool = False; unresolved_entities: list[str] = []
class GroundingRun(BaseModel):
    run_id; question; answer_text; slice: str; phase: str
    claims: list[ClaimRecord]; active_perturbations: list[str] = []
    grading_reference_id: str|None; error_rates: dict[str,float] = {}   # per modality path
    def status_counts(self)->dict[str,int]: ...
    def fabrication_rate(self)->float: ...
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
- **Context (`context.py`):** build `GenerationContext` from full evidence, then apply active
  `Perturbation.withhold`. The **only** place ablation happens.
- **Generation (`generate.py`):** `BaseAIClient` ABC; `LocalModelClient` (POC default) + `CloudAIClient`.
  No provider SDK in business logic. Cached by `hash(question, context)`. *(VLM client for image
  generation: `SPEC-image-artwork.md`.)*
- **A — extraction (`extract.py`):** RefChecker `LLMExtractor` → atomic claims / `(h,r,t)`; vendored
  KGR/VeGraph fallback; cached.
- **B — linking (`link.py`):** `BaseEntityLinker`: `LabelAliasIndex` (default) / `ReFinEDLinker` (opt);
  out-of-slice → `unresolved_entities`.
- **C — classification (`classify.py`):** decision order — (1) direct triple entailing → RETRIEVED/
  DIRECT_TRIPLE; (2) content fact (description / curated label) entailing → RETRIEVED/TEXT_CONTENT
  (IMAGE_CONTENT on the image axis); (3) **undirected** multi-hop path 2..k (`all_simple_paths`,
  **literal nodes excluded as waypoints**, **highest-entailment** path) entailing → REASONED_SUPPORTABLE/
  MULTI_HOP_PATH; (4) else FABRICATED/NONE, `spurious_path=True` if evidence existed but failed entailment.
- **Entailment gate (`entailment.py`):** `BaseEntailmentGate.entails(premise, hypothesis)`. Text NLI
  (**MiniCheck**): premise = serialized reference evidence, hypothesis = claim (asymmetric — do not
  invert). **Value-sensitive**: a claim whose asserted value the evidence contradicts/omits fails →
  FABRICATED. Tunes `tau`/`k` on a **disjoint fold**. *(Image-content claims grade by text NLI
  against the curated label, not the raster; the visual probe constructs/verifies labels — image spec.)*
Classification always reads the **grading reference**, never the ablated context.

### 4.4 Perturbation interface (P0)
`Perturbation` ABC (`type_name`, `id`, `modality`, `withhold(ctx)->ctx`, `manifest_entry()`,
`control_spec()`) + registry + `AblationManifest` (serialize/`from_json`, fixed before inspection).
Classes: `TextContentAbsence(entity_id)`, `KnowledgeAbsence(triples: list[TripleRef])`,
`ImageContentAbsence(entity_id)` (generic withhold-the-image seam; its *data/grading* is the image
axis). All withhold from the **generation context**, not the frozen KG. A claim's
`active_perturbations` lists entries touching its linked entities (composed-manifest attributable;
caveat: ambiguous if one claim links two entities under different perturbations — fine for Phase-A
single-axis runs).

### 4.5 Interface — three panels (P0 skeleton; P2 full)
dash-cytoscape; Dash 2.x; data/layout/callbacks separation; one `get_*_panel()` / `make_*_figure()`.
- **Answer panel** — claims colour-coded retrieved / reasoned-supportable / fabricated; click → store.
- **Subgraph panel** — `nx.ego_graph` around linked entities; support path highlighted by **appending
  stylesheet selectors** (never mutate the global stylesheet); node detail on tap; **entity-detail
  pane shows the entity image when present** (P18 — demo-visual even though not grounding evidence:
  book covers / author portraits). *(On the image axis the panel also shows the slice image + claim→
  region/visual attribution — image spec.)*
- **Analytics panel** — claim-status distribution, modality coverage, repair history + **leverage**;
  **Trust indicator** rendering `GroundingRun.error_rates` (per-modality classifier error, always
  visible — the MMA-model Trust pillar). Bars start at y=0; node sizing by area.
- **Coordination:** `dcc.Store(selected_claim)` written by Answer-click; Subgraph + Analytics read it
  independently (no circular callbacks); `modified_timestamp` for initial-load reads.
- **Controls-from-registry:** iterate `available_perturbations()`/`control_spec()`.

### 4.6 Repair loop & repair-leverage (P2)
`RepairSession` re-adds withheld evidence to the **generation context**. **Primary metric
(deterministic):** re-ground a fixed answer; `leverage = |{claims FABRICATED→grounded}|` per atomic
restored item, aligned by `claim_id`; bit-identical across runs (§6 test). **Secondary
(illustrative):** live regeneration at temp 0, pinned model, mean±CI over N — the one live call.

### 4.7 Classifier-error & label accounting (P1)
Error rate on a held-out hand-labelled sample, **per modality path** — text-NLI gate and structure
path search separately → `GroundingRun.error_rates`. Content labels double-labelled / spot-checked
(IAA reported). `tau`/`k` tuned on a **disjoint fold** from the reported sample. *(Image visual-probe
error + image-label IAA: image spec.)*

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
spurious shared-literal rejected; composed-manifest attribution; deterministic-leverage identity;
grade-against-reference invariant. **Adversarial re-review** each phase; **empirical pilot** (~10 q on
a small real slice) before locking.

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
(offline-capable):** (question × {full, manifest entry}) assemble→`generate_answer`→`ground_response`
→ `data/runs/<id>.json`; per-modality error. **Runtime (demo):** load frozen slice + precomputed
runs → render panels → coordinated interactions are store/stylesheet updates → repair loop = the one
live call.

## 9. Build sequence
P0-a scaffold/schema/config → P0-b books data layer + freeze + overlap check → P0-c perturbation +
mechanical tests → P0-d UI skeleton on mock + grounding stub → **P0 stop-and-review** → P1 grounding
+ entailment gate + per-modality error + §6 controls → **P2 books = M-BOOKS** (runs + controls PASS +
repair loop) → EX6 reports/recording. **After M-BOOKS:** open the image specs/tasks (artwork→taxa).

## 10. Reproducibility & demo safety
Live SPARQL build-time only (cached, deterministic order, QLever fallback). Answers/claims/groundings
precomputed + cached by input hash; manifest fixed before inspection; fixed model ids + `tau`. Only
the repair loop is live (temp 0, pinned).

## 11. Risks & mitigations
Content/structure redundancy → books overlap check + content-only questions. "reasoned-supportable"
thorniest → path + entailment gate + `spurious_path` + per-modality error. Directed-path
false-negatives → undirected traversal + test. Spurious shared-literal paths → literal exclusion +
test. Repair-leverage nondeterminism → deterministic primary metric. Cited backend doesn't exist →
reimplement KGR; vendor MIT prompts. Entity out of slice → `unresolved_entities`. *(Image-axis risks:
image specs.)*

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
