# Panel verdict: contribution focus decision

> Workflow: ivg-kg-focus-decision (17 agents: 5 evaluators + wildcard scout +
> 10 adversarial refuters + synthesis chair) | run 2026-06-11.
> STATUS NOTE: verdict = per-fact absence-behavior map + agreement quadrants as the
> future core focus (post-intermediate-report). NOT yet encoded into the docs; open
> decision 1 (4th both-withheld condition amends the locked RQ2 design) needs team
> sign-off before EX1/EX2 changes.

# PANEL VERDICT — Synthesis Chair

## 1. Ranking

| # | Candidate | Verdict line |
|---|-----------|--------------|
| 1 | **risk-map** (8) | Highest user-insight (9) and synergy (9.5) on the slate; both refutations serious-but-survived with concrete mitigations; it is the artifact that cures "the tool doesn't tell the user anything." |
| 2 | **agreement-scatter** (8) | Best novelty (8 — observational-vs-causal agreement at KG-item granularity is unclaimed); survives refutation only with capped sweep + uncertainty encoding; consumes the *same per-item data* as the risk-map, so it is the risk-map's quantitative face, not a rival. |
| 3 | **Wildcard P1 — claim-fate tracking** | Competitive: it is the missing *operationalization* of the risk-map's third category (omission/abstention), pure post-processing on sweep logs, and upgrades RQ2 from rates to mechanism. Adopted as machinery, not as a fourth view. |
| 4 | **repair-case-studies** (7) | Best demo narrative and the rubric's verbatim "core of VA" feedback loop, but reviewer showed leverage>1 is partly a deterministic regrade artifact and existence of cascades is unverified — co-star, never the lead. |
| 5 | **bank-overview** (6) | Must-build glue (feasibility 9, synergy 9) but novelty 4: "we made our results figure clickable" cannot headline. One day, navigation index only. |
| 6 | **sweep-findings** (5) | Reviewer attack is **fatal as headline**: the lead finding is the spec's own manipulation check, and the aggregate effect size is set by bank authorship. Demoted to evidence engine. |
| — | Wildcard P2 (fabrication fingerprint) | Cut. New NLI-equivalence clustering machinery in a zero-slack window for a secondary axis. |

## 2. The Recommended Core

**The per-fact absence-behavior map: an interactive overlay that shows, for every probed fact in a grounded KG, whether this LLM recovers it parametrically, silently confabulates, or omits when the evidence is withheld — validated against the cheap observational support-frequency map via the agreement quadrants.**

This fuses ranks 1–3 into one focus, and the fusion is not a compromise — it is the same dataset viewed twice. One capped per-item ablation sweep produces per-fact absence-behavior labels; painted on the subgraph it is the **risk-map**; crossed with support-frequency it is the **agreement scatter** with its 2x2 taxonomy (load-bearing / redundant scaffold / hidden dependency / inert); the labels themselves come from **claim-fate alignment** (entity+predicate key), which is what makes "omits" a real measured category instead of a heuristic.

**Why it wins on novelty:** risk-map alone scores 6.5 because KGLens and Mallen et al. occupy "what does the LLM know per fact." Importing the agreement question fixes this: *no found work measures the agreement between observational support-frequency and causal absence-shift, at KG-triple granularity, with a deterministic verifier, interactively, coupled to a repair loop* (evaluation: novelty 8; Agrawal 2512.00663 has no ablation; ContextCite/Wallat establish cited≠relied-upon but never the agreement question or the KG/VA form). The "redundant scaffold" quadrant — cited constantly, yet withholding changes nothing — is the canonical North-2006 unexpected insight.

**Why it wins on user-insight:** the insight is interaction-borne, not figure-borne. The analyst pans the subgraph, sees where the model will silently confabulate, clicks a risk fact into the N runs behind it, checks it against the support-frequency overlay, and *acts* (repair) — the full Overview→Inspection→Repair cycle, and the exact "interactively explore a complex AI architecture" lens the grader wrote. Risk-map's 9 on user-insight is the highest on the panel.

