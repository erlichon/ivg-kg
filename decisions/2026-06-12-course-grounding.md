# Course-grounding: lectures 5-AI4MMA & 6-MMA4AI applied to ivg-kg

> Workflow: ivg-kg-course-grounding (5 agents: 2 digesters + problem-regrounding + interface-
> re-evaluation [read the actual demo screenshots] + coordinator) | run 2026-06-12.
> STATUS: final-report / demo material. Headline: the course VALIDATES the architecture; the only
> real gaps are VISIBILITY (surface the Trust strip) and REPORT FRAMING (requirements skeleton,
> guidance-bias defense) -- not redesign. Respects the locked C1/C2/C3 focus + hue=status invariant.

## Coordinator synthesis

I have all the context needed from the digests and the two appliers' findings. Let me produce the decisive synthesis.

# ivg-kg — Coordinator Synthesis (Lectures 5 & 6)

## 1. COURSE-GROUNDED PROBLEM STATEMENT

> **ivg-kg is an MMA4AI instrument** [L6, Slides 3-6]: a visual-analytics tool whose **one main action is *analyze***, **probing** (not prompting) an LLM's knowledge-graph grounding behaviour. It grounds each generated claim against a frozen Wikidata books slice, classifies it *retrieved / Supportable / fabricated*, and pairs every verdict with a faithful **support-path attribution** so a decision-maker can **understand and calibrate trust** before acting [L6, Slide 33; L5, Slide 26].

**C1 — the instrument.** Built by Worring's recipe [L6, Slide 27]: purpose+audience → architecture elements → **define scores** → visualize → coordinate views. Our STATUS / support-frequency / repair_leverage / gold-QA verifier-error are those **scores** [L6, Slides 27,34]. The deterministic verifier is an **Analysis VA Agent** whose mandated trustworthy rationale = the **Provenance Card** [L5, Slide 31], itself an **Explanation** in the Montavon sense (interpretable-domain features that drove the verdict) [L6, Slide 17]. Overview→Inspection→Repair = **GNNLens R1→R2→R3** (overview → error patterns → cause) [L6, Slide 74] and an **ATWL artifact→transform chain** ascending to epistemic outcomes [L5, Slides 17-19].

**C2 — absence sweep / distribution shift.** This is **ablation-as-evidence** (leave-out, measure effect) [L6, Slides 49-50]. N=20 multi-run = **aggregate-over-all-instances**, single-run = **instance-based** [L6, Slides 24,45,50], orchestrated as the **Coordinator's async fan-out/aggregate** [L5, Slide 34], reported as a **comparison view** [L6, Slides 25,37].

**C3 — observational-vs-causal agreement quadrant.** GNNLens **R3 = "analyze the CAUSE of errors"** [L6, Slide 74]; the support-frequency vs intervention-shift agreement is that cause layer.

## 2. TERMINOLOGY / FRAMING CHANGES

- **ADOPT "MMA4AI" + "probing, not prompting"** in §1-2 [L6, Slides 3-6]. The course names our problem class; say it outright.
- **ADOPT "scores/metrics"** language for STATUS / support-frequency / repair_leverage / verifier-error [L6, Slide 27]; §6 currently lists encodings without naming the score-definition step they render.
- **ADOPT "ablation-based attribution"** for the absence sweep [L6, Slides 49-50]; keep "remove-from-context" as the *mechanism*, relabel the *frame*.
- **ADOPT the Vega-Lite encoding tuple** [L5, Slides 9-10] to harden hue=STATUS from style into grammar (STATUS = nominal field on the color channel; everything else on glyph/size/border/position).
- **ADOPT the Perez-Messina guidance ladder** [L5, Slide 27]: status-hues + Trust strip = **Orienting**; why-fabricated slot-diff + repair_leverage = **Directing**; we deliberately stop short of **Prescriptive** — consistent with [L6, Slide 6] "guidance can easily lead to bias."
- **TIGHTEN the VA-Agent framing in §6** [L5, Slide 31]: Generate/Analyze agent (LLM draft+CoT) + **Analysis VA Agent** (deterministic verifier, rationale = Provenance Card). Drop the loose "Expert Module" wording.

