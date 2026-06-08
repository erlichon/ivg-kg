# Proposed amendments to `project_statement.md` (v2 — revised after independent review)

> **Status: PROPOSAL for review — `project_statement.md` is unchanged.** This is **v2**,
> revised to address an independent review of v1. Each item gives location, current text,
> proposed text, and why. Implementation mechanics stay in `SPEC.md`; only scientific
> framing is touched here.
>
> Change groups: **G-MM** multimodal resolution, **G-RAG** in-context/grounding split,
> **G-RS** reasoned-supportable, **G-7** [7] softening, **G-CITE** GraphEval de-scoping +
> citations. A **changelog vs v1** is at the end.
>
> Approve / edit per item; on sign-off I apply accepted items to the statement, then sync
> `SPEC.md` and re-review.

---

## Summary

The empirical gate (live, via QLever; independently re-verified) **passed** for taxa range
maps: ~16k range-map taxa in the 5–40 sitelink band, **~60% with no structured range
property**, and descriptions are generic stubs that never carry range. So a range-map image
carries a queryable spatial fact absent from triples (majority) and description (always).

**Key framing correction from the review:** the two content modalities live on **two domain
slices** — text-content on **books** (rich descriptions), image-content on **taxa** (range
maps; taxa descriptions are too thin for a text axis). A *taxon* entity is itself multimodal
(image + description + triples, per §1's own definition), but the project does **not** run all
modalities on one slice. The amendments therefore (a) keep multimodality honest by stating it
is realized **across two slices at the study level**, (b) treat the image axis as a **gated
secondary** axis rather than a co-equal shipped core, and (c) separate *evidence* from the
*grading reference* so image grounding is coherent.

The review also requires the in-context/grounding split (G-RAG, the load-bearing correctness
fix), the reasoned→reasoned-supportable rename (G-RS), the [7] softening (G-7), and the
GraphEval de-scoping + citation fixes (G-CITE) — all confirmed correct and verified.

---

## G-MM — Multimodal resolution (gate PASSED; gated secondary image axis on a second slice)

### G-MM-0 · Title (line 1) and §1 "multimodal KG" definition (line 12) — NEW in v2
**Decision required (one genuine choice; recommendation given).** Because the two modalities
live on two slices, the bare term "multimodal **knowledge graph**" overclaims a single
tri-modal substrate. Two honest options:

- **Option A (recommended): keep "Multimodal," scope it explicitly.** Keep the title. Amend
  §1 so "multimodal" is realized on the **taxa slice** (each taxon attaches a fact-bearing
  range-map image, a description, and triples — matching §1's own definition) and clarify that
  the study compares evidence modalities **across two curated slices** (books for text-content,
  taxa for image-content). Lowest disruption; defensible because taxa genuinely satisfy §1's
  multimodal-KG definition.
- **Option B: retitle to grounding-across-modalities.** e.g. *"Interactive Visual Grounding of
  LLM Responses Across Evidence Modalities in Knowledge Graphs."* Most literally accurate; drops
  the contested noun phrase but changes the project's established name (`ivg-kg`).

**§1 (line 12) current:** "*multimodal* KGs additionally attach images and textual descriptions
to each entity, making them a rich substrate for multimedia analytics."
**Proposed (under Option A):** keep, and add one clause: "...— a property our **taxa slice**
instantiates (fact-bearing range-map images alongside descriptions and triples), while the
study compares evidence modalities across this slice and a text-rich **books** slice."

### G-MM-1 · §2, content-absence bullet (line 20)
**Current:**
> Images are a secondary, optional modality: entity images in general-purpose KGs are
> frequently *decorative* (identity-confirming rather than fact-bearing), so they are included
> only where the chosen domain's images demonstrably encode queryable facts.

**Proposed:**
> Images are a **gated second content modality, admitted only where they demonstrably encode
> queryable facts**. General-purpose KG images (Wikidata P18, and — verified here — book
> cover/identity images) are *decorative* and excluded. The image modality is realized on a
> **second, image-bearing slice — biological taxa with range-map images (Wikidata P181)** —
> where an empirical non-redundancy check (§10) confirms the map carries spatial-distribution
> facts absent from both the taxon's triples (for the majority) and its description (always).
> Text content (descriptions) remains the **primary** content modality, anchored on the books
> slice.

*(Per review F-MM-E, the artwork/P180 negative finding is moved to SPEC, not cited here.)*

### G-MM-2 · §2, "multimedia load-bearing" sentence (line 23)
**Current:** "...the experiment *is* a comparison between structural and (textual) content
evidence."
**Proposed:** "...the experiment *is* a comparison **across evidence modalities — structural
knowledge, textual content (books), and image content (taxa range maps)** — of how the
modality of missing evidence changes grounding."

### G-MM-3 · §5.1 — second slice + evidence-vs-reference separation (REVISED in v2 per F-MM-C)
**Add** a paragraph: a **second slice, taxa with range maps (P181)**, supplies the
image-content axis; sampled in the same sitelink band and **filtered to taxa whose range is
not already a structured triple**, guaranteeing image non-redundancy by construction (the
taxa analogue of the books band). Define two distinct sets explicitly:

- **Evidence** (what the generator may or may not see): triples + description + range-map
  image. A perturbation withholds from this.
- **Grading reference** (what the classifier grades against, never ablated): **KG-full
  triples + a small curated set of content-only labels** (the textual content-only facts for
  books; the hand-labelled map facts for taxa). The image is *evidence*, not a label — image
  claims are graded against the curated label, not the raster.

Note the data-layer fallback: when WDQS is degraded, the pull uses the independent **QLever**
endpoint.

### G-MM-4 · §7 Architecture — image-absence as a GATED axis on the interface (REVISED in v2 per F-MM-A)
**Current:** "the minimal version ships content-ablation and knowledge-absence."
**Proposed:** "the minimal core fully instruments **text-content-absence vs. knowledge-absence**
on books. The **perturbation-as-interface** seam additionally carries an
**image-content-absence** axis on the taxa slice, **gated**: it is reported as a result iff its
per-domain non-redundancy check and the visual-probe error accounting hold (§10). It is an
axis on the same seam, not a rewrite of the pipeline."
Leave entity-linking / conflict-staleness, the multi-axis factorial, and live diagnosis
**deferred** as before.

*(Resolves the v1 contradiction with §10 thinness and with the G-MM-6 fallback.)*

### G-MM-5 · §9 Implementation (line 95) — at altitude (REVISED in v2 per F-MM-D)
**Add:** "the image axis uses a **local open VLM** for image-grounded answer generation, and
image-claim support is checked with a **fixed-template binary visual probe** (not free-form
VLM judging, which is unreliable); one live VLM/LLM call drives repair regeneration." The
specific model id (Qwen2.5-VL-7B via MLX) and the POPE-style probe live in `SPEC.md`, not here.

### G-MM-6 · §10 Risks — image-axis honesty + data dependency
**Add a risk bullet** *Image-axis cost and validity:* genuine image non-redundancy means the
fact is **not in the KG**, so image claims are graded against a **small hand-labelled set**,
not triples; VLMs hallucinate (mitigated by the fixed-template probe); range maps are often SVG
(rasterized). The gate passed for taxa but **must be re-checked per domain before locking.**
**Fallback:** if the image axis underperforms, the project reports the fully-measured
**text-content vs. knowledge-absence** spine on books with no loss to the core contribution.
**Reconcile (per review):** update §5.1 (line 57, "entity images via P18 only as a secondary
modality") and §10 (line 101, "images dropped as a primary modality") so they read as
"general-purpose P18 images dropped; a *dedicated fact-bearing* image axis (taxa P181 range
maps) added as a gated secondary axis" — otherwise the new axis contradicts that prose.

---

## G-RAG — in-context generation / full-reference grounding (the load-bearing fix)

### G-RAG-1 · §5.3 Answer generation (line 59)
**Current:** "The LLM (or VLM, where image content is in scope) produces a chain-of-thought
draft per question; precomputed and stored for demo safety."
**Proposed:** "The model answers **in-context**: the (possibly ablated) evidence for the target
entity — triples, description, and range-map image where in scope — is assembled into the
prompt, and the LLM/VLM produces a chain-of-thought draft from that context (precomputed and
stored for demo safety). **A perturbation removes evidence from this generation context** (it
does not alter the grading reference). The image axis uses a VLM." *(Avoid the word "RAG" in the
statement — the context is a fixed per-entity assembly, not corpus retrieval.)*

### G-RAG-2 · §5.6 Coverage & ablation (line 62)
**Add:** "Classification always grades against the **full grading reference** (§5.1), never the
ablated context; ablation changes only what the *generator* sees, so a fact hidden from the
model remains gradable. Knowledge-absence is realized as **withholding triples from the
generation context** (covering both incompleteness and retrieval-locality, per §2) while those
triples remain in the grading reference — which is also what makes the repair loop's 'restore
evidence → regenerate' meaningful."

**Why:** without this, ablation cannot causally affect the answer and hidden-evidence claims
would be fabricated-by-construction (review F1/F2/F7, re-confirmed). §2 already implies it.

---

## G-RS — "reasoned" → "reasoned-supportable"; reframe RQ1

### G-RS-1 · RQ1 (lines 40–41)
**Proposed:** "Can claim-level attribution against the knowledge graph reliably separate
**retrieved** (a direct triple supports the claim), **reasoned-supportable** (a multi-hop path
supports it), and **fabricated** (no supporting evidence), and can a visual interface make this
distinction legible to a non-expert? *We make claim **supportability** legible — whether the
evidence to ground the claim exists in the graph — not the model's internal reasoning process.
Novelty lies in the visual legibility and the three-way split, not the attribution algorithm.*"

### G-RS-2 · Propagate the rename (EXPANDED in v2 per F-RS-B)
Replace "reasoned" with "reasoned-supportable" at: §4 contribution 1 (line 51); §5.5 (line 61);
§6 panels (lines 68–69); §10 (line 103). **Plus §1 (line 12):** the plain-language "facts it
obtained by reasoning over several pieces of structured knowledge" — add a one-clause bridge so
§1's informal "reasoning" is reconciled with the formal **reasoned-supportable** label used in
§3+ (avoid a vocabulary split in the most-read paragraph).

### G-RS-3 · §5.5 grounding mechanism (line 61) — entailment gate, at altitude
**Proposed:** "Per claim: entity-link to KG nodes; a direct triple that **entails** the claim →
*retrieved*; else a multi-hop path that **entails** the claim → *reasoned-supportable*; else
*fabricated*. Entailment is checked by a lightweight gate (textual claims: an NLI model; image
claims: a fixed-template visual probe) so a merely-existing path that does not support the claim
is **not** mislabeled. The attribution **reimplements the KGR-style claim→triple pipeline**
(§2 / references), extended from two-way to this three-way split."

---

## G-7 — soften the [7] "grounded in mechanism" claim

### G-7-1 · §2, mechanism bullet (line 30)
**Proposed:** "**The reasoning-vs-retrieval distinction is motivated by mechanism.** '[7]'
shows mechanistically that, when grounding evidence is absent from context, models revert to
parametric memory. [7] studies the model's **internal states**; our tool does not measure that
mechanism — it makes **claim supportability against the KG legible** per claim, which [7]
motivates but which we do not claim to measure."
**Also (per review F-7-A):** verify the inherited phrase "generalises from single-hop to
multi-hop" against [7]'s body before locking; soften if the paper does not state it explicitly.

---

## G-CITE — GraphEval de-scoping and citation fixes

### G-CITE-1 · §2, claim-attribution bullet (line 29)
**Proposed:** "**Claim-level attribution is adopted in spirit, then reimplemented.** KGR [1]
decomposes a response into atomic claims and verifies them against KG triples, and VeGraph [6]
represents claims as triplets and verifies them iteratively. None ships reusable **KG-grounded**
code for our setting (GraphEval [4] is document/NLI-grounded with no public code; VeGraph is
Wikipedia-derived), so we **reimplement** the KGR-style pipeline and **extend** it from a two-way
(supported / unsupported) judgement to the three-way **retrieved / reasoned-supportable /
fabricated** distinction." *(Repo-level detail like "Elasticsearch" stays in SPEC, per review
F-CITE-A.)*

