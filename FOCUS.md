# ivg-kg — FOCUS

> The one page that ends the scatter. What we are building, why it's defensible, and what we are NOT
> doing. Last consolidated 2026-06-12 from: the focus-decision panel, the trust-views panel, the
> novelty fact-check, and the course-grounding of lectures 5-AI4MMA / 6-MMA4AI (all in `decisions/`).
> If a proposal isn't on this page, it's out of scope until this page changes.

## The one contribution

**An MMA4AI instrument**: an interactive visual-analytics tool that makes an LLM's knowledge-graph
grounding **inspectable, trustworthy, and repairable**. This is a Multimedia Analytics course project —
the *instrument* is the contribution, not an ML result. The course names our problem class outright
(lecture 6: "MMA4AI", *probing not prompting*, "one main action: analyze"); we should say it outright.

Course-grounded problem statement (the framing to use):
> ivg-kg grounds each generated claim against a frozen Wikidata slice, classifies it
> *retrieved / Supportable / fabricated*, and pairs every verdict with a faithful support-path
> attribution, so an analyst can understand and **calibrate trust** in the model's grounding before
> acting — and repair the knowledge gaps that cause fabrication.

## C1 / C2 / C3 — build in this order (decreasing robustness)

- **C1 — the instrument (robust; build first; earns the grade even if the sweep finds nothing).**
  Grounding + a **deterministic, calibrated verifier** + the Overview->Inspection->Repair loop, wrapped
  in the honesty layer below. Course mapping: Worring's build recipe (purpose+audience -> architecture
  -> define *scores* -> visualize -> coordinate views); the verifier is an L5 **Analysis VA-Agent**
  whose contract is a trustworthy rationale (= the Provenance Card).
