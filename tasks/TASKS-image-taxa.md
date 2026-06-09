# TASKS — image-content axis (TAXA, fallback) · gated, post-M-BOOKS

> **DO NOT OPEN unless** the artwork axis failed its validity gate (`TASKS-image-artwork.md` IA7 /
> `../spec/SPEC-image-artwork.md` §5) **and time remains.** De-risked fallback: its non-redundancy
> gate is already verified. Build target: `../spec/SPEC-image-taxa.md`. Inherits the execution
> protocol, models, review tiers, and Invariants kit from `TASKS.md`. **Reuses** the VLM client,
> visual probe, image grading, and `ImageContentAbsence` already built in the artwork tasks (IA2/IA3)
> — this file only adds the taxa slice. All Tier 1 when run.

Single fact type per entity: **geographic range** (in the map, absent from triples/description).
Image-content claims grade by text NLI against the curated range label, not the raster.

- **IT1 — Taxa slice `data/taxa.py`** · deps: (artwork fallback triggered), DA1, DA2, IA2
  *Delivers:* `Q16521 + P181` enumeration, non-redundancy filter (drop `P9714`/`P183`/`P2341`),
  image fetch + **SVG→PNG rasterize**, freeze `data/frozen/taxa/<id>/`. *SPEC:* SPEC-image-taxa §1, §3.
- **IT2 — Curated range labels** · deps: IT1, IA3
  *Delivers:* per-taxon hand-labelled range fact(s) (probe-assisted → double-labelled / spot-checked,
  IAA); IMAGE-modality `ContentLabel`s. Reuses the IA3 probe. *SPEC:* SPEC-image-taxa §3.
- **IT3 — Taxa question bank + manifest (Phase A)** · deps: IT1
  *Delivers:* range/distribution questions (answerable only from the map) + knowledge questions;
  fixed image-content-absence + knowledge-absence manifest. *SPEC:* SPEC-image-taxa §2.
- **IT4 — Taxa runs + validity check** · deps: IT1–IT3, IA4, IA6, GR11, EX3
  *Delivers:* run precompute over the taxa bank×manifests; check (a) measurable range fabrication
  shift in pilot, (b) VLM reads the map reliably enough, (c) labelable in time. **Pass ⇒ report** the
  taxa image axis; **fail ⇒ books-only** (no core loss). Reuses the IA4 attribution UI + IA6 error
  accounting. *SPEC:* SPEC-image-taxa §4.

**Curtail rule:** cut from IT4 backward; books spine + reports stand regardless.