### G-CITE-2 · Reference [4] (line 128) + knowledge-base note (line 120)
Remove "Code: github.com/xz-liu/GraphEval"; add: *no public code released for this paper;
`github.com/xz-liu/GraphEval` is an unrelated work (Liu et al., arXiv:2404.00942, a large-scale-KG
factuality benchmark).*

### G-CITE-3 · Reference [6] (line 132) — EXPANDED in v2 per F-CITE-B
Add authors **Pham, H., Nguyen, T.-D., Bui, K.-H. N.** *and* the missing **arXiv:2505.22993**
(currently [6] is the only reference without an arXiv id).

### G-CITE-4 · §11 Planning (lines 109–110) — EXPANDED in v2
Step 2: "Build the grounding backend (**reimplement KGR-style attribution; no usable upstream
code**) + three-way classifier with the entailment gate; quantify its error rate." Step 1: note
the **second-slice (taxa/range-map) freeze** alongside the books freeze. Add a planning step for
the **gated VLM image axis**.

---

## G-EVAL — extend evaluation to the visual path (NEW in v2 per review "missing items")

### G-EVAL-1 · §4 Contribution 2 (line 52)
**Current:** "...on **a curated multimodal KG**." (singular — now inaccurate)
**Proposed:** "...on **curated KG slices** (a text-rich books slice and a multimodal taxa
slice)."

