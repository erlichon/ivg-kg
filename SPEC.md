# SPEC — Interactive Visual Grounding of LLM Responses in Knowledge Graphs (`ivg-kg`)

> Implementation specification, **v2 — synced to the locked `project_statement.md`**
> (the scientific source of truth). This document translates the statement into a buildable
> architecture and is grounded in the reuse investigation + the empirical taxa range-map gate.
> Section refs like (§5.1) point to `project_statement.md`; `STATEMENT-CHANGES.md` is the audit
> trail of how the statement reached its locked form.
>
> **What changed vs SPEC v1** (to match the locked statement and fold in review fixes):
> in-context generation + **evidence vs. grading-reference** split; `reasoned` →
> **`reasoned-supportable`** with a `support_source` detail; a **two-slice** data layer
> (books + taxa range maps) with a **VLM** image axis (gated, Phase B); **undirected** path
> search; entailment-gate direction + literal-node exclusion + max-entailment path selection;
> **deterministic** repair-leverage; **per-claim perturbation list**; **per-modality + label**
> error accounting; QLever fallback; and a new **§6 Validation & controls**.

## 0. How to read this

- **§1–§2:** scope/phasing and the reuse reality-check (what exists vs what we reimplement).
- **§3:** architecture + the three statement seams + repo layout.
- **§4:** component specs with concrete interfaces — the build target.
- **§5:** question bank (Phase A / Phase B). **§6:** validation & controls (how we know the
  instrument is correct). **§7–§12:** stack, data flow, build order, reproducibility, risks,
  decisions, reuse dossier.

---

## 1. Scope and phasing

The project fully measures **one comparison** — text-content-absence vs. knowledge-absence on
books — and adds a **gated** image-content axis on a taxa slice. Two orthogonal phasings:

**Build phases**

| Phase | Goal | Components |
| --- | --- | --- |
| **P0 — Foundation** | Data layer + skeleton UI on mock data, joined by the typed schema. No real grounding. | Data layer (§4.1), schema (§4.2), perturbation interface (§4.4), UI skeleton (§4.5) on mock, grounding **stub**. |
| **P1 — Grounding** | Real in-context generation + three-way classifier + entailment gate; per-modality error. | Grounding backend (§4.3), classifier-error accounting (§4.7), §6 controls wired. |
| **P2 — Experiment** | Question bank, ablation runs, repair loop + leverage. | Question bank (§5), repair loop (§4.6), analytics. |

**Experiment phasing (per the locked statement, RQ2)**

- **Phase A (minimal, first):** per-slice within-modality manipulation — text-content on books,
  image-content on taxa, knowledge-absence on both — reported **per slice**; knowledge-absence
  is the shared *reference manipulation*, **no head-to-head text-vs-image claim**.
- **Phase B (second, time-permitting):** within-taxa three-way on the **same** entities (image +
  description + triples) for an *unconfounded* cross-modality contrast; **curtailed first** under
  schedule pressure, with no loss to the Phase-A core.

The image axis is **gated**: reported only if its non-redundancy check and visual-probe error
accounting hold (§6, §4.7); otherwise the project falls back to the books text-vs-knowledge spine.

---

## 2. Reuse reality-check (what actually exists)

The cited "backends" mostly do not exist as reusable code; we reimplement published methods and
adopt a small set of permissive OSS the statement doesn't name. (Full dossier in §13.)

### 2.1 Cited references

| Ref | Status | License | Verdict | We take |
| --- | --- | --- | --- | --- |
| **GraphEval** [4] (Sansford 2407.10793) | **No public code**; document/NLI-grounded, not KG-grounded. The statement-cited `xz-liu/GraphEval` is a *different* paper (2404.00942, large-scale-KG factuality benchmark). | paper CC-BY-4.0 | reference-only | the two-stage idea; **not** a backend. |
| **VeGraph** [6] (Pham et al., MIT) | Wikipedia-text + Elasticsearch; "graph" is a `\|\|`-delimited string; no Wikidata, no graph object; tokenizer hardcodes a Llama path; entry needs a running ES server. | **MIT** | vendor *prompts* | claim→triplet, hidden-entity-resolution, subclaim-verification prompt templates + few-shots. |
| **CogMG** [5] | Unlicensed; Chinese; LangChain 0.0.354; KoPL/KQA-Pro; Streamlit; pydantic v1; no live KG write-back; no claim-status tracking. | **none** | reference *pattern* | the repair-loop shape only. |
| **KGR** [1] | No public code. | n/a | reimplement | the 5-stage pipeline (extract→detect→select→verify→[drop retrofit]). Backbone. |
| **VISA** [2] | Document-screenshot bbox attribution; region attribution needs fine-tuning. | — | reference framing | the "attribution analogue" idea only. |