- **C2 — the absence finding (the science; medium risk; needs the sweep).** Controlled
  absence-induced hallucination via the offline sweep, reported as a **distribution shift** across
  {full, content-withheld, knowledge-withheld}. The **modality** of the withheld evidence (textual
  content / structural knowledge / image content) is the **manipulated variable** (RQ2) — so the
  multimodal axis is **instrumented and analyzed**, not decoration. The **promised claim is
  within-modality** (each modality's absence induces fabrication within its slice); the **cross-modality
  CONTRAST** ("modality M matters more than M'") is **Phase-B / future upside, quarantined and not
  promised**. Course mapping: ablation-as-attribution; instance-vs-aggregate duality (single-run vs
  multi-run).
- **C3 — the agreement quadrant (upside; highest risk).** Observational
  support-frequency vs causal absence-shift at KG-triple grain -> load-bearing / redundant-scaffold /
  hidden-dependency / inert. Course mapping: GNNLens R3 "analyze the cause of errors". **Novelty split:**
  the **instrument + the taxonomy-as-a-lens** (present in C1's UI by construction) is the **delivered
  novelty**; the **populated quadrant** is the **cuttable empirical finding**. A delivered novelty
  survives even if C3 is only a pilot: **repair_leverage is a standalone delivered novelty** (vs CogMG),
  shipping with C1/RQ3 independent of the C3 sweep.

Focus rule: **C3 must not drive the schedule.** Build C1 solidly, get a C2 pilot, treat the populated
quadrant as bonus — but the delivered novelty (instrument + taxonomy-as-a-lens + repair_leverage) ships
regardless.

## Generator vs verifier (the methodological spine)

- **Generator** = sampled local LLM (stochastic; produces a CoT draft). **Verifier** = DETERMINISTIC
  (NLI gate DeBERTa-live / MiniCheck-7B-offline + symbolic multi-hop path search; a **different model
  family**; **not an LLM, no chain-of-thought**; always grades vs the FULL reference).
- The verifier's "reasoning" is a **faithful deterministic proof chain** (the Provenance Card), not a
  narration. We show the generator's CoT *beside* it, labelled "stated, not necessarily faithful" — the
  fallible-vs-faithful contrast IS the lesson, and it visualizes system-under-test vs instrument.
- The non-steering, no-CoT verifier is **not a limitation** — it is licensed by L6 ("guidance can
  easily lead to bias"). Lean into it.

## The honesty layer (C1's trust + interpretability + causality, one spine)

- **Interpretability = "why this verdict?"** (faithful, per claim): the Provenance Card (proof chain)
  + the **why-fabricated slot-diff** (VALUE-mismatch vs MISSING-fact -> repairable?) + verbalized
  support path + spurious-path glyph. The slot-diff is highest value: it connects interpretation to
  action.
- **Causality = "does this evidence matter, and how sure are we?"** kept honest by the **epistemic
  glyph grammar** — three glyphs that never get confused: open circle = observational
  (support-frequency), filled triangle+interval = interventional aggregate (sweep), outlined triangle
  "n=1" = single-sample demo. This disciplined encoding (not a new causal method) is our causality
  contribution; it prevents the tool's worst failure mode (reading correlation as causation).
- **Trust = the instrument shows its own error first.** Two-tier, **data-agnostic by design**:
  - *Instrument-level (any KG, always shown):* the NLI gate's published benchmark accuracy + the
    per-claim entailment **margin to tau**. No labels needed.
  - *Deployment-level (shown when labels exist):* error calibrated on a curated gold QA set for the
    loaded slice. For our books demo: computed and shown. For a user's BYO-KG: degrade to the
    instrument-level number + an explicit "not calibrated to your KG" caveat + a "label N claims to
    calibrate" affordance.
  Plus the **"fabricated != false" overlay** (out-of-slice claims hatched: unsupported here != untrue).
- **Curated gold QA set does double duty:** it calibrates the verifier (Trust/C1) AND anchors the RQ2
  sweep (C2). "How big a sweep?" -> a good curated QA set, not "the whole dataset".

## Interface verdict (from the course-grounding; hue stays locked to STATUS)

- **KEEP (course-validated — stop second-guessing):** three-panel Answer/Subgraph/Analytics (MULTI-CASE
  triad); hue=STATUS + selection on outline/badge (Vega-Lite grammar); single-run vs multi-run
  (instance/aggregate); support-path highlight on claim-select (VisQA drill-down); REMOVE/ADD
  perturbation (ablation + counterfactual); multi-run mean+/-SE + small-N caveat.
- **CHANGE (ranked):** (1) **surface the Trust strip + "fabricated!=false" overlay on-stage** — THE
  single highest-leverage change; the headline trust contribution is currently invisible in every
  screenshot. (2) persist a single-run **before/after status delta** after REMOVE/ADD (show the
  ablation's effect, don't re-render in place). (3) make the support-frequency list the **selector**
  into inspection. (4) encode **repair_leverage on a glyph/size channel**, not prose.
- **ADD (only clearly-implied, S/M):** the **epistemic glyph** (observed / intervened / n=1) as a shape
  channel — subsumes (4).
- **CUT / DEFER-WITH-DEFENSE:** do NOT build a t-SNE/UMAP **projection overview** — claim embeddings
  don't separate by grounding status (it's a relational, not semantic, property), so it would be
  decorative. Defend its absence in one report sentence; the support-frequency map serves the overview
  role. Cut nothing else.

## Vocabulary to adopt (course-grounded)

MMA4AI; *probing not prompting*; "scores/metrics" for STATUS / support-frequency / repair_leverage /
verifier-error; "ablation-based attribution" for the absence sweep (mechanism stays "remove-from-
context"); VA-Agent (Generate/Analyze agent + Analysis VA-Agent); Perez-Messina guidance ladder
(Orienting + Directing, deliberately NOT Prescriptive).

## Report-framing fixes (documentation, not code)

1. Add a numbered **requirements skeleton** (R1/R2/R3 mapped to Overview->Inspection->Repair) — every
   L6 system is requirements-driven; RQs are not interface requirements.
2. Defend the **non-steering verifier** with L6 "guidance -> bias".
3. Pre-empt "why no learning loop": state the bound — *human-AI teaming without RL strategy optimization.*
4. **Novelty honesty (from the fact-check):** cite ContextCite (causal context attribution) and
   "Attention is not Explanation" as closest prior art; claim novelty as the **composition + KG-triple
   granularity + agreement taxonomy**, NOT as inventing causal attribution or the cited!=needed
   phenomenon. Fix the Agrawal cite (four-quadrant, no user study). **Multimedia side (same honesty):**
   claim the instrument **composition** (multi-layer attribution + image-absence ablation arm +
   repair), NOT the primitives — cite *Graphing the Truth* [9] (text-only), VISA [2], VDGD [22] and
   M3ID (image-ablation mechanic = prior art), MCiteBench [23] (multimodal citation exists).
5. **Verb/term scoping:** "calibrate trust" and "legible to a non-expert" are **design intent pending
   the user study**, not established results; instrument-tier trust is an **uncalibrated reliability
   prior** (per-claim margin = confidence proxy, not calibration) — reserve "calibrated" for the
   deployment tier (gold-QA-set numbers). The three statuses are **evidential** ("retrieved" = directly
   supported, not a process claim).

## What we are NOT doing (the cut list)

Per-item ablation at scale (cap to ~5-8 questions); the live per-question condition toggle; a projection
overview; making the agreement quadrant the headline; any ML-novelty framing; resurrecting dropped
metrics (absence_leverage/fabrication_induction scalars, per-claim stability, slot/variant cross-run
alignment, "verifier runs N times").

## Multimodal scope (RESOLVED — committed; contrast quarantined)

The image axis is **committed, not optional**: text/books core **first**, then the image modality as a
**gated second phase** (sequencing, not a maybe). Artwork (relational/compositional facts) is primary;
**taxa range-maps are the de-risked fallback that guarantees an image axis** even if the artwork
non-redundancy gate fails — the validity gate chooses *which* image domain, never *whether* to do
image. The framing is instrument-first (MMA4AI), but multimodality is the **manipulated variable** for
the absence-by-modality finding (C2/RQ2), so it is **instrumented and analyzed**, not decoration. The
title keeps "Multimodal Knowledge Graphs." The statement drops "curtailable / books-only with no core
loss" hedging — image is a commitment, sequenced after text.

**Multimedia novelty = the guaranteed instrument COMPOSITION, not the primitives.** What we claim is the
coupled tool: **multi-layer attribution (KG-triple / text / image / none) + the image-content-absence
ablation arm + KG-repair**, as one interactive VA instrument. We do **not** claim the primitives:
*Graphing the Truth* [9] is the nearest VA competitor but **text-only**; VISA [2] = visual source
attribution for documents; the **image-withholding ablation mechanic is prior art** (VDGD [22]; M3ID);
multimodal citation exists (MCiteBench [23]). The composition is novel; the mechanic is not.

**Anchored on the taxa floor; artwork = securable upside.** The **guaranteed floor** is taxa
range-maps (verified ~62% non-redundant, one fact type) plus multi-layer attribution. **Artwork
relational facts are securable upside**, gated on a **pre-registered non-redundancy check that has not
yet been run** — this gate is the **"work harder" task** that converts the thin floor into the robust
version.

**Cross-modality CONTRAST quarantined.** The promised, robust claim is **within-modality** (each
modality's absence induces fabrication within its slice). The **cross-modality contrast** ("modality M
matters more than M'") is **Phase-B / future upside, explicitly not promised** — it is the first thing
cut. Multimodality stays **committed**; only the *contrast* is quarantined. Claim the **composition,
not the primitives**.

## Pointers (detail lives here)

`decisions/2026-06-11-focus-decision-verdict.md` · `decisions/2026-06-12-trust-views-verdict.md` ·
`decisions/2026-06-12-novelty-factcheck.md` · `decisions/2026-06-12-course-grounding.md` ·
`course/INSPIRATION-2024-25.md`