### G-EVAL-2 · §8 Evaluation + §5.8 error accounting (lines 84–91, 64)
**Add:** the classifier-error accounting (§5.8) is reported **per modality path** — the textual
NLI gate and the **visual probe separately** (the visual path is expected to be noisier); §8's
analytic evidence includes the image-axis results only insofar as the visual-probe error rate
supports them (ties to the G-MM-6 gate/fallback).

---

## Items intentionally NOT promoted to the statement (stay in `SPEC.md`)

Path-search directionality; NLI premise/hypothesis direction; `tau`/`k` tuning on disjoint folds;
repair-leverage determinism + metric definition; per-claim perturbation attribution as a list;
literal-node path exclusion; provenance/guidance UI; the specific VLM id + POPE probe details;
the artwork/P180 negative finding; VeGraph's Elasticsearch/tokenizer specifics.

---

## Changelog vs v1 (what the independent review changed)

- **G-MM-4 rewritten:** image-absence is a **gated secondary axis on the perturbation seam**,
  not a "shipped third core perturbation" (fixed the contradiction with §7/§10 and with the
  G-MM-6 fallback).
- **G-MM-0 added:** title + §1 "multimodal KG" definition reconciled (two-slice framing); a
  genuine title choice surfaced (recommend Option A: keep + scope).