**Genuine MISMATCHES to fix in the report (not the UI):**
1. **Guidance posture under-defended.** [L6, Slide 6]'s "guidance could easily lead to bias" is the *strongest* license for the non-steering, no-CoT verifier and is currently unused. **Add it.**
2. **RQs ≠ requirements.** Every L6 system is requirements-driven (R1/R2/R3; G/T) [L6, Slides 45-47,58,74] tied to a named audience. §3 has research questions, not interface requirements for "an analyst calibrating trust in an LLM's grounding." **Add a numbered requirements skeleton** mapped to Overview→Inspection→Repair.
3. **"Why no learning loop" un-pre-empted.** L5 [Slides 35-36] ends on RLHF. State the bound explicitly: *human-AI teaming without RL strategy optimization.*

These three are documentation work, not code — cheap and high-value before the demo.

## 3. INTERFACE VERDICT

**KEEP (well-grounded — stop second-guessing):**
1. Three-panel Answer/Subgraph/Analytics — MULTI-CASE A/B/C triad [L5, Slide 42].
2. Hue=STATUS, selection on outline+badge — Vega-Lite tuple, status on color, selection on a separate detail channel [L5, Slides 9-10].
3. Single-run vs Multi-run toggle — instance vs aggregate duality [L6, Slides 24,45,50].
4. Support-path highlight on claim select — VisQA confident-answer→evidence drill-down [L6, Slides 67-70].
5. REMOVE/ADD perturbation — ablation + counterfactual explanation [L6, Slides 49-50; L5, Slide 26].
6. Multi-run mean±SE + small-N caveat — comparison + uncertainty-in-context [L5, Slide 26].

**CHANGE (ranked by leverage):**
1. **Surface the Trust strip / verifier-error + "fabricated≠false" overlay on-stage.** It is the single strongest trust citation [L5, Slide 26; L6, Slide 33] and is currently invisible in the UI. This is the honesty layer's whole point — it must be visible during the demo. **(S)**
2. **Persist a single-run before/after status delta after REMOVE/ADD.** The ablation's *effect* is the evidence and must be shown side-by-side [L6, Slides 49-50], not silently re-rendered in place. **(S/M)**
3. **Make the multi-run support-frequency list the actual selector** that loads a run/item into inspection (half-done already) — projection-that-is-a-selector [L6, Slides 23,48,60,77]. **(S/M)**
4. **Bind repair_leverage to a size/glyph channel** instead of prose "+1 (c3)" — it is a defined score, encode it [L6, Slide 27]. **(S)**

**ADD (only the clearly-implied, S/M):**
- **Epistemic glyph (observed / intervened / n=1) as a shape channel** on claims/nodes, distinguishing single-run (intervened, n=1) from multi-run (observed) evidence [L6, Slides 28,35-36,82]. Already in your design language; render it. **(S)** This subsumes change #4 — do them together.

**CUT:** Nothing. No lecture implies removing anything. Do **not** build a t-SNE/UMAP projection overview — see §5; it is not warranted here and is M/L effort days before a demo.

## 3b. SINGLE HIGHEST-LEVERAGE CHANGE

**Surface the Trust strip (verifier-error on the gold QA set) + the "fabricated≠false" overlay as a persistent, on-stage element.** It is S effort, needs no new backend, and is cited by *both* lectures as the core trust mechanism ([L5, Slide 26] uncertainty-in-context; [L6, Slide 33] trust-as-audience-need). It is the literal point of the honesty layer and it is currently absent from every screenshot — a demo that claims a trust/honesty contribution must show it. This beats the run-strip projection the interface-applier nominated: that change addresses a *grammar-completeness* gap, whereas the Trust strip addresses a *contribution-is-invisible* gap. **Resolved in favour of the Trust strip.**

(I am overriding the interface applier's pick. Their run-strip is legitimate but optional polish; the missing Trust strip is a hole in the demo's headline claim.)

## 4. WHAT THE COURSE CONFIRMS (stop second-guessing)