**Mandatory mitigations (both refuters flagged "serious"; all must be adopted):**
1. **Add a fourth sweep condition: both-withheld** — without it "parametric recovery" is confounded by cross-modality leakage (reviewer). Cheap: one more manifest dimension in the already-offline EX4.
2. **Probed-facts-only scope** — only facts the question bank exercises get labels; unprobed facts render explicitly grey with a "not probed" legend (TA). No graph-wide claims.
3. **Uncertainty-first encoding** — Wilson/SE intervals on both axes, an explicit "indeterminate" class, quadrant membership claimed only when shift > 2SE; boundary points rendered unstable (both refuters).
4. **Honest framing** — "absence behavior under modality withholding," not per-fact causal ablation; cite KGLens, Mallen, ContextCite, Wallat and claim only the interactive-VA + agreement + repair coupling. Demote "can cheap maps substitute for ablation?" to "where do observational and causal importance disagree in this testbed?"
5. **Capped per-item sweep** — ~5–8 questions x ~8 items x N=10 (~400–600 runs, one overnight on the 48GB box), added to the EX4 manifest *now*; modality-level agreement figure committed by ~Jun 18 as guaranteed fallback (TA).
6. **Channel discipline** — hue is contractually locked to claim status (TASKS invariant #12); the overlay uses border/glyph/pattern or a toggled view mode.

## 3. The Supporting Stack (one story: *absence has a geography; the tool maps it and repairs it*)

- **sweep-findings → the evidence engine.** Modality contrast reported as manipulation check + per-fact outcome profiles, stratified by question type, bank-composition caveat explicit. Pilot (~10q) aggregate locked by ~Jun 18 as the guaranteed report figure. Never the headline.
- **Wildcard P1 claim-fate alignment → the labeling machinery.** Entity+predicate alignment pass over sweep logs produces the recover/fabricate/omit trichotomy and alignment-coverage stats. The alluvial/Sankey view is a stretch goal only; the data ships regardless.
- **bank-overview → the entry view.** One day, px.imshow over EX4 aggregates, SE-aware cells, click lands on the **multi-run** view (not one arbitrary run). Completes the Overview state the rubric's mandated state-machine figure needs. One sentence in the paper, no contribution bullet.
- **repair-case-studies → the closing act.** 2–3 pre-screened, frozen cascade scenarios targeted *via the risk-map* (risk facts = predicted high-leverage repairs — the map's live validation). Leverage **decomposed into regrade-only vs behavioral flips** and grounded in the leverage distribution over the sweep; cascades replicated over ≥3 re-runs (both refuters' mitigations).
- **Tool evaluation (separate from the sweep):** Zahalka-style simulated analytic-quality (with/without-overview task counts) + North insight-based on the case studies — so the LLM-sweep is never mistaken for the mandated tool evaluation.

## 4. The Cut List

- **Sweep-findings as headline** — fatal: leads with its own manipulation check.
- **Wildcard P2 (fabrication fingerprint)** — new value-normalization/NLI-clustering machinery; zero slack.
- **Graph-wide risk coverage / per-fact causal language** — unidentified by the design; grey is honest.
- **The general "cheap maps substitute for ablation" claim** — ~10 questions, one domain cannot support it.
- **Alluvial claim-fate *view*** — data yes, fourth analytic view only if days 10–12 are clean ("do NOT overwhelm").
- **Custom bank-overview interactions** (linked brushing, condition drill-downs) — effort belongs to the pipeline and the 50%-weighted report.
- **Hunting natural cascades at large** — pre-screen hub-gap scenarios from sweep output instead.

## 5. Contribution Bullets (findings-first)

- **C1 (Finding):** Per-fact absence-behavior maps of a local LLM over a verified-non-redundant KG slice: under controlled withholding (content / knowledge / both), facts partition into parametrically-recovered, silently-confabulated, and omitted — and the modality of absence shifts this three-way claim-fate split, not just the fabrication rate.
- **C2 (Finding):** Observational reliance (support-frequency) and causal importance (absence-induced status shift) systematically disagree at KG-item granularity: a quadrant taxonomy (load-bearing / redundant scaffold / hidden dependency / inert) with uncertainty-aware membership — the first agreement analysis between the two attribution views in a KG-grounded, verifier-gated setting.
- **C3 (Instrument):** An open, offline-reproducible VA instrument that couples the map to action: deterministic entailment + symbolic path verification, Overview→Inspection→Repair, and decomposed repair-leverage (regrade vs behavioral flips) — capabilities absent from KGR, CogMG, GraphEval, KGLens, and Agrawal 2512.00663.

## 6. 12-Day Sketch (4 people; pipeline ~day 7 = Jun 18; demo Jun 23; report Jun 25)

| Days | A (pipeline) | B (experiments) | C (UI/Dash) | D (report/eval) |
|------|--------------|------------------|-------------|-----------------|
| 1–3 (Jun 11–13) | Grounding pipeline (extraction→linking→NLI→paths) | **Update EX1/EX2 now**: 4th condition, per-item manifest entries, hub-gap cascade pre-check | Risk overlay + agreement scatter + bank-overview **against mock sweep JSON** | Report skeleton; related-work positioning (KGLens, Mallen, ContextCite, Wallat, Agrawal); state-machine figure |
| 4–7 (Jun 14–18) | Pipeline integration + GR10 calibration | Sweep harness; §6 controls | Claim-fate alignment pass (post-processing); wire stores/click-through | Evaluation design (Zahalka sim + North insight); fallback modality-level figure spec |
| 7–8 (Jun 18–19) | Pipeline ships | **Pilot sweep (~10q, 4 cond.) overnight → lock guaranteed headline figure** | Rebind views to pilot data | Pilot figures into report |
| 8–10 (Jun 19–21) | Bug-fix reserve | Full sweep + capped per-item sweep (overnight batches); mine cascades, freeze 2–3 scenarios | Uncertainty encoding, grey/not-probed legend, demo polish | Run tool evaluation; results section |
| 10–12 (Jun 21–23) | Offline-safe precompute check | Replicate cascade leverage over re-runs; decompose regrade/behavioral | Frozen-scenario demo path; **demo Jun 23** | Demo script |
| 12–14 (Jun 23–25) | — | Final agreement analysis | Figure exports | **Report Jun 25** |

**Single biggest schedule risk:** everything insight-bearing is downstream of the day-7 pipeline, and the per-item sweep is a sweep-on-top-of-a-sweep landing in the final 4–5 days. **Mitigation (three-layer, already named by the TA refuters):** (a) all views built against mock data days 1–7 and rendering any partial runs directory; (b) pilot-first policy — the ~10-question pilot aggregate locked by Jun 18 is the guaranteed headline, full + per-item sweeps only upgrade it; (c) the modality-level agreement figure (free from EX4) is the committed fallback, so the worst case is a weakened figure, never a hole.

## 7. Open Decisions

1. **Approve the spec/statement change**: adding the both-withheld condition and per-item manifest entries amends the locked 3-condition RQ2 design — requires explicit team sign-off on project_statement.md/SPEC-text.md edits before B touches EX1/EX2 (this gates day 1).
2. **Per-item sweep budget**: which 5–8 questions, how many items each, N=10 vs N=20 — fixes the overnight-batch size and the scatter's statistical floor.
3. **Abstention operationalization**: claim-fate (entity, predicate) alignment as primary, with a pre-committed collapse to two-way (recover vs fabricate) if alignment coverage is poor — pick the coverage threshold now.
4. **Risk-overlay visual channel**: border vs glyph vs toggled view mode (hue is locked to claim status) — affects C's day-1 work.
5. **Alluvial view ship/no-ship gate**: decide at the Jun 19 pilot checkpoint, not before.

## Appendix: dossier summary (scores + refutation outcomes)

```json
[
  {
    "id": "sweep-findings",
    "overall": 5,
    "attacks": [
      "reviewer:fatal:killed",
      "ta:serious:survives"
    ]
  },
  {
    "id": "bank-overview",
    "overall": 6,
    "attacks": [
      "reviewer:serious:survives",
      "ta:serious:survives"
    ]
  },
  {
    "id": "risk-map",
    "overall": 8,
    "attacks": [
      "reviewer:serious:survives",
      "ta:serious:survives"
    ]
  },
  {
    "id": "agreement-scatter",
    "overall": 8,
    "attacks": [
      "reviewer:serious:survives",
      "ta:serious:survives"
    ]
  },
  {
    "id": "repair-case-studies",
    "overall": 7,
    "attacks": [
      "reviewer:serious:survives",
      "ta:serious:survives"
    ]
  }
]
```

## Appendix: wildcard scout proposals (verbatim)

PROPOSAL 1 — Claim Fate Tracking ("where do claims GO when evidence disappears?")

Pitch: The locked design reports condition-level shifts in the claim-status distribution, but distributions hide the mechanism. Align individual claims across conditions (by linked entity + predicate, infrastructure the pipeline already produces) and visualize each claim's *fate* when its evidence is withheld: survives grounded (parametric recall), flips to fabricated (absence-induced hallucination), or silently *disappears* (omission/abstention). Omission is an uncounted third outcome the entire current design is blind to — a model that drops a claim under absence is behaving safely, and absence-induced hallucination is properly defined as fabrication-given-non-omission. Render as an alluvial/Sankey flow (full → content-withheld → knowledge-withheld) in a fourth analytics view, with click-through to single-run inspection.

Why it beats the 5 candidates: It upgrades RQ2 from "rates changed" to a mechanism-level finding (hallucinate vs. omit vs. recall parametrically — does modality of absence shift this three-way split?), which is exactly the "insight" the rubric grades. Candidates 1–4 all aggregate; none follows an identifiable claim across conditions. The abstention–hallucination tradeoff is hot in 2025–26 NLP (AbstentionBench, TruthRL) but no one has it claim-aligned, KG-grounded, and visual — the search found no such combination, and Agrawal (2512.00663) has no cross-condition tracking.

Main risk: Claim alignment across stochastic runs is fuzzy (paraphrases, claim granularity drift); mitigate by aligning on the canonical (entity, predicate) key the linker already emits and reporting alignment coverage honestly.

Build plan: (1) Add a claim-alignment pass over the existing sweep logs (entity+predicate key, value-slot comparison) — pure post-processing, no pipeline change. (2) Compute per-claim fate matrices per condition pair and the fabricate/omit/survive split per modality. (3) Add one Dash alluvial view wired to the existing dcc.Store and claim-click highlighting.

PROPOSAL 2 — Fabrication Fingerprint (consistent lie vs. confabulation)

Pitch: Within multi-run mode, cluster the *values* of fabricated claims across the N runs: does the model assert the SAME wrong fact every run (a stable parametric belief — possibly true-in-world but absent from the KG) or a different one each time (true confabulation)? One number per fabricated claim slot (value entropy), overlaid on the existing support-frequency map; connects to semantic-entropy literature but is novel under controlled absence ablation and KG grounding.

Why it beats the candidates: Adds a scientific axis (belief vs. guess) with near-zero new compute — reuses sweep outputs. Risk: value normalization for clustering ("1844" vs "in 1844"); mitigate with the NLI gate pairwise. Build: extract fabricated-claim values from sweep logs; cluster per claim slot via NLI equivalence; add entropy badge to the multi-run claim list.

Recommendation: Proposal 1 — it is rubric-aligned, fills a genuine blind spot (omission), and is pure post-processing on data the sweep already produces.

Sources: [AbstentionBench](https://arxiv.org/pdf/2506.09038), [TruthRL](https://arxiv.org/pdf/2509.25760), [Anchored Confabulation](https://arxiv.org/html/2604.25931v1), [Self-Consistency Hallucination Detection](https://www.emergentmind.com/topics/self-consistency-based-hallucination-detection), [Graphing the Truth (Agrawal)](https://arxiv.org/pdf/2512.00663)