- **G-MM-3 revised:** explicit **evidence vs. grading-reference** split; the image is evidence,
  graded against a curated label, not treated as gradable ground truth.
- **G-MM-5 de-scoped:** specific VLM/probe names moved to SPEC; statement stays at altitude.
- **G-MM-1 trimmed:** artwork/P180 example moved to SPEC.
- **G-RS-2 expanded:** §1 line-12 "reasoning" added to the rename/reconciliation list.
- **G-CITE-3 expanded:** add arXiv:2505.22993 to [6].
- **G-EVAL added:** §4 contribution 2 singular→slices; §8/§5.8 error accounting extended to the
  visual path.
- **G-7-1:** added an action to verify the inherited "single-hop to multi-hop" phrasing against
  [7]'s body.

---

## Addendum — applied after review round 2 (RQ2 confound fix + F2)

Review round 2 verdict was SOUND-WITH-MINOR-FIXES; it found a **modality/domain confound** in
RQ2 (text-content axis on books, image-content axis on taxa → modality collinear with domain).
Resolved by **Fix A + Fix B, explicitly staged** (user decision):

- **G-RQ2-A (applied):** RQ2 reframed into **Phase A (minimal, first)** — per-slice
  within-modality manipulation with **knowledge-absence as the shared cross-slice anchor**, and
  **no head-to-head text-vs-image claim** (domain confound acknowledged). Touched §2 (multimedia
  sentence), RQ2 (§3), contribution 2 (§4).
