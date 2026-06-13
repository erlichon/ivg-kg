# TASKS — image-content axis (TAXA, VERIFIED FLOOR) · COMMITTED, sequenced post-M-BOOKS

> **The VERIFIED FLOOR of the COMMITTED image axis** — reached when the artwork DOMAIN fails its
> non-redundancy gate (`TASKS-image-artwork.md` IA0/IA7 / `../spec/SPEC-image-taxa.md` §5). **DO NOT
> OPEN before M-BOOKS.** The image axis is **committed, not optional** (Invariant #23): this taxa floor
> **guarantees an image axis by construction**, so the validity gate only ever **routes the DOMAIN
> (artwork → taxa); it never abandons the modality** — there is no "drop to books-only" path. Its
> non-redundancy gate is **already verified** (~62% non-redundant, one narrow fact type — geographic
> range). Build target: `../spec/SPEC-image-taxa.md`. Inherits the execution protocol, models, review
> tiers, and Invariants kit from `TASKS.md`. **Reuses** the VLM client, visual probe, image grading,
> and `ImageContentAbsence` already built in the artwork tasks (IA2/IA3) — this file only adds the
> taxa slice. All Tier 1 when run.

Single fact type per entity: **geographic range** (in the map, absent from triples/description).
**Verifier is NOT multimodal:** image-content claims grade by **text NLI against the curated range
label, not the raster**; the **fixed-template binary visual probe** only constructs/verifies labels.
The **four-layer attribution schema (KG / text / image / none) is used UNCHANGED** — "mostly
visual-vs-none" is the expected empirical distribution on taxa, not a schema restriction.

- **IT1 — Taxa slice `data/taxa.py`** · deps: (artwork-domain gate failed → routed here), DA1, DA2, IA2
  *Delivers:* `Q16521 + P181` enumeration, non-redundancy filter (drop `P9714`/`P183`/`P2341` so the
  range map is **non-redundant by construction**), image fetch + **SVG→PNG rasterize**, freeze
  `data/frozen/taxa/<id>/`. The **range-map fact** (where the species lives — continents, coastal vs
  inland) is the queryable spatial fact absent from triples (majority) and description (always).
  *SPEC:* SPEC-image-taxa §1, §3.
- **IT2 — Curated range labels** · deps: IT1, IA3
  *Delivers:* per-taxon hand-labelled range fact(s) (probe-assisted → double-labelled / spot-checked,
  IAA); IMAGE-modality `ContentLabel`s. Reuses the IA3 probe. *SPEC:* SPEC-image-taxa §3.
- **IT3 — Taxa question bank + manifest (Phase A)** · deps: IT1
  *Delivers:* range/distribution questions (answerable only from the map) + knowledge questions;
  fixed image-content-absence + knowledge-absence manifest. *SPEC:* SPEC-image-taxa §2.
- **IT4 — Taxa runs + reporting-quality check** · deps: IT1–IT3, IA4, IA6, GR11, EX3
  *Delivers:* run precompute over the taxa bank×manifests; the **range fact extraction** + visual probe
  feed the curated labels (IT2). Non-redundancy is **already verified** (§1) — the floor's guarantee —
  so these are **reporting-quality checks on the already-committed image axis**, NOT a switch that
  drops the modality: **(a)** measurable range fabrication shift in pilot, **(b)** VLM reads the map
  reliably enough (curated-label construction error acceptable), **(c)** labelable in time. Reuses the
  IA4 four-layer attribution UI + IA6 error accounting. *SPEC:* SPEC-image-taxa §4.

## Dependency graph (adjacency) — taxa floor (entered only when the artwork gate routes here)
```
(artwork gate fail) ─► IT1 ◄─ DA1, DA2, IA2
IT1 ─► IT2 ◄─ IA3
IT1 ─► IT3
IT1, IT2, IT3, IA4, IA6, GR11, EX3 ─► IT4 (taxa runs + reporting-quality checks)
```

## Parallel execution waves (earliest-start; all post-M-BOOKS, after the gate routes here)
- **Wave T0:** IT1.  *(needs DA1, DA2, IA2 from the books/artwork build.)*
- **Wave T1:** IT2 ‖ IT3.  *(IT2 also needs IA3.)*
- **Wave T2:** IT4 (taxa runs + reporting-quality checks).  *(also needs IA4, IA6, GR11, EX3.)*

**No drop path.** Taxa is the **verified FLOOR that guarantees the committed image axis** — there is no
"books-only" fallback below it (Invariant #23). The IT4 checks are quality gates on what is reported,
not on whether the image modality ships. Only the cross-modality contrast is quarantined as upside.