### 2.2 Additional OSS adopted (all permissive, offline-capable after first download)

| Capability | Library | License | Role |
| --- | --- | --- | --- |
| Wikidata pull (build-time) | **WikibaseIntegrator** | MIT | per-entity labels/descriptions/claims + datatype. |
| Bulk SPARQL enumeration (build-time) | **SPARQLWrapper** | W3C | `Q571` books / taxa `P181` enumeration + label resolution. |
| **SPARQL fallback** | **QLever** (`qlever.dev/api/wikidata`) | — (public service) | used when WDQS is degraded; **verified working during a WDQS outage in this project**. No `wikibase:label` service (resolve labels via `rdfs:label`/`schema:description`). |
| Optional full-dump subsetting | KGTK | MIT | one-shot dump→TSV if a slice grows large. |
| Graph store + path search | **NetworkX** | BSD-3 | frozen graph; `ego_graph`, `all_simple_paths`, undirected views. |
| Claim → triplets | **RefChecker** `LLMExtractor` | Apache-2.0 | offline `text → [head,relation,tail]`. Fallback: vendored KGR/VeGraph prompts. |
| Entity linking → QID | **ReFinED** *(optional adapter)* | Apache-2.0 | neural Wikidata-native EL; CPU/MPS at precompute. |
| Text entailment gate | **MiniCheck** | Apache-2.0 | asymmetric NLI (premise=evidence, hypothesis=claim); DeBERTa on CPU/MPS. |
| **VLM (image axis)** | **Qwen2.5-VL-7B** via **MLX / vllm-mlx** | Apache-2.0 (weights) / MIT (MLX) | image-grounded generation + the visual probe on Apple Silicon (MPS, 48 GB). |
| Subgraph renderer | **dash-cytoscape** | MIT | stylesheet-selector path highlighting; `tapNodeData`. |

Skipped: GENRE/mGENRE (CC-BY-NC), BLINK (archived), FacTool/Loki/VeriScore (online-only),
py2cytoscape (dead). Free-form **VLM-as-judge** is rejected as a grader (severe object
hallucination — POPE/MFC-Bench); the image gate is a **fixed-template binary probe** instead.

---

## 3. Architecture and the three seams

### 3.1 Seams (statement §7)
1. **Perturbation-as-interface** — pipeline consumes `(evidence, Perturbation)`; the perturbation
   withholds evidence from the **generation context**. New axes = new `Perturbation` subclasses.
2. **Uniform per-claim log** — every claim is a `ClaimRecord`; every axis writes the same shape.
3. **Controls-from-registry UI** — perturbation controls render from the registered types.

### 3.2 The load-bearing invariant (statement §5.3/§5.6)
```
 full evidence (KG-full triples + description + range-map image)
        │  Perturbation.withhold(...)            [generation only]
        ▼
 GENERATION CONTEXT ──► generate_answer (LLM, or VLM for image axis) ──► answer_text
                                                                          │
 GRADING REFERENCE  ◄── never ablated ──┐                                 ▼
 (KG-full triples + curated content labels)   ground_response: extract → link → classify
        └──────────────── claims graded against the REFERENCE, not the ablated context ──┘
```
A fact hidden from the generator stays in the grading reference, so it remains gradable; ablation
can only change the *answer*, never the grader. This is the correctness spine.