- **G-RQ2-B (applied):** **Phase B (second step, time-permitting)** — the **within-taxa
  three-way** comparison (same taxa entities carry image + description + triples) as the
  *unconfounded* cross-modality contrast, with the caveat that taxa descriptions are generic
  (a weak text effect there = content-poverty, not modality). Stated as **curtailed first if
  time is short, with no loss to the Phase-A core.** Threaded into §2, RQ2, §4, §10 fallback,
  and §11 step 5.
- **F2 (applied):** §5.8 now also accounts for the **hand-labelled image reference's** own
  error (double-labelled / spot-checked), since the image axis grades against curated labels,
  not the KG.

**Final polish (applied after review round 3 / verification — statement now LOCK-READY):**
§8 "gated secondary" → "gated (validity-conditional)" (reconciles with image-content's Phase-A
membership); §1 cross-slice phrasing softened to per-slice + within-taxa; RQ2 knowledge-absence
anchor role clarified (shared reference manipulation, not a cross-modality comparand); §1 and
§5.1 readability run-ons split.
**Still open:** F6 — reference [7] (arXiv:2605.26362) is one month old and not yet in the
knowledge base, so the [7]-grounded sentence in §2 is **provisional until the PDF is confirmed**
(requires the user).

---

## Addendum — applied after the combined statement+SPEC review (G-TAX + image-grading)

The combined review (verdict: MINOR-FIXES, consistent-and-buildable) endorsed the G-TAX
resolution (keep three-way status + `support_source`, no fourth status) and found two coherence
items, both now applied to the SPEC and reconciled into the statement:

- **G-TAX (applied to §5.5):** `RETRIEVED` = a **single piece of reference evidence that entails
  the claim — a direct triple *or* a content fact (description / curated image-fact label)**, with
  the evidence modality recorded (SPEC `support_source`). This lets content-only true claims grade
  as grounded and flip RETRIEVED→FABRICATED under content-absence (the RQ2 signal); without it
  content claims would be fabricated-by-construction and the §6 negative control would fail.
- **Value-sensitivity (applied to §5.5):** the entailment gate is value-sensitive — a claim
  asserting a value the evidence contradicts/omits fails the gate → fabricated. SPEC adds a §6
  "false-claim rejection" control (the check that catches an entity-match-only grader).
- **Image-grading reconciliation (applied to §5.5 + §9):** image-content claims are graded by NLI
  against the **curated label, not the raster** (resolves the latent §5.1↔§5.5 contradiction); the
  fixed-template visual probe is for **constructing/verifying** those labels, not per-claim grading.

SPEC-side fixes from the same review (no statement impact): under-typed contracts now defined
(`ValueType`/`TripleRef`/`GenerationContext`/`GroundingConfig`); structure-path error reported as
its own path; composed-manifest attribution caveat.

**Statement and SPEC are now consistent and build-ready (P0).** Only F6 remains, on the user.
