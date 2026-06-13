# SPEC-image-taxa — Image-content axis (VERIFIED FLOOR / fallback domain) · `ivg-kg`

> **Sequenced post-M-BOOKS; the VERIFIED FLOOR of the COMMITTED image axis** — reached when the
> artwork domain fails its non-redundancy gate (`SPEC-image-artwork.md` §5). The image axis is a
> **commitment, not optional** (statement §2, §10; FOCUS): this taxa floor **guarantees an image axis
> by construction**, so the validity gate only ever **routes the DOMAIN (artwork → taxa); it never
> abandons the modality**. Its non-redundancy gate is **already verified** (~62% non-redundant range-
> map facts, one narrow fact type — geographic range). It **reuses the shared schema** (`SPEC-text.md`
> §4.2) and the **shared image infrastructure** (VLM client, visual probe, image grading, image error
> accounting) defined in `SPEC-image-artwork.md` §3 — this file only adds the taxa-specific slice.

## 1. Why taxa is the fallback (verified gate)
Domain: **taxa (`P31 = Q16521`) with a range-map image (`P181`)**, sampled in the **5–40 sitelink
band** and **filtered to taxa whose range is not already a structured triple** (no `P9714`/`P183`/
`P2341`), so the map is **non-redundant by construction**. Gate probe (QLever, run in this project):
**15,484** band taxa with a range map; **~60% carry no structured range property at all**; taxa
descriptions are generic stubs that never carry range. So a range map encodes a **queryable spatial
fact** (where the species lives — continents, coastal vs inland) absent from triples (majority) and
description (always).

**Trade vs artwork:** taxa is **verified** and simpler, but thinner — essentially **one narrow fact
type (geographic range) per entity** (~62% non-redundant), and a range map is a less engaging demo
than a painting. It is the **guaranteed FLOOR** — the de-risked insurance that delivers the committed
image modality; **artwork is the securable UPSIDE** layered on top when its pre-registered
non-redundancy gate passes (`SPEC-image-artwork.md` §5). Floor, not first choice — never a drop of the
modality.

## 2. What this axis measures
- **RQ2 — image-content-absence:** withhold the range-map image from the VLM context (keep triples +
  description); measure the fabrication shift on **range/distribution** questions.
- **RQ1 — multi-layer attribution (the image-side VA element).** Range claims attribute to the IMAGE
  layer (the fact isn't in triples/description), so the multi-layer attribution (KG-triple / text /
  image / none) is mostly visual-vs-none here (less rich than artwork's KG/text/visual mix). It is the
  same image-side analogue of the text-side Provenance Card (`SPEC-text.md` §4.9b). The full four-layer
  attribution schema (KG-triple / textual / image / none, via `SupportSource`; `SPEC-text.md` §4.2) is
  used **UNCHANGED**; "mostly visual-vs-none" is the **expected empirical distribution** on taxa, not a
  schema restriction.

**Verifier scope — NOT multimodal (statement §5.1, §5.5).** As on artwork, the verifier never grades
the raster: range claims are graded by the **text-NLI gate against the CURATED range LABEL** (rendered
as text). The **VLM is the GENERATOR**; the **fixed-template visual probe constructs/verifies** the
curated range labels at reference-build time (§3). **Multimedia novelty = the composition, not the
primitives** — the image-withholding ablation mechanic is prior art (VDGD [22], M3ID); see
`SPEC-image-artwork.md` §2/§7.

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
Non-redundancy is **already verified** (§1) — this is the FLOOR's guarantee, which is why the image
modality is delivered regardless of the artwork gate. The remaining checks before reporting: (a)
image-content-absence produces a measurable fabrication shift on range questions in a pilot; (b) the
VLM can read a range map reliably enough (curated-label construction error acceptable); (c) labelable
in time. These are reporting-quality checks on the **already-committed** image axis, not a switch that
drops the modality.

## 5. Tasks
See `../tasks/TASKS-image-taxa.md` (gated, post-M-BOOKS, fallback). Inherits the Invariants kit and
the review loop from `../tasks/TASKS.md`.
