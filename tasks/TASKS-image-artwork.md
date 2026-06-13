# TASKS — image-content axis (ARTWORK, primary) · COMMITTED, sequenced post-M-BOOKS

> **DO NOT OPEN until M-BOOKS** (books validated end-to-end; see `TASKS.md`). **COMMITTED, not
> curtailable** — this is the **primary image DOMAIN**; the validity gate **routes the domain (artwork
> → taxa-verified-floor), it never abandons the image modality** (SPEC-image-artwork §1, §5;
> Invariant #23). Build target: `../spec/SPEC-image-artwork.md`. Inherits the **execution protocol,
> models, review tiers, and Invariants kit** from `TASKS.md` (esp. Invariant #7 books-first, #23 image
> committed, and: schema is shared — never redefine it). All tasks here are **Tier 1** when run (image
> grading correctness is load-bearing), reviewed by Opus 4.8, implemented by Sonnet 4.6, one at a time.

Targets the **relational / compositional / action** facts a flat `P180` cannot express (entity
presence is KG-redundant — do not target it). Image-content claims grade by **text NLI against the
curated label, not the raster** — the **verifier is NOT multimodal**; the **fixed-template binary
visual probe** (NOT free-form VLM-as-judge) only **constructs/verifies** the curated labels at
reference-build time.

- **IA0 — Artwork non-redundancy gate (PRE-LOCK; the lock decision is gated on this)** · deps: M-BOOKS, IA2
  *Delivers:* the formal run of the **pre-registered 3-part non-redundancy check** on the actual
  sampled artwork set, before locking the artwork domain (SPEC-image-artwork §5):
  **(a)** the targeted relational fact is **NOT entailed by any triple (incl. `P180 depicts`)**;
  **(b)** the fact is **NOT in the textual description**; **(c)** the **target VLM can read the fact
  from the image at a pre-set rate** — run with the **fixed-template binary visual probe** (NOT
  free-form judging) on the target VLM (**Qwen2.5-VL via MLX**, IA2). Stratify by genre
  (history/genre/portrait vs landscape/still-life); report per-stratum rates; target the **fine-grained
  spatial/gestural** layer (P180 eats the abstract actions).
  *On file (the preliminary result):* `decisions/2026-06-12-artwork-nonredundancy-gate.md` already
  records a PARTIAL run — ~**4,184** (live WDQS; cf. the spec's earlier ~4,180 QLever estimate) band
  paintings (P31=Q3305213 + P18 + P180, sitelinks 5–40),
  ~**85% non-redundant** on parts **(a)+(b)** (range 70–100% by partial-scoring convention; description
  redundancy near-trivially killed by the 5–40 band), **above the verified ~62% taxa floor**. The
  **REMAINING step** is the **local-VLM (c)-check** on the target VLM (Qwen2.5-VL via MLX) on this
  corpus with the POPE-style probe — that proxy in the decision file used a frontier model, not the 7B
  MLX VLM, and **over-states legibility**. **The lock decision is gated on (c).**
  **Pass ⇒ lock artwork as the reported domain. Fail ⇒ route to the verified taxa floor**
  (`TASKS-image-taxa.md`) — the image modality ships either way; the gate selects the domain, it never
  drops the axis. *SPEC:* SPEC-image-artwork §1, §5.
- **IA1 — Artwork slice `data/artwork.py`** · deps: M-BOOKS, DA1, DA2
  *Delivers:* paintings pull (`Q3305213` + `P18` + `P180`, band 5–40); image fetch + rasterize/resize;
  freeze `data/frozen/artwork/<id>/` (snapshot + images/). *SPEC:* SPEC-image-artwork §1, §3, §4.
- **IA2 — VLM client `grounding/clients/vlm.py`** · deps: M-BOOKS, GR1
  *Delivers:* `VLMClient(BaseAIClient)` (Qwen2.5-VL via MLX) for image-grounded generation + the
  visual-probe backend. No provider SDK in business logic. *SPEC:* SPEC-image-artwork §3.
- **IA3 — Visual probe + curated relational labels** · deps: IA1, IA2, GR7
  *Delivers:* fixed-template binary visual probe (label *construction/verification* only, never
  per-claim grading); curated **relational** `content_labels.json` (probe-assisted → **double-labelled
  / spot-checked**, IAA). *SPEC:* SPEC-image-artwork §3, §4.
- **IA4 — Multi-layer attribution (RQ1) in UI + grading** · deps: IA1, IA3, GR8, GR9, UI3
  *Delivers:* each claim tagged **KG / text / visual / none** (the four-layer attribution schema);
  painting shown in the entity-detail pane; per-claim visual indicator. (Region bounding-box
  highlighting descoped.) **Verifier is NOT multimodal:** image claims grade via the **existing
  text-NLI gate (GR7/GR8) against the curated label**, never the raster — the image axis only adds the
  curated labels + the IMAGE_CONTENT support source (already in the schema). *SPEC:* SPEC-image-artwork §2, §3, §4.
- **IA5 — Artwork question bank + manifest (Phase A)** · deps: IA1
  *Delivers:* relational/compositional questions (answerable only from the image) + knowledge
  questions; fixed image-content-absence + knowledge-absence manifest (fixed before inspection).
  *SPEC:* SPEC-image-artwork §1–§2.
- **IA6 — Image error accounting** · deps: IA3, GR10
  *Delivers:* visual-probe vs hand-label error; image-path classifier error; reported separately.
  *SPEC:* SPEC-image-artwork §4; SPEC-text §4.7.
- **IA7 — Artwork runs + VALIDITY GATE** · deps: IA0, IA1–IA6, GR11, EX3
  *Delivers:* run precompute over the artwork bank×manifests; **evaluate the §5 validity gate**
  (non-redundancy re-confirmed via IA0 incl. the local-VLM (c)-check; pilot shows a relational
  fabrication shift but ~none on entity presence — the specificity check; probe/label error acceptable;
  labelable in time). **Pass ⇒ report artwork** (multi-layer attribution RQ1 + image-absence RQ2).
  **Fail ⇒ route to the verified taxa floor** (`TASKS-image-taxa.md`) — the image axis ships either
  way; the gate selects the **domain**, it never drops the modality. *SPEC:* SPEC-image-artwork §5.

**Domain-routing rule (NOT a curtail rule):** the image axis is **committed** (Invariant #23). If the
artwork non-redundancy gate (IA0) or the IA7 validity gate fails, **route the DOMAIN to the verified
taxa floor** (`TASKS-image-taxa.md`), which guarantees an image axis by construction. **Only the
cross-modality CONTRAST is quarantined** as future upside — never the image modality itself.
