# TASKS — image-content axis (ARTWORK, primary) · gated, post-M-BOOKS

> **DO NOT OPEN until M-BOOKS** (books validated end-to-end; see `TASKS.md`). Curtailable. Build
> target: `../spec/SPEC-image-artwork.md`. Inherits the **execution protocol, models, review tiers,
> and Invariants kit** from `TASKS.md` (esp. Invariant #7 books-first, and: schema is shared — never
> redefine it). All tasks here are **Tier 1** when run (image grading correctness is load-bearing),
> reviewed by Opus 4.8, implemented by Sonnet 4.6, one at a time.

Targets the **relational / compositional / action** facts a flat `P180` cannot express (entity
presence is KG-redundant — do not target it). Image-content claims grade by **text NLI against the
curated label, not the raster**; the visual probe only **constructs/verifies** labels.

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
  *Delivers:* each claim tagged KG / text / visual / none; painting shown in the entity-detail pane;
  per-claim visual indicator. (Region bounding-box highlighting descoped.) Image claims grade via the
  existing text NLI gate vs the curated label. *SPEC:* SPEC-image-artwork §2, §3, §4.
- **IA5 — Artwork question bank + manifest (Phase A)** · deps: IA1
  *Delivers:* relational/compositional questions (answerable only from the image) + knowledge
  questions; fixed image-content-absence + knowledge-absence manifest (fixed before inspection).
  *SPEC:* SPEC-image-artwork §1–§2.
- **IA6 — Image error accounting** · deps: IA3, GR10
  *Delivers:* visual-probe vs hand-label error; image-path classifier error; reported separately.
  *SPEC:* SPEC-image-artwork §4; SPEC-text §4.7.
- **IA7 — Artwork runs + VALIDITY GATE** · deps: IA1–IA6, GR11, EX3
  *Delivers:* run precompute over the artwork bank×manifests; **evaluate the §5 validity gate**
  (non-redundancy re-confirmed; pilot shows a relational fabrication shift but ~none on entity
  presence; probe/label error acceptable; labelable in time). **Pass ⇒ report** (multi-layer
  attribution RQ1 + image-absence RQ2). **Fail ⇒ fall back to `TASKS-image-taxa.md` if time remains,
  else drop to books-only** (no core loss). *SPEC:* SPEC-image-artwork §5.

**Curtail rule:** under schedule pressure cut from IA7 backward; the books spine + reports already
stand. If dropped, record artwork multimodality as future work in the report.