- The **two-component split** (sampled LLM = Generate/Analyze agent; deterministic verifier = Analysis VA Agent) is exactly the L5 VA-Agent architecture [Slide 31]. Validated.
- The **deterministic, no-CoT, non-steering verifier** is not a limitation — it is *directly licensed* by [L6, Slide 6] ("guidance can easily lead to bias"). Validated; lean into it.
- **Hue=STATUS invariant** is principled grammar, not a style preference [L5, Slides 9-10; L6, glyph pattern Slides 35-36,82]. Validated; defend it confidently.
- **Single-run + multi-run, the repair loop, and the perturbation demos** all map cleanly onto course-canonical patterns (instance/aggregate, ablation, comparison, VisQA drill-down). Validated. The architecture is sound — remaining work is *surfacing* what exists, not redesigning.
- **Three-panel layout and Provenance Card** sit squarely in MULTI-CASE + Montavon-explanation territory. Validated.

The design is course-aligned. The gaps are about **visibility and report framing**, not architecture. Protect focus.

## 5. OPEN QUESTIONS (only plan-changing ones)

1. **Is the gold-QA verifier-error number actually computed and available to render?** The Trust strip (3b) is only S effort *if* that score already exists. If it must be computed from scratch before Jun 23, it drops to M and may need a stubbed/placeholder value for the demo with a clear "illustrative" label. **This is the one answer that gates the top recommendation.**
2. **Does the single-run path already retain the pre-perturbation status vector?** If yes, the before/after delta (CHANGE #2) is pure presentation; if the regeneration overwrites state, it needs a small state-retention fix. Confirm before committing it to the Jun-23 scope.
3. **Projection overview — explicitly deferred?** I am recommending *against* building it now. Confirm the team agrees to log it as post-demo future work so it stops resurfacing as a "gap."

Relevant files for the recommended changes: `/Users/itay/Documents/repos/MSc/MMA/ivg-kg/app/panels/subgraph.py`, `/Users/itay/Documents/repos/MSc/MMA/ivg-kg/src/ivg_kg/mock/fixtures.py` (`_OUTCOME_COUNTS`, `aggregate_runset`), `/Users/itay/Documents/repos/MSc/MMA/ivg-kg/project_statement.md` (§3 requirements skeleton, §6 VA-Agent tightening), and the Trust-strip render site (location to confirm under `app/panels/`).

---

## Appendix A -- Problem re-grounding (applier)

I have the current framing (sections 1-6 read) and the lecture digests. I have everything needed to produce the re-grounded problem definition.

# Re-grounded PROBLEM DEFINITION for ivg-kg (course vocabulary)

## (a) The one sentence the course would use

> **ivg-kg is an MMA4AI instrument**: a visual-analytics tool that **probes** an LLM's knowledge-graph grounding behaviour — its **one main action is *analyze*** — surfacing per-claim status, support-path attribution, and ablation-based evidence so a decision-maker can *understand and calibrate trust* in the model before acting.

This directly instantiates **MMA4AI (vs AI4MMA)** [L6, Slides 3-5] and **"prompting → probing the architecture, one main action: analyze"** [L6, Slide 6].

## (b) Contribution → named course concepts

- **C1 (the instrument).** Build recipe [L6, Slide 27]: purpose+audience → architecture elements → **define scores** → visualize scores → balance coordinated-views vs one-complex-view. Our **STATUS (retrieved/Supportable/fabricated), support-frequency, repair_leverage, gold-QA verifier-error** are the **scores/metrics** in Worring's sense [L6, Slides 27,34]. The verifier is an **Analysis VA Agent** whose mandated **trustworthy rationale** = the Provenance Card [L5, Slide 31]; the Provenance Card is an **Explanation** (interpretable-domain features that drove the decision) per **Montavon Interpretation/Explanation** [L6, Slide 17]. Overview→Inspection→Repair = **GNNLens R1→R2→R3** (overview → identify error patterns → analyze cause) [L6, Slide 74] and an **ATWL artifact→transform chain** ascending to epistemic outcomes [L5, Slides 17-19]. Three-panel layout parallels **MULTI-CASE** A/B/C [L5, Slides 40-43].
- **C2 (absence sweep / distribution shift).** This is **ablation/pruning as evidence** — leave-evidence-out, measure the effect [L6, Slides 49-50]. The N=20 multi-run is **aggregate-over-all-instances** vs single-run **instance-based** [L6, Slides 24,45,50], orchestrated as the **Coordinator's async fan-out/aggregate** [L5, Slide 34]; reported as a **comparison view** [L6, Slides 25,37].
- **C3 (observational-vs-causal agreement quadrant).** GNNLens **R3 = "analyze the CAUSE of errors"** [L6, Slide 74]; the support-frequency vs distribution-shift agreement is the "cause" layer.

## (c) Terminology to ADOPT / framing to CHANGE

- **ADOPT "MMA4AI" and "probing, not prompting"** explicitly in §1-2 — the course names our problem class; say it.
- **ADOPT "scores/metrics"** language: present STATUS / support-frequency / repair_leverage / verifier-error as the *defined scores* [L6, Slide 27], which §6 encodings then render. Currently §6 lists encodings without naming them as the recipe's score-definition step.
- **ADOPT "ablation"** for the absence sweep (§5.6/§6) — currently "withhold-from-context"; keep that as the mechanism but label it ablation-based attribution [L6, Slides 49-50].
- **ADOPT the Vega-Lite encoding tuple** [L5, Slides 9-10] to harden the hue=STATUS invariant from a style choice into a grammar argument (status = nominal field on the color channel; glyph/size/border/position carry other scores).
- **ADOPT the Perez-Messina guidance ladder** [L5, Slide 27]: name status-hues + Trust strip as **Orienting**, why-fabricated slot-diff + repair_leverage as **Directing**, and state ivg-kg deliberately stops short of **Prescriptive** — which aligns with [L6, Slide 6] "limited guidance, bias risk."
- **CHANGE the VA-model citation framing (§6).** §6 currently calls the pipeline "Analysis agent" and KG "Expert Module" loosely; tighten to the **VA Agent contract** [L5, Slide 31]: Generate/Analyze agent (LLM draft+CoT) + **Analysis VA Agent** (deterministic verifier, rationale = Provenance Card).

## (d) MISMATCH where our framing diverges from the course

1. **Guidance posture is under-defended.** §6 lists a Trust pillar but never invokes [L6, Slide 6]'s explicit warning that **guidance "could easily lead to bias"** when analyzing a foundation model. This is the *strongest* course license for our non-steering deterministic verifier and no-CoT-narration rule — currently unused. **Add it.**
2. **No explicit target-audience + numbered requirements.** Every VA-for-AI system in L6 [Slides 45-47,58,74] is requirements-driven (R1/R2/R3; G/T). Our §3 has RQs (research questions), not interface **requirements** tied to an audience ("an analyst calibrating trust in an LLM's factual grounding"). The rubric rewards the requirements skeleton; RQs ≠ requirements.
3. **Overview pillar may be too thin for the course's expected grammar.** L6's primary navigation surface is repeatedly a **2D projection of an instance population, used as the selector for drill-down** [L6, Slides 23,48,60,77]. Our multi-run Overview is a per-item frequency map, not a projection. **Possible gap** — consider a projection-style overview of the 20 runs / KG-items in score-space (position+glyph, **not** recoloring — respects the hue invariant). Refine, do not rescope.
4. **No "why no learning loop" pre-empt.** L5 [Slides 35-36] concludes with RLHF as the optimization path; our repair loop gathers human feedback but deliberately does **not** close an RL loop. State this bound explicitly ("human-AI teaming without RL strategy optimization") to pre-empt the reviewer question.

Source file read: `/Users/itay/Documents/repos/MSc/MMA/ivg-kg/project_statement.md` (§1-6).

---

## Appendix B -- Interface re-evaluation (applier, read the screenshots)

I have enough to critique the actual interface. The 04-node-zoom screenshot also reveals a per-claim status panel with bars and a "support-frequency" inspection state I can ground against.

# IVG-KG interface re-evaluation (grounded in lectures 5 & 6)

## (a) WELL-GROUNDED — keep

- **Three-panel Answer / Subgraph / Analytics layout** — matches MULTI-CASE's A (ontological result) + B (textual view) + C (KG interface) panel triad (AI4MMA, slide 42). Keep; cite as established MMA interface practice.
- **Hue = STATUS (3-grade), selection by outline+badge** — textbook Vega-Lite encoding-tuple discipline: STATUS is a nominal field on the color channel, selection rides a *separate* detail/border channel (AI4MMA, slides 9-10). Strong; the invariant is principled, not stylistic.
- **Single-run vs Multi-run toggle** — exactly the course's instance-based vs aggregate-over-all-instances duality (MMA4AI, slides 24/45/50). Keep and name it.
- **Support-path highlight on claim select (hover/click → evidence)** — the VisQA "confident answer → click through to the evidence" interaction (MMA4AI, slides 67-70) and the structural analogue of attention visualization (AI4MMA, slide 26). Keep.
- **REMOVE / ADD perturbation strip** — these are ablation-as-evidence (leave-one-out, add-back; MMA4AI, slides 49-50) AND counterfactual explanations in the course's exact sense (AI4MMA, slide 26). Keep; relabel as "probing/ablation," not "prompt editing" (MMA4AI, slide 6: probing > prompting).
- **Multi-run mean±SE + small-N caveat** — comparison view + uncertainty-in-context (AI4MMA, slide 26; comparison tradition MMA4AI slides 25/37/63). Keep.

## (b) WEAK / UNGROUNDED — change

- **Multi-run overview is a bar chart + ranked list only.** The course's dominant navigation surface for an *aggregate of instances* is a **2D projection that is itself the selector for drill-down** (MMA4AI, slides 23/48/60/77). The bars don't let you see *which runs* cluster (all-grounded vs partial-fabrication). Change: make the support-frequency list/graph the selector (already half-done) and add run-level structure (below).
- **No explicit COMPARISON of baseline vs perturbed in single-run.** After REMOVE/ADD you re-run in place; the before/after delta — the actual *evidence* of the ablation — isn't shown side-by-side (MMA4AI slides 49-50 demand showing the effect). Change: persist a before/after status delta.
- **Trust strip / verifier-error not visible in any screenshot.** "Uncertainty and performance shown IN THE CONTEXT of the output" is the single strongest trust citation (AI4MMA, slide 26; trust-as-audience-need MMA4AI slide 33) and it's absent on-stage. Change: surface it.
- **repair_leverage is text-only ("+1 (c3)").** It's a defined *score* (MMA4AI, slide 27) but rendered as prose, not encoded on a channel. Change: bind it to a size/glyph channel on the repaired claim/node.

## (c) MISSING — what the course implies for model-behaviour/trust

- **An ablation before/after delta view** (the explanation of a probe) — slides 49-50.
- **The Trust strip + "fabricated ≠ false" overlay made visible** — slide 26/33; this is the honesty layer's whole point and isn't on screen.
- **Epistemic glyph grammar (observed / intervened / n=1)** rendered as a *shape* channel on claims/nodes, distinguishing single-run (intervened, n=1) from multi-run (observed) evidence — glyph-encoded per-unit scores (MMA4AI slides 28/35-36/77/82).
- **Numbered requirements skeleton** (GNNLens R1 overview → R2 error patterns → R3 cause) mapping onto Overview→Inspection→Repair — for the report, not the UI (MMA4AI slide 74).

## (d) SINGLE HIGHEST-VALUE CHANGE (S effort, Jun-23)

**Add a run-strip / small-multiples projection to the multi-run Overview**: one glyph per run (N=20), positioned by grounded-fraction, hue = dominant status, **clickable to load that run into single-run inspection** — turning the overview into the course-canonical *projection-that-is-a-selector* for drill-down (MMA4AI, slides 23/48/60/77). It closes the biggest gap (aggregate→instance navigation), respects hue=STATUS (uses position+glyph, not recolor), needs no new backend (the per-run outcomes already exist in `_OUTCOME_COUNTS`/`aggregate_runset`), and visibly upgrades the Overview pillar of the Worring model.

Relevant files: `/Users/itay/Documents/repos/MSc/MMA/ivg-kg/.claude/worktrees/ivg-kg-p0-build/MOCKUP-WALKTHROUGH.md`, `app/panels/subgraph.py`, `src/ivg_kg/mock/fixtures.py` (`_OUTCOME_COUNTS`, `aggregate_runset`).

---

## Appendix C -- Lecture digest theses

### 5-AI4MMA (11 concepts)

Lecture 5 ("AI for Multimedia Analytics") extends the Worring MMA model from a static UI-pillar diagram into an AGENTIC reference architecture: AI/foundation models sit INSIDE the MMA loop as Visual Analytics Agents (specialized action agents: Search, Query, Generate, Analyze, plus a Coordinator), each driven by a Visual Analytics Strategy over prompt templates and each obliged to return a "trustworthy (lawful, ethical, robust) rationale" alongside its result. This is the exact architecture ivg-kg instantiates: the sampled LLM is a Generate/Analyze agent producing a draft + CoT, and the deterministic verifier is best framed as a specialized Analyze agent whose contract is precisely the trustworthy rationale (the Provenance Card = the agent's faithful structured rationale, not a narration). The lecture gives ivg-kg three concrete things: (1) a vocabulary to define the system as a human-AI teaming instrument over a graph data model with a fixed prompt-template set; (2) a formal visual-grammar (Vega-Lite encoding tuple + ATWL artifact->transform workflow) to justify the hue=status encoding invariant and the Overview->Inspection->Repair flow as an artifact-transform chain; (3) an explicit trust-building toolkit for foundation models (attention viz, counterfactual explanations, uncertainty-in-context) plus a guidance typology (orienting / directing / prescriptive) that maps directly onto the repair loop and the honesty layer. The MULTI-CASE case study (graph data model + expert-module tool-use agents + fixed prompt templates over an ontology, "no explicit strategy or guidance") is almost a sibling system to ivg-kg and gives a ready-made "describe-in-the-model" template for the report.

### 6-MMA4AI (12 concepts)

Lecture 6 reframes the entire ivg-kg project in the course's own terms: it is the "MMA4AI" direction — using multimedia/visual analytics TO understand, inspect, debug, and trust an AI model (here an LLM), as opposed to AI4MMA (using AI to help analyze media). Worring's canonical recipe for building such a tool is explicit and procedural: (1) shift from PROMPTING the model to PROBING its architecture, with "one main action: analyze" and a deliberately LIMITED role for guidance because guidance "could easily lead to bias" (Slide 6) — which directly licenses ivg-kg's deterministic, non-steering verifier and its honesty-first posture. (2) The build method (Slide 27): define purpose + target audience, consider the architecture and what its elements are, define scores/metrics that quantify those elements acting upon the data, pick visualizations for those scores, then balance many-simple-coordinated-views against one-complex-view via interaction. ivg-kg's claim STATUS (retrieved / Supportable / fabricated), support-frequency, and repair_leverage ARE its "scores" in this framework, and the Overview->Inspection->Repair spine is the coordinated-multiple-views answer. (3) Across four worked VA-for-model systems (Dodrio, the ViT analyzer, AttentionViz, VisQA, GNNLens) the lecture demonstrates a repeatable interface grammar — requirements-driven (R1/R2/R3 or G/T), overview-by-projection-then-drill-down-to-instance, glyph-encoded per-unit scores, comparison views, and crucially a single-instance vs aggregate-over-all-instances duality — which is the precise template for ivg-kg's single-run vs multi-run (N=20) modes and its repair loop. The lecture's interpretability/explanation definitions (Slide 17) and its "trust" motivation for decision-makers (Slide 33) give the project its vocabulary for the honesty layer. Net: this lecture is the strongest course-grounding for ivg-kg — it both DEFINES the problem (MMA4AI, probing, analyze-not-steer) and supplies concrete VISUALIZATION patterns (projection overview, glyph scores, instance/aggregate duality, comparison, ablation-as-evidence) that ivg-kg should explicitly claim and, in one or two cases, is currently missing.