### 3.3 Repository layout
```
ivg-kg/
  pyproject.toml                 # uv, py>=3.11
  README.md  SPEC.md  STATEMENT-CHANGES.md  project_statement.md
  data/
    cache/                       # SPARQL response cache (gitignored)
    frozen/books/<id>/           # snapshot.json (+parquet), manifest.json
    frozen/taxa/<id>/            # snapshot.json + images/ + content_labels.json
    runs/<run_id>.json           # precomputed GroundingRun store (demo-safe)
  src/ivg_kg/
    schema.py                    # §4.2 typed contracts (pydantic v2)
    config.py                    # band, k-hop, tau, model ids, endpoints
    data/
      wikidata.py                # pull client (WDQS + QLever fallback), cache, rate-limit, UA
      graph_store.py             # build/freeze/load NetworkX <-> KGSnapshot; nx<->cytoscape
      taxa.py                    # taxa P181 pull + non-redundancy filter + image fetch/rasterize
      reference.py               # GradingReference (KG-full + content labels) assembly
      pipeline.py                # orchestrate per-slice pull->filter->build->freeze
    perturbation/
      base.py                    # Perturbation ABC + registry + AblationManifest
      text_content_absence.py    # withhold description from context
      image_content_absence.py   # withhold range-map image from context (gated)
      knowledge_absence.py       # withhold specified triples from context
    grounding/
      clients/base.py            # BaseAIClient ABC (text + multimodal)
      clients/local.py           # open LLM adapter (POC default)
      clients/vlm.py             # Qwen2.5-VL via MLX adapter (image axis)
      clients/cloud.py           # generic cloud adapter
      context.py                 # assemble generation context from evidence + perturbations
      generate.py                # generate_answer(question, context, client)
      extract.py                 # claim extraction (RefChecker / vendored prompts)
      link.py                    # BaseEntityLinker: LabelAliasIndex (default), ReFinED (opt)
      classify.py                # path search (undirected) + entailment gate -> status+source
      entailment.py              # text gate (MiniCheck) + visual probe (fixed-template) ABCs
      backend.py                 # ground_response(...); P0 stub
    mock/fixtures.py             # P0 hardcoded GroundingRun
  app/
    app.py  layout.py  callbacks.py
    panels/{answer,subgraph,analytics}.py
    charts/{status_dist,repair_history,coverage}.py
  tests/                         # §6 mechanical-invariant tests + unit tests
```

---

## 4. Component specifications

### 4.1 Data layer (P0; taxa slice P1/P2)

**Two slices.**
- **Books (`Q571`)** — text-content axis. Pull label, description (CONTENT), outgoing triples
  with human-readable property/value labels (STRUCTURE). Sitelink band default **5–40**.
- **Taxa (`P31=Q16521` with `P181` range map)** — image-content axis. Same band, **filtered to
  taxa whose range is not already a structured triple** (no `P9714`/`P183`/`P2341`), so the map is
  non-redundant by construction (gate verified: ~60% of banded range-map taxa qualify). Fetch the
  P181 image (rasterize SVG→PNG for the VLM); store under `frozen/taxa/<id>/images/`.

**Pull (`wikidata.py`).** Endpoint `query.wikidata.org/sparql`, no key; descriptive User-Agent,
rate-limit, retry/backoff on 429/5xx, disk cache keyed by query hash. **Fallback to QLever
(`qlever.dev/api/wikidata`)** when WDQS is degraded (no label service there → resolve labels via
`rdfs:label`/`schema:description`). Property-type filter keeps WikibaseItem/Time/Quantity/
Monolingualtext/String; drops ExternalId/Url/CommonsMedia/etc.

**`sitelink_band_filter`** — pure, inclusive, drops missing counts; applied server-side *and*
re-checked in Python (unit-tested seam).

**Freeze (`graph_store.py`).** Canonical JSON `snapshot.json` (+ optional parquet); NetworkX
**rebuilt from JSON on load** (no pickle). `nx_to_cyto_elements` adapter for the renderer.

**Grading reference (`reference.py`).** `GradingReference = KGSnapshot (KG-full) + list[ContentLabel]`.
`ContentLabel(entity_id, modality∈{text,image}, fact, source)` holds **content-only** facts the
triples omit — for books, content-only textual facts; for taxa, **hand-labelled range facts**
(double-labelled, §4.7). The reference is **never ablated**.

### 4.2 Typed schema — the contract (P0)

Pydantic v2; JSON-serializable for `dcc.Store`.

