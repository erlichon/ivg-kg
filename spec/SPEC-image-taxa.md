# SPEC-image-taxa — Image-content axis (FALLBACK) · `ivg-kg`

> **Gated, post-M-BOOKS, curtailable — and only reached if the artwork axis fails its validity gate
> (`SPEC-image-artwork.md` §5) and time remains.** This is the **de-risked fallback**: its
> non-redundancy gate is *already verified*. It **reuses the shared schema** (`SPEC-text.md` §4.2)
> and the **shared image infrastructure** (VLM client, visual probe, image grading, image error
> accounting) defined in `SPEC-image-artwork.md` §3 — this file only adds the taxa-specific slice.

## 1. Why taxa is the fallback (verified gate)
Domain: **taxa (`P31 = Q16521`) with a range-map image (`P181`)**, sampled in the **5–40 sitelink
band** and **filtered to taxa whose range is not already a structured triple** (no `P9714`/`P183`/
`P2341`), so the map is **non-redundant by construction**. Gate probe (QLever, run in this project):
**15,484** band taxa with a range map; **~60% carry no structured range property at all**; taxa
descriptions are generic stubs that never carry range. So a range map encodes a **queryable spatial
fact** (where the species lives — continents, coastal vs inland) absent from triples (majority) and
description (always).

**Trade vs artwork:** taxa is **verified** and simpler, but thinner — essentially **one fact type
(geographic range) per entity**, and a range map is a less engaging demo than a painting. It is the
insurance, not the first choice.

## 2. What this axis measures
- **RQ2 — image-content-absence:** withhold the range-map image from the VLM context (keep triples +
  description); measure the fabrication shift on **range/distribution** questions.
- **RQ1:** range claims attribute to the IMAGE layer (the fact isn't in triples/description), so the
  multi-layer attribution is mostly visual-vs-none here (less rich than artwork's KG/text/visual mix).

## 3. Components (build only if this fallback is reached)
- **`data/taxa.py`** — `Q16521 + P181` enumeration, non-redundancy filter (drop `P9714`/`P183`/
  `P2341`), image fetch + **SVG→PNG rasterize**, freeze `data/frozen/taxa/<id>/`.
- **Curated range labels (`content_labels.json`)** — per taxon, the hand-labelled range fact(s)
  (visual-probe-assisted, double-labelled / spot-checked, IAA reported). IMAGE-modality `ContentLabel`s.
- Reuses `VLMClient`, the visual probe, image grading (text NLI vs curated label), and the
  `ImageContentAbsence` perturbation — all from `SPEC-image-artwork.md` §3 / the core seam.
- UI: range-map image in the entity-detail pane; per-claim visual indicator. (Range-region
  highlighting is descoped, as for artwork.)

## 4. Validity gate
Non-redundancy is **already verified** (§1). The remaining checks before reporting: (a) image-content-
absence produces a measurable fabrication shift on range questions in a pilot; (b) the VLM can read a
range map reliably enough (curated-label construction error acceptable); (c) labelable in time. If
these hold → report; else → books-only spine (no core loss).

## 5. Tasks
See `../tasks/TASKS-image-taxa.md` (gated, post-M-BOOKS, fallback). Inherits the Invariants kit and
the review loop from `../tasks/TASKS.md`.
