# SPEC-image-artwork — Image-content axis (PRIMARY) · `ivg-kg`

> **Gated, post-M-BOOKS, curtailable.** Do not start this until the books spine is validated
> (M-BOOKS, `SPEC-text.md` §1). This is the **primary** image axis; if its validity gate fails and
> time remains, fall back to `SPEC-image-taxa.md`; else drop to the books-only spine (no core loss).
> It **reuses the shared schema** in `SPEC-text.md` §4.2 (never redefines it) and carries the
> **shared image infrastructure** (VLM client, visual probe, image grading, image error accounting)
> that the taxa fallback also reuses.

## 1. Why artworks, and the non-redundancy refinement (verified)
Domain: **paintings (`P31 = Q3305213`)** with an image (`P18`) and `depicts` (`P180`), sampled in
the same **5–40 sitelink band**. Gate probe (QLever): **4,180** band paintings have image + depicts.

- Descriptions are generic stubs ("1890 painting by …") → no content redundancy there.
- `P180` *depicts* is a **flat bag of entities** and is often rich (e.g. "violin, girl, sitting,
  bench, bridge, Notre-Dame"), so **entity-presence is frequently KG-redundant**.
- **The non-redundant image signal is RELATIONAL / compositional / action** — facts `P180` cannot
  express: *"the violin is held on her lap, not played", "she is sitting on a ledge", "Notre-Dame is
  behind-right", "the bridge is behind-left", composition/spatial layout*. Confirmed by inspecting a
  band example (Bouguereau, "The Bohemian", Q1000128).

**Design rule:** the image-content axis targets **relational/compositional/action facts**, NOT entity
presence (which the triples often supply). Questions, ablation, and ground-truth labels must target
the relational layer. Entity-presence questions correctly show *no* image-ablation signal because the
triples answer them.

## 2. What this axis adds (two RQs, richer than taxa)
- **RQ1 — multi-layer attribution (the VISA analogue).** Each claim is attributed to **KG-triple /
  textual / visual / none** (or a combination). Example: "depicts a violin" → KG (P180) + visual;
  "she is playing the violin" → visual-only (relation absent from P180); "Saint George is a martyr" →
  textual/KG, not visual; "the dragon represents evil" → interpretive → unsupported/weak.
- **RQ2 — image-content-absence.** Withhold the painting image from the VLM's generation context
  (keep triples + description); measure the fabrication shift on **relational** claims. Entity claims
  are unaffected (triples supply them) — a built-in specificity check.

## 3. Shared image infrastructure (reused by the taxa fallback)
- **`grounding/clients/vlm.py` — `VLMClient(BaseAIClient)`:** Qwen2.5-VL-7B via **MLX / vllm-mlx**
  (Apache-2.0 weights / MIT) on Apple Silicon (MPS, 48 GB). Used for image-grounded **generation**
  (answer from image+text context) and as the visual-probe backend. No provider SDK in business logic.
- **Visual probe (`entailment.py` extension):** a **fixed-template binary probe** (POPE-style) over
  the raster — used **only to construct/verify the curated image-fact labels** at reference-build
  time, *not* as a per-claim grader and **never** as a free-form VLM-as-judge (rejected:
  POPE/MFC-Bench object hallucination).
- **Image grading:** image-content claims are graded by the **text NLI gate (MiniCheck) against the
  curated image-fact label rendered as text** — *not* against the raster (statement §5.1). This
  reuses `GR7`/`GR8` unchanged; the image axis only adds the curated labels + the IMAGE_CONTENT
  support source (already in the schema).
- **SVG/raster handling:** fetch `P18` via Commons `Special:FilePath`; rasterize/resize to a
  VLM-friendly size; store under `data/frozen/artwork/<id>/images/`.

## 4. Components (build only post-M-BOOKS)
- **`data/artwork.py`** — paintings pull (`Q3305213` + `P18` + `P180`, band 5–40); image fetch +
  rasterize; freeze `data/frozen/artwork/<id>/` (snapshot.json + images/ + content_labels.json).
- **Curated relational labels (`content_labels.json`)** — per painting, a small set of
  **relational/compositional facts** (visual-probe-assisted, then **double-labelled / spot-checked by
  hand**, IAA reported). These are the IMAGE-modality `ContentLabel`s the grader uses.
- **`ImageContentAbsence`** (already in the core perturbation seam) — withholds `image_path` from the
  generation context.
- **Multi-layer attribution view (UI)** — the answer/subgraph panels tag each claim with its
  support layer(s) (KG / text / visual / none) and show the painting in the entity-detail pane;
  per-claim "visual-present?" indicator. *Region bounding-box highlighting is descoped* (VISA-style
  localization needs fine-tuning) — start with image-display + per-claim visual indicator.

## 5. Validity gate (evaluated before reporting any image result)
Report the artwork image axis **only if** all hold (else fall back to taxa, or drop):
1. **Non-redundancy:** the targeted relational facts are absent from `P180`/description (per §1) — re-
   confirm on the actual sampled set.
2. **Pilot signal:** image-content-absence produces a **measurable fabrication shift** on relational
   questions in a small pilot (and ~none on entity-presence questions — the specificity check).
3. **Visual-probe / label error:** the curated-label construction error (visual probe vs hand labels)
   is low enough to interpret results; image-path classifier error is reported separately (§4.7).
4. **Labelability:** relational ground-truth can be produced for the sample in the available time.

If 1–4 hold → report; the multi-layer attribution strengthens RQ1 and the image-absence axis extends
RQ2. If any fail → `SPEC-image-taxa.md` (verified, simpler) if time remains, else books-only.

## 6. Tasks
See `../tasks/TASKS-image-artwork.md` (gated, post-M-BOOKS). All inherit the Invariants kit and the
Opus/Sonnet review loop from `../tasks/TASKS.md`.

## 7. Reuse notes
VISA [2] — the multi-layer / region-attribution framing (region localization itself descoped).
Qwen2.5-VL via MLX — generation + visual probe (Apache-2.0/MIT). Free-form VLM-as-judge rejected.
The text grounding (extract/link/classify/MiniCheck) and the schema are reused unchanged from
`SPEC-text.md`.