```python
class ClaimStatus(str, Enum):
    RETRIEVED = "retrieved"                 # directly grounded in ONE evidence item (triple OR content fact)
    REASONED_SUPPORTABLE = "reasoned-supportable"   # grounded only via a multi-hop path
    FABRICATED = "fabricated"               # not grounded in the reference

class SupportSource(str, Enum):             # detail orthogonal to status (the modality of support)
    DIRECT_TRIPLE; MULTI_HOP_PATH; TEXT_CONTENT; IMAGE_CONTENT; NONE

class Modality(str, Enum): STRUCTURE; TEXT; IMAGE
class ValueType(str, Enum): ITEM; TIME; QUANTITY; MONOLINGUAL; STRING
class TripleRef(BaseModel): subject_id; property_id; object_id: str|None = None   # selects triples to withhold

# --- KG shape ---
class KGNode(BaseModel):  id; label; description: str|None; sitelinks: int|None
                          image_path: str|None; kind="entity"          # image_path used for taxa P181
class KGEdge(BaseModel):  subject_id; property_id; property_label; object_id: str|None
                          object_label; value_type: ValueType
class KGSnapshot(BaseModel): snapshot_id; slice: str; domain_qid; nodes; edges; meta: dict
class ContentLabel(BaseModel): entity_id; modality: Modality; fact: str; source: str
class GradingReference(BaseModel): snapshot: KGSnapshot; content_labels: list[ContentLabel]

# --- pipeline I/O (inputs to the two load-bearing functions, §4.3) ---
class GenerationContext(BaseModel):       # the (possibly ablated) evidence shown to the generator
    entity_id; triples: list[KGEdge]; description: str | None; image_path: str | None
class GroundingConfig(BaseModel):
    k_hops: int = 2; tau: float = 0.5; linker: str = "label_alias"; entailment: str = "minicheck"

# --- per-claim log (statement §7) ---
class LinkedEntity(BaseModel): id; label; description: str|None; link_score: float|None
class PathEdge(BaseModel): subject_id; subject_label; property_id; property_label
                           object_id: str|None; object_label; traversed_forward: bool  # direction along path
class GroundingPath(BaseModel): edges: list[PathEdge]; node_ids: list[str]   # hops==len(edges)

class ClaimRecord(BaseModel):
    claim_id; text; status: ClaimStatus
    support_source: SupportSource                 # NEW: triple/path/text/image/none
    linked_entities: list[LinkedEntity]
    grounding_path: GroundingPath                 # empty unless MULTI_HOP_PATH
    active_perturbations: list[str] = []          # NEW: manifest-entry ids touching this claim's entities
    entailment_score: float | None                # gate score (MiniCheck or visual probe)
    spurious_path: bool = False                   # a path/evidence existed but failed entailment -> fabricated
    unresolved_entities: list[str] = []           # mentions not in the slice (distinct from fabricated)

class GroundingRun(BaseModel):
    run_id; question; answer_text; slice: str; phase: str          # "A" | "B"
    claims: list[ClaimRecord]
    active_perturbations: list[str] = []
    grading_reference_id: str | None
    error_rates: dict[str, float] = {}            # per modality path: {"text": .., "structure": .., "image": ..}
    def status_counts(self) -> dict[str,int]: ...
    def fabrication_rate(self) -> float: ...
```

> **Taxonomy note (consistent with statement §5.5 — applied):** `RETRIEVED` = *directly grounded
> in a single evidence item — a triple OR a content fact (description/image)*; not triples only.
> This is what lets a content-only true claim be graded grounded (not fabricated) and flip
> RETRIEVED→FABRICATED under content-absence — the RQ2 signal. `support_source` records which.

### 4.3 Grounding backend (P1; stub in P0)

Stable entry point from P0 (**two-graph signature** — the §3.2 invariant):
```python
def generate_answer(question: str, context: GenerationContext, client: BaseAIClient) -> str: ...

def ground_response(
    question: str, answer_text: str,
    reference: GradingReference,                 # ALWAYS KG-full + content labels (never ablated)
    *, active_perturbations: list[str], config: GroundingConfig,
) -> GroundingRun: ...
```
P0: both raise `NotImplementedError` + TODO; UI uses `mock/fixtures.py`.

**Context assembly (`context.py`).** Build `GenerationContext` from an entity's full evidence
(triples + description + image), then apply the active `Perturbation`s, which **withhold** their
targets. This is the only place ablation happens.

**Generation (`generate.py`).** `BaseAIClient` ABC; adapters: `LocalModelClient` (open LLM, POC
default), `VLMClient` (Qwen2.5-VL via MLX — used when an image is in context), `CloudAIClient`
(generic). No business logic imports a provider SDK. Answers cached by `hash(question, context)`.

**Stage A — extraction (`extract.py`).** RefChecker `LLMExtractor` (offline) → atomic claims /
`(head,relation,tail)`; fallback vendored KGR/VeGraph prompts. Cached.

