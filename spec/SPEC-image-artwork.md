# SPEC-image-artwork — Image-content axis (PRIMARY) · `ivg-kg`

> **COMMITTED, sequenced post-M-BOOKS (NOT curtailable).** The image axis is a **commitment**, not an
> option (statement §2, §10; FOCUS "Multimodal scope"); it is *sequenced* after the books spine
> (M-BOOKS, `SPEC-text.md` §1), never contingent on it. Do not start this until M-BOOKS is validated.
> This is the **primary** image domain (artwork). The **validity gate routes the image DOMAIN
> (artwork → taxa), it never abandons the modality**: if the artwork non-redundancy gate fails, fall
> back to the **verified taxa floor** (`SPEC-image-taxa.md`), which **guarantees an image axis** by
> construction. **Only the cross-modality CONTRAST is quarantined** as future upside (statement §3
> Phase B) — the image axis itself is not.
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

**Floor vs upside (statement §2, §10; FOCUS "Anchored on the taxa floor").** Artwork relational facts
are **securable UPSIDE**, not the floor. The **verified FLOOR** is the taxa range-map axis
(`SPEC-image-taxa.md`: ~62% non-redundant, one narrow fact type — geographic range). Artwork is gated
on a **PRE-REGISTERED NON-REDUNDANCY CHECK that has NOT yet been formally run** (§5): the targeted
fact must be **(i) NOT in the triples** (incl. `P180 depicts`), **(ii) NOT in the description**, **AND
(iii) readable by the VLM at a pre-set rate**. This gate **routes artwork → taxa** when it fails — it
**never abandons the image modality**; the modality is committed, the domain is what the gate selects.
The gate is the **"work harder" task** that converts the thin taxa floor into the robust artwork
version.

## 2. What this axis adds (two RQs, richer than taxa)
- **RQ1 — multi-layer attribution (the image-side VA element; the VISA analogue for KG+image).** Each
  claim is attributed to **KG-triple / textual / visual / none** (or a combination). Example: "depicts
  a violin" → KG (P180) + visual; "she is playing the violin" → visual-only (relation absent from
  P180); "Saint George is a martyr" → textual/KG, not visual; "the dragon represents evil" →
  interpretive → unsupported/weak. This per-claim multi-layer attribution is the image-side analogue
  of the text-side Provenance Card (`SPEC-text.md` §4.9b).
- **RQ2 — image-content-absence.** Withhold the painting image from the VLM's generation context
  (keep triples + description); measure the fabrication shift on **relational** claims. Entity claims
  are unaffected (triples supply them) — a built-in specificity check.

**Multimedia novelty = the COMPOSITION, not the primitives (statement §2, §10; FOCUS "Multimedia
novelty").** The contribution is the **coupled instrument** — per-claim KG grounding + multi-layer
attribution (KG-triple / text / image / none) + image-content-absence ablation + KG-repair as one
interactive VA tool. We do **NOT** claim the primitives: the **image-withholding ablation MECHANIC is
prior art** (VDGD [22]; M3ID) — do not claim it; visual source attribution for documents is **VISA
[2]**; multimodal citation is **MCiteBench [23]**; the nearest VA competitor is *Graphing the Truth*
[9] (text-only). The composition is novel; the mechanic is not. Cite these for positioning.

**Verifier scope — NOT multimodal (statement §5.1, §5.5; make explicit).** The verifier never grades
the raster. Image-content claims are graded by the **text-NLI gate against the CURATED LABEL** (the
relational fact rendered as text), exactly as text claims are. The **VLM is the GENERATOR**; the
**fixed-template visual probe constructs/verifies the curated labels** at reference-build time (§3).
So the only multimodal component is the generator + label-construction probe — the grading instrument
stays the same text-NLI gate as the books core.

## 3. Shared image infrastructure (reused by the taxa fallback)
- **`grounding/clients/vlm.py` — `VLMClient(BaseAIClient)`:** Qwen2.5-VL-7B via **MLX / vllm-mlx**
  (Apache-2.0 weights / MIT) on Apple Silicon (MPS, 48 GB). Used for image-grounded **generation**
  (answer from image+text context) and as the visual-probe backend. No provider SDK in business logic.
- **Visual probe (`entailment.py` extension):** a **fixed-template binary probe** (object-presence
  style, e.g. POPE) over the raster — used **only to construct/verify the curated image-fact labels**
  at reference-build time, *not* as a per-claim grader. We **retain** the fixed-template binary probe
  and **reject FREE-FORM VLM-as-judge** (its hallucination susceptibility, per the POPE / MFC-Bench
  object-hallucination findings); rejecting free-form judging does **not** reject the object-presence
  probe itself.
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

## 5. Validity gate — routes the DOMAIN (artwork → taxa), never abandons the modality
This gate chooses **which image domain** is reported; the **image axis is committed** regardless
(statement §2, §10; FOCUS). It is the **PRE-REGISTERED non-redundancy check that has NOT yet been
formally run** (§1). Report the **artwork** domain **only if** all hold; otherwise **route to the
verified taxa floor** (`SPEC-image-taxa.md`), which guarantees an image axis by construction:
1. **Non-redundancy (pre-registered):** the targeted relational fact is **(i) NOT in the triples
   (incl. `P180 depicts`)**, **(ii) NOT in the description**, **AND (iii) VLM-readable at a pre-set
   rate** — formally run and confirmed on the actual sampled set before locking.
2. **Pilot signal:** image-content-absence produces a **measurable fabrication shift** on relational
   questions in a small pilot (and ~none on entity-presence questions — the specificity check).
3. **Visual-probe / label error:** the curated-label construction error (visual probe vs hand labels)
   is low enough to interpret results; image-path classifier error is reported separately (§4.7).
4. **Labelability:** relational ground-truth can be produced for the sample in the available time.

If 1–4 hold → report **artwork**; the multi-layer attribution strengthens RQ1 and the image-absence
axis extends RQ2. If any fail → **route to `SPEC-image-taxa.md`** (the verified, de-risked floor) — the
image modality is delivered either way; the gate selects the domain, it does not drop the axis.

## 6. Tasks
See `../tasks/TASKS-image-artwork.md` (gated, post-M-BOOKS). All inherit the Invariants kit and the
Opus/Sonnet review loop from `../tasks/TASKS.md`.

## 7. Reuse notes
VISA [2] — the multi-layer / region-attribution framing (region localization itself descoped).
Qwen2.5-VL via MLX — generation + visual probe (Apache-2.0/MIT). Free-form VLM-as-judge rejected.
The text grounding (extract/link/classify/MiniCheck) and the schema are reused unchanged from
`SPEC-text.md`.
**Novelty positioning (cite, do not claim the primitives):** the **image-withholding ablation
mechanic is prior art** — VDGD [22] and M3ID — we adopt it and do **not** claim it; MCiteBench [23]
shows multimodal citation already exists; *Graphing the Truth* [9] is the nearest VA competitor but
**text-only**. The delivered novelty is the **composition** (per-claim KG grounding + multi-layer
attribution + image-content-absence ablation + KG-repair as one instrument), not any single primitive.
