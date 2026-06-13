# Inspiration from MMA 2024-25 projects (multix.io/mma-2024-2025)

Distilled 2026-06-12 from reading two papers in full: InfoCIR (best-project award,
published PacificVis 2026) and the Graph Query System (closest topical neighbor).
All items below are FINAL-report / demo ammunition -- none required for the
intermediate report.

## What made InfoCIR win (and what to copy)

InfoCIR ran NO evaluation studies. It won on venue-quality writing and design rigor.

1. **Explicit Design Goals section (DG1-DG4: Assess / Compare / Enhance / Understand)**
   -- every interface and algorithmic choice traced back to a named goal. We have the
   material (inspect / diagnose / repair / trust); name it as design goals in the
   final report.
2. **Evaluation roadmap with named methods and numbers, none executed**: expert
   heuristic audit -> agent-based simulation computing van Wijk's K/C cost-benefit
   ratio (acceptance threshold > 1.5) -> 12-student within-subjects A/B with SUS +
   Wilcoxon signed-rank -> North insight-density case study (success threshold 0.25
   insights/min) -> ethics paragraph. Lesson: evaluation literacy WITH SPECIFICS
   (thresholds, n, statistical test) scores like evaluation. Concretize our
   Zahalka + North plan the same way.
3. **They measured their own instrument**: appendix table of UMAP quality metrics,
   initial vs final config (trustworthiness 91->97% etc.). Our Trust pillar /
   verifier-error calibration is the same move -- present as a before/after table.
4. **Formal task definition with equations** (their 3.1) + a **named usage scenario**
   ("red apple" walkthrough: diagnose -> refine -> validate). We have both
   ingredients (SPEC 4.8 formulas; the Chopin scenario) -- surface a compact
   formalization and write Chopin as a usage-scenario subsection.
5. Pike framing worth adopting verbatim-ish: "we treat each user action as a
   micro-scale hypothesis test."
6. Polish signals: 6-panel teaser with A-F labels + self-contained caption;
   architecture figure laid over the Worring zones; modularity claim; metadata
   logging for reproducibility; a SPECIFIC limitations list.
7. The bar for "shoot high": two 2024-25 projects were published (InfoCIR ->
   PacificVis 2026; HIVE -> ICCV 2025 workshop).

## Graph Query System ("Understanding (Sub)graphs through LLM Commentary")

G-Retriever + Dash/Cytoscape + local Ollama Llama-3.2-3B answering NL questions over
retrieved subgraphs, with query-phrase significance scores.

- **Positioning gift: it takes the LLM answer entirely on faith.** No verification,
  no grounding, no fabrication detection. One related-work sentence for our final
  report: a prior same-course project produced LLM-over-KG querying WITHOUT
  verification; ivg-kg closes that loop (deterministic verifier, three-way grounding).
- **Their importance score is query-side, ours is knowledge-side**: they perturb
  phrases in the question (leave-one-out -> Jaccard shift of the retrieved subgraph);
  we perturb evidence in the KG/context and measure grounding outcomes. Adjacent
  enough to cite, different enough to be safely ours.
- **They ran a tiny but real user study**: n=4, 100 trials, binary one-shot
  satisfaction metric, +14% with visual feedback. Same-scale study is within our
  reach for the final report (e.g., one-shot repair-success or insight count, with
  vs without the bank overview).
- **Stack precedent**: both projects ship our exact stack (Dash + Cytoscape + local
  quantized LLM via Ollama) -- feasibility precedent for the live path.

## Concrete final-report TODOs harvested

- [ ] Design-Goals subsection (DG-style), traced to interface choices.
- [ ] Concretized evaluation roadmap (van Wijk K/C via simulation; SUS + Wilcoxon
      A/B sketch; North insight density with numeric threshold; ethics line).
- [ ] Verifier-calibration before/after table (Trust pillar as instrument
      self-measurement).
- [ ] Compact formal task definition + Chopin usage-scenario subsection.
- [ ] Related-work sentence positioning vs the 2024-25 Graph Query System.
- [ ] Consider a tiny executed user study (n~4, binary task-success metric).