**Stage B — entity linking (`link.py`).** `BaseEntityLinker`: `LabelAliasIndex` (default;
offline, deterministic; correct for the controlled slice) or `ReFinEDLinker` (optional). Mentions
outside the slice → `unresolved_entities` (not silently fabricated).

**Stage C — classification (`classify.py`).** Decision order:
1. **Direct triple** entailing the claim → `RETRIEVED` / `DIRECT_TRIPLE`.
2. **Content fact** (description or, for taxa, the curated image label) entailing the claim →
   `RETRIEVED` / `TEXT_CONTENT` or `IMAGE_CONTENT`. (Direct support precedes path search.)
3. **Multi-hop path**, 2..`k` hops, searched on an **undirected view** of the graph (a reasoned
   chain may traverse an edge against its stored direction; direction retained in `PathEdge`).
   Use `all_simple_paths`; **exclude literal nodes as intermediate waypoints** (only as
   endpoints) to avoid spurious shared-literal connectors. Among entailing paths pick the
   **highest-entailment** one (not the shortest). → `REASONED_SUPPORTABLE` / `MULTI_HOP_PATH`.
4. Else `FABRICATED` / `NONE`. If a triple/path/label existed but **failed entailment**, set
   `spurious_path=True` (the §10 "thorniest category" guard).

**Entailment gate (`entailment.py`).** `BaseEntailmentGate.entails(premise, hypothesis)->score`.
All per-claim grading uses **text NLI (MiniCheck)** — **premise = the serialized reference
evidence (triple / path / textual content fact / curated image-fact label), hypothesis = the
claim** (asymmetric; do not invert). The gate is **value-sensitive**: steps 1–3 fire only if the
evidence entails the claim's *asserted value*; a claim asserting a value the evidence contradicts
or omits **fails** entailment and falls through to `FABRICATED` (`spurious_path=True`). This
truth-sensitivity is what produces the RQ2 signal — a wrong value fabricated under ablation grades
FABRICATED while the correct value grades RETRIEVED (verified by the §6 false-claim control).
Image-content claims are graded the **same way**, against the **curated image-fact label rendered
as text** — *not* against the raster (statement §5.1). The **fixed-template visual probe
(VLM-on-raster)** is therefore **not** a per-claim grader; it is used only to **construct/verify
the curated image labels** (§4.7) and as a §6 validity check. `tau` and `k` are tuned on a
**disjoint fold**, never the test/eval fold (§4.7).

Classification always reads the **grading reference**, never the ablated context.

### 4.4 Perturbation interface (P0)

```python
class Perturbation(ABC):
    type_name: ClassVar[str]; id: str; modality: Modality
    @abstractmethod
    def withhold(self, ctx: GenerationContext) -> GenerationContext: ...   # remove from GENERATION context
    @abstractmethod
    def manifest_entry(self) -> dict: ...
    @classmethod
    def control_spec(cls) -> dict: ...

@register_perturbation
class TextContentAbsence(Perturbation):   # modality=TEXT  — withhold the description
    def __init__(self, entity_id: str): ...
@register_perturbation
class KnowledgeAbsence(Perturbation):     # modality=STRUCTURE — withhold specified triples (incompleteness ∪ retrieval-locality)
    def __init__(self, triples: list[TripleRef]): ...
@register_perturbation
class ImageContentAbsence(Perturbation):  # modality=IMAGE — withhold the range-map image (GATED)
    def __init__(self, entity_id: str): ...
```
- Perturbations act on the **generation context**, not the frozen KG (which is the reference).
- **Registry** powers UI control generation and manifest reconstruction.
- **`AblationManifest`** = base slice id + ordered perturbations; serializes to `manifest.json`
  (fixed before inspection); `apply_all`; `from_json`. A claim's `active_perturbations` lists the
  entries touching its linked entities (so composed manifests are attributable per claim).
  *Caveat:* attribution is by linked entity, so a single claim linking two entities under
  different perturbations has an ambiguous cause at claim granularity — harmless for the Phase-A
  single-axis-per-run design; relevant only to composed manifests.

### 4.5 Interface — three panels (P0 skeleton; P2 full)

dash-cytoscape; Dash 2.x imports; data/layout/callbacks separation; one `get_*_panel()` /
`make_*_figure()` each.
- **Answer panel** — claims colour-coded retrieved / reasoned-supportable / fabricated; click →
  store. (`html.Button` per claim or scatter with `customdata=claim_id`.)
- **Subgraph panel** — `nx.ego_graph` around linked entities; selected claim's support path
  highlighted by **appending stylesheet selectors** (never mutate the global stylesheet).
  Node detail on tap; **taxa nodes render the range-map image** (`background-image` / detail pane).
- **Analytics panel** — claim-status distribution, modality coverage per entity, repair history
  (fabrication before/after + leverage). Plotly figures.
- **Coordination:** `dcc.Store(selected_claim)` written by Answer-click; Subgraph + Analytics read
  it independently (no circular callbacks); `modified_timestamp` for initial-load reads.
- **Controls-from-registry:** iterate `available_perturbations()`/`control_spec()`.

### 4.6 Repair loop & repair-leverage (P2)

Statement §5.7 / RQ3. Analyst restores a withheld triple/description/image → re-ground.
- **State:** a `RepairSession` that re-adds the withheld evidence to the **generation context**
  for the target entity.
- **Primary metric (deterministic):** re-ground a **fixed** answer against the repaired context's
  claims (or re-run extraction+classification deterministically); `leverage = |{claims that flip
  FABRICATED→grounded}|` per **atomic restored item**, aligned by `claim_id`. Bit-identical across
  runs (a §6 test).
- **Secondary (illustrative):** a live VLM/LLM **regeneration** at temp 0, pinned model; report
  leverage as mean±CI over *N* runs. The one live call (demo-safe otherwise).

### 4.7 Classifier-error & label accounting (P1)

- The classifier error rate is measured on a held-out hand-labelled sample, **reported per
  modality path** — the **text NLI gate** (which grades text- *and* image-content claims against
  their serialized reference facts) and the **structure path search** — separately →
  `GroundingRun.error_rates`. (Statement §5.8 names the NLI gate and the visual path; reporting
  the structure path-search error as its own path is an intentional refinement.)
- **Reference-label construction & error (F2):** taxa image facts are turned into curated text
  labels with the **fixed-template visual probe (VLM-on-raster) as an assist**, then
  **double-labelled / spot-checked by hand**; report inter-annotator agreement and the visual
  probe's own error against the hand labels, so the image reference is not a single unverified
  judgement.
- `tau`/`k` are tuned on a **disjoint fold** from the reported error sample.

---

## 5. Question bank (P2)

Fixed set (statement §5.2): one-hop (retrieval), multi-hop (reasoning), ablated-entity questions;
KGR-style Simple/Complex/Multi-hop tiers.
- **Phase A (per slice):** books — content-only fact types descriptions carry but triples omit
  (genre/form, tradition/affiliation, scope, descriptive role); taxa — **range/distribution
  questions answerable only from the map** (e.g. "is its range coastal or inland?", "which
  continents?"); knowledge-absence questions on both slices.
- **Phase B (within-taxa, time-permitting):** for the same taxa entities, questions that probe
  image-content, (weak) text-content, and structure, enabling the unconfounded three-way — with
  the caveat that taxa text is generic (weak text effect ≠ modality).
Authored against the frozen slices; out-of-slice mentions → `unresolved_entities`.

---

## 6. Validation & controls (how we know the instrument is correct)

Correctness is earned by behaviour on known-answer cases + adversarial review + invariants, not
asserted. Built into the design:

**Falsifiable controls (run before trusting any result):**
- **Negative control:** with **no ablation** (full context), fabrication must sit at the
  classifier-error floor. High fabrication ⇒ pipeline broken (stop).
- **False-claim rejection (entailment-gate discrimination):** a claim asserting a *wrong value*
  about an entity that **is** in the reference must grade `FABRICATED` (`spurious_path=True`) even
  with full context. This is the control that catches an entity-match-only grader (it verifies the
  §4.3 value-sensitivity invariant); without it a broken gate passes every other control.
- **Manipulation check (validates §3.2):** ablating a *content-only* fact must raise fabrication
  on questions targeting that fact, and **leave structure-answerable claims unchanged** (and
  symmetrically for knowledge-absence). A perturbation that flips claims it shouldn't touch ⇒ the
  generation/grading separation is leaking.
- **Modality-strength check (Phase B honesty):** confirm taxa text-content ablation has small
  effect *because* descriptions are generic (content-poverty), reported as such — not as a
  modality result.

**Mechanical-invariant tests (TDD, P0+):**
- sitelink-band filter (inclusive, drops None);
- **undirected path found** on a hand-built `book→author←book` mini-KG (regression for the v1
  directed-only bug);
- **spurious shared-literal path rejected** (literal nodes excluded as waypoints);
- **composed-manifest attribution** (ablate E1.description + E2.triples → each affected claim
  attributed to the right entry);
- **deterministic leverage identity** (repeated deterministic re-grounding ⇒ identical leverage);
- **grade-against-reference invariant** (a claim whose evidence is withheld from generation is
  still gradable against KG-full).

**Adversarial re-review loop:** an independent reviewer over statement+SPEC each major phase;
iterate until no Critical/Major. **Empirical pilot:** freeze a small real slice, ~10 questions,
run the full pipeline, confirm the controls hold on real data before locking the experiment.

---

## 7. Tech stack & licenses

Python 3.11+, `uv`. CPU/MPS-friendly; no GPU required (optional later).

**Core (runtime):** dash, dash-cytoscape, plotly (MIT); networkx (BSD-3); pydantic, pandas
(BSD-3); pyarrow (Apache-2.0).
**Data (build-time):** requests (Apache-2.0), SPARQLWrapper (W3C), WikibaseIntegrator (MIT);
QLever (public fallback service); KGTK (MIT, optional).
**Grounding (P1):** RefChecker (Apache-2.0) or vendored VeGraph/FActScore prompts (MIT); ReFinED
(Apache-2.0, optional); MiniCheck (Apache-2.0)+transformers/torch; **Qwen2.5-VL via MLX**
(Apache-2.0 weights / MIT MLX) for the image axis; LLM/VLM client libs behind `BaseAIClient`.
**Dev:** pytest, ruff (MIT).

CogMG (unlicensed) and GENRE (non-commercial) are **not** vendored.

---

## 8. End-to-end data flow

**Build (online, once):** `pipeline.py` → enumerate (band) + filter → fetch triples/description
(+ taxa P181 images) → freeze `frozen/{books,taxa}/...`. Author manifests + question bank +
curated content labels.
**Precompute (offline-capable):** for each (question × {full, each manifest entry}): assemble
context → `generate_answer` → `ground_response` → `data/runs/<run_id>.json`. Compute per-modality
+ label error.
**Runtime (demo):** load frozen slices + precomputed runs → render panels from `GroundingRun` →
coordinated interactions are store/stylesheet updates (instant) → repair loop = the single live
call.

---

## 9. Build sequence (maps to statement §11)

1. **P0-a** scaffold, `schema.py`, `config.py`.
2. **P0-b** data layer: `wikidata.py` (WDQS+QLever, cache/UA/rate-limit), `graph_store.py`,
   `reference.py`, `pipeline.py`; freeze the **books** KG-full; re-run the content/structure check.
3. **P0-c** perturbation interface + manifest; §6 mechanical-invariant tests.
4. **P0-d** UI skeleton on `mock/fixtures.py` (layout, store, CB1–CB3, cytoscape highlight,
   analytics); grounding **stub**.
5. **P1** `BaseAIClient`+local adapter; context assembly + generation; extraction; linking;
   classifier (undirected path + entailment gate); per-modality+label error; §6 controls wired.
6. **P2 / Phase A — books first.** Take **books** text-content-vs-knowledge **end-to-end through
   P2** (runs complete *and* the §6 negative / false-claim / manipulation controls pass) + repair
   loop + deterministic leverage. This is milestone **M-BOOKS**.
7. **P2 / image axis — gated behind M-BOOKS.** **Books-first gate (hard):** no taxa/image work
   begins until M-BOOKS is validated — then **taxa** image-vs-knowledge (gated), and **Phase B**
   within-taxa three-way *if time permits* (curtailed first). **Dated backstop:** deadline
   **2026-06-14**; if M-BOOKS is not met by **2026-06-12 (T-2)**, the image axis is **dropped to
   future work** (statement §10 fallback — no loss to the books core), leaving the final two days
   for the write-up. Case studies; demo video backup.

**Foundation deliverable = P0 (a–d).** Stop and review before P1. **Books-first is a hard gate
(§9.6→§9.7):** the image axis is not started until books is validated end-to-end through P2;
this converts the statement's "curtail first" *option* into a triggered *action*.

---

## 10. Reproducibility & demo safety

Live SPARQL is build-time only (cached, deterministic order, QLever fallback). Answers/claims/
groundings precomputed + stored keyed by (question, manifest entry). Manifest fixed before
inspection. Fixed model ids + `tau`; LLM/VLM calls cached by input hash. Only the repair loop is
live (temp 0, pinned).

---

## 11. Risks & mitigations (maps to statement §10)

| Risk | Mitigation |
| --- | --- |
| Content/structure redundancy nulls the comparison | books overlap check; content-only question types; taxa filtered to non-redundant range maps (gate). |
| Obscurity vs reliability | sitelink band 5–40, re-checked in Python. |
| "reasoned-supportable" thorniest | path + entailment gate; `spurious_path`; per-modality error reports the category. |
| **Modality⊥domain confound (RQ2)** | per-slice reporting + knowledge-absence anchor (Phase A); unconfounded contrast only within taxa (Phase B); modality-strength check (§6). |
| Image-axis cost/validity | gated on non-redundancy + visual-probe error; hand-labels double-checked; SVG rasterized; **fallback** to books spine with no core loss. |
| Directed path false-negatives | undirected traversal (§4.3) + §6 regression test. |
| Spurious shared-literal paths | literal nodes excluded as waypoints + §6 test. |
| Repair-leverage nondeterminism | deterministic primary metric; live regen illustrative only. |
| Cited backend doesn't exist | reimplement KGR; vendor MIT prompts; adopt permissive OSS (§2). |
| Entity out of slice | `unresolved_entities` distinct from fabricated. |

---

## 12. Decisions & open assumptions

**Locked with the user:** generic `BaseAIClient` (local/open default + cloud); entity linking
pluggable (`LabelAliasIndex` default, ReFinED optional); classification = path search **+
entailment gate**; **multimodal via taxa range maps**, gated, **Phase A then Phase B**; title kept
("Multimodal", scoped per §1).

**Assumptions:** outgoing triples collected, but path search is **undirected**; English labels;
property-type filter as in §4.1; deterministic by-QID sampling; JSON canonical store; `k`≈2–3,
`tau`≈0.5 tuned on a disjoint fold.

**G-TAX (APPLIED).** Statement §5.5 now defines `RETRIEVED` as *directly grounded in a single
evidence item — a triple **or** a content fact (description / curated image-fact label)*, with
`support_source` recording which (applied during the statement lock; see `STATEMENT-CHANGES.md`).
This is what lets content-only true claims grade as grounded and flip RETRIEVED→FABRICATED under
content-absence (the RQ2 signal). Statement and SPEC are consistent on this; no open action.

---

## 13. Reuse dossier (condensed)

- **GraphEval (Sansford 2407.10793)** — no code; text/NLI vs a *document*, not a KG. Idea only.
  `xz-liu/GraphEval` = different paper (2404.00942, MIT) — skip.
- **VeGraph (MIT)** — vendor the claim→triplet / hidden-entity / subclaim prompts + few-shots;
  replace its Elasticsearch/Wikipedia retrieval with our KG; do not import (hardcoded Llama
  tokenizer path; needs a running ES server).
- **CogMG (unlicensed)** — repair-loop *pattern* only; build ours (CogMG has no live KG write-back
  and no claim-status tracking; pydantic v1 conflicts with Dash).
- **KGR (no code)** — reimplement stages 1–4 from the paper prompts; drop retrofit; split
  supported into retrieved vs reasoned-supportable after fact selection; cache extraction.
- **RefChecker (Apache-2.0)** — `LLMExtractor` for Stage A; NLI checkers reference-only.
- **ReFinED (Apache-2.0)** — optional Wikidata-native EL, offline after download, CPU/MPS.
- **MiniCheck (Apache-2.0)** — asymmetric NLI text gate (premise=evidence, hypothesis=claim).
- **Qwen2.5-VL via MLX (Apache-2.0/MIT)** — image-grounded generation + visual probe on MPS/48 GB;
  free-form VLM-as-judge rejected (POPE/MFC-Bench hallucination) in favour of a fixed-template probe.
- **Wikidata image facts** — only **P181 taxon range maps** passed the non-redundancy gate; **P18
  book images** decorative; **artwork P180 "depicts"** is *structurally redundant* (the depicted
  facts are already triples) — both excluded.
- **dash-cytoscape (MIT)** — stylesheet-selector highlighting; `nx.cytoscape_data` + ~10-line
  adapter; `dash-sample-apps/dash-cytoscape-lda` is a structural reference.
- **QLever (`qlever.dev/api/wikidata`)** — independent SPARQL endpoint; data-layer fallback when
  WDQS is degraded (no `wikibase:label` service).
```
