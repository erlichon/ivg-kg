# Panel verdict: trust, causality, verifier-reliability, and interpretability views

> Workflow: ivg-kg-trust-views (9 agents: 4 themed researchers + 4 skeptical filters
> + synthesis chair) | run 2026-06-12.
> STATUS NOTE: adopt-now shortlist (5 items) pending team veto; report-only and cut
> lists final. Composes with the locked two-mode design and the focus-decision verdict.

# Synthesis Verdict — ivg-kg feature triage (chair ruling, 2026-06-11, demo T-12 days)

## 1. ADOPT-NOW SHORTLIST (ranked, 5 items)

Cross-theme merges are explicit. Total budget: roughly 3×S + 2×M — feasible by 06-23 with the stated trims.

### 1. "Fabricated ≠ false" overlay + gate-coverage gauge *(trust — adopted as proposed)*
Fabricated claims whose triplet contains `unresolved_entities` keep the fabricated hue but get a diagonal-hatch pattern overlay + tooltip ("unsupported by this KG slice — entities not in slice; may be true in the world"); the SPEC-4.7 alignment/linking coverage fraction renders as a gauge in the Trust strip, visually distinct from gate error. This is a correctness fix, not a feature: without it the instrument can convince a viewer that a world-true claim is a lie — the worst miscalibration it can cause.
- **Panel:** Answer panel (hatch overlay) + Trust strip in Analytics panel (gauge).
- **Reads:** `link.py` unresolved_entities output; SPEC-4.7 coverage metric (both already computed).
- **Cost:** S.
- **Insight unlocked:** "Fabricated means unsupported by *this frozen slice*, and here is exactly which verdicts never even reached the gate."

### 2. Verifier Margin Surface *(MERGE: trust "Margin-to-tau borderline chips" + verifier "Tau-sensitivity flip band" — same persisted margin, same borderline claims, one feature)*
Per-claim: claims with |score − τ| < δ get a dashed border + "borderline" chip; hover shows a one-line [0,1] strip plot with τ tick and score dot. Global: a read-only τ-sweep lens in a Verifier-diagnostics drawer off the Trust strip — step chart of status counts vs a virtual threshold, with the frozen operational τ drawn as a locked vertical rule and the slider visibly labelled what-if-only. Pure label recomputation over persisted `entailment_score` + τ; zero model runs. δ comes from the 4.7 calibration fold if the gold set localizes the error band, else a documented fixed δ stated honestly in the tooltip.
- **Panel:** Answer panel (chips/borders) + Trust-strip drawer (sweep chart).
- **Reads:** ClaimRecord.entailment_score, GroundingRun τ (SPEC 4.3, already persisted).
- **Cost:** S.
- **Insight unlocked:** "Was this verdict robust or knife-edge — and how many verdicts in this answer would flip if τ moved a hair?"

### 3. Verdict Provenance Card *(MERGE: interpretability "Proof-Chain Provenance Card" + trust "Verdict lineage popover / wrench glyph" + interpretability "Spurious-Reason Glyph Badges" — three names for one provenance surface; build it once with one vocabulary)*
A per-claim collapsible card in the entity-detail sub-pane verbalizing the full deterministic decision path via templates over persisted fields (triplet → linking outcome incl. "unresolved → never reached the gate" → decision rung → winning premise → score/τ/margin → KG revision graded against). Two badges propagate to all panels: a **wrench** on any claim whose support path traverses an analyst-ADDed triplet (RepairSession log — without it, repair silently launders analyst assertions into "Retrieved"), and **spurious-reason glyphs** on Supportable claims with verbatim fired-rule hover text + hub ring on the subgraph. No LLM narration; every sentence is a typed trace field, so faithfulness is by construction. Trims per the skeptics: skip alias-orientation display and copyable-monospace polish; glyphs and wrench first if time runs short.
- **Panel:** bottom-middle entity-detail sub-pane (card); Answer panel + Subgraph (badges).
- **Reads:** persisted GroundingRun fields, `spurious_path`/`spurious_reason` (SPEC 4.8), RepairSession log — all existing.
- **Cost:** M (trimmed; the badge halves are S each).
- **Insight unlocked:** "Exactly *how* this verdict was reached, against *which* version of the ground truth, and which gameability detector fired."

### 4. Intervention Demo Pair: Counterfactual Twin View (REMOVE) + Repair Diff Slopegraph (ADD) *(MERGE of the two causality demo views — same Analytics demo surface, same chip renderer, the two halves of the perturbation spine; ADD half absorbs the kernel of interpretability's "Why-Fabricated Contrastive Card")*
REMOVE: side-by-side Full-context vs Evidence-withheld answer columns, both graded against the same full reference (header restates the invariant), withheld KG item marked with dashed border + hatch + scissors badge in the Subgraph; counts only, no cross-run claim alignment. ADD: a before/after slopegraph using the only spec-legal claim alignment (claim_id within one repair pair), where each FABRICATED→grounded flip is one countable delta line so `repair_leverage` is visually auditable; added triplet gets a plus badge on the Subgraph. Fold in the contrastive-card kernel: for a fabricated claim, a cached-pairs-only slot diff distinguishing "KG holds (Chopin, born, 1810) → VALUE mismatch" from "KG silent → MISSING FACT (repairable)" with an "add this fact?" link into the 4.6 repair flow — this makes the analyst's repair choice legible instead of magical. Cut order under pressure: paired-bar delta arrows first (decoration), then the slot-diff "add this fact?" wiring (keep the diff display); the sub-τ nearest-miss foil premise is **not** built (report).
- **Panel:** Analytics panel single-run demo area + Subgraph intervention badges.
- **Reads:** existing withhold path, two SingleRunStatusSummary objects, RepairResult, per-claim status lists, entailment cache + link.py relation table.
- **Cost:** M (twin view) + S (slopegraph) + S (slot diff) — the demo centerpiece, worth the largest share of remaining budget.
- **Insight unlocked:** "Withholding this evidence *visibly produces* fabrication, and adding this one true fact *visibly and countably* repairs it — with 'n=1, not an effect size' stamped on both."

### 5. Epistemic Channel Grammar *(causality — adopted as proposed, strictly three glyphs)*
A fixed glyph vocabulary stamped beside every quantitative readout: open circle = observational (support-frequency map), filled triangle-with-interval = interventional aggregate (sweep, absence-shift axis), outlined triangle "n=1" = single-sample demo result. Legend lives permanently in the Trust strip beside the verifier error bars; includes the agreement-scatter axis-language fix ("observed — correlational" / "intervened — causal estimate", quadrant labels only past the >2SE gate). It supplies the n=1 badges item 4 needs and consolidates the design's scattered prose caveats into one always-visible channel. Hard condition: exactly three glyphs, one legend, no per-view variants.
- **Panel:** Trust strip (legend); stamps appear wherever numbers do.
- **Reads:** nothing new — it labels existing/planned readouts.
- **Cost:** S.
- **Insight unlocked:** "What *kind* of claim is this number — observed, intervened, or anecdote — at the same glance that tells me how often the grader is wrong."

**Chair demotions of skeptic adopt-nows (overruled to keep the cap of 5):**
- **Trust-strip drill-down (reliability diagram + Squares confusion)** → final report. The trust-side skeptic's small-gold-set objection to the reliability-band strip applies with equal force here: 10 bins over a small student-labelled QA set yields mostly-empty bins and an over-read ECE. Items 1+2 already answer per-verdict calibration; generate the reliability diagram and 3×3 dot matrix as static report figures from the 4.7 calibration artifacts (near-free) rather than a live drawer.
- **Spurious-path forensics (detector breakdown + hub bar)** → final report figures. The user-facing half (per-claim badges, hub ring) ships inside item 3; the aggregate bars are error-analysis material that reads identically as two static Plotly figures in the report.
- **Instrument Causal Diagram (do-operator DAG)** → final report + drop the same static SVG into the Help modal. Hours of work, conceptual value; it does not compete for a build slot and answers the inevitable "why isn't support-frequency causal?" examiner question.

## 2. FINAL-REPORT ITEMS

**Evaluation roadmap**
- Reliability-band Trust strip / per-bin error lookup — the natural upgrade once a larger gold set makes 5–8 score bands non-vacuous.
- Trust-strip drill-down (reliability diagram + Squares-style confusion matrix) — ship as static report figures from the 4.7 calibration run; live drawer is roadmap.
- Flip-Persistence Strip (R=5 mini-replication of repair) — spell out the KG-item-ID persistence definition that respects the no-cross-run-alignment invariant; note R=5 Wilson intervals are information-free.
- Dual-verifier agreement (DeBERTa vs MiniCheck) — compute the QA-set κ once, report it with a disagreement-example table as verifier-robustness evidence; no UI.
- Conformal / Venn-ABERS calibrated gate — half-page principled umbrella over the margin surface, with the exchangeability caveat and "vacuous at this N" honesty.

**Design discussion / future work**
- Margin-calibrated abstain band — the principled successor to the flip band; pattern-channel-not-fourth-color abstention is worth a paragraph.
- Runner-Up Path Ribbon — persist top-k scored paths, show margin-over-runner-up; note the skeptic's correction (over-hop paths are never enumerated; the allowlist is a detector, not a search rule).
- Counterfactual Sentence Tooltips — the causal-verb-allowed/forbidden template split as design discussion; the disciplined hovertemplate with raw x/N counts is simply part of building the agreement scatter.
- Why-Fabricated foil half (highest sub-τ premise display) — describe alongside the shipped slot diff.
- Spurious-path forensics aggregate (detector-rate stack + hub-sensitivity bar) — error-analysis section figures.
- Instrument Causal Diagram — report figure + Help modal image.

## 3. CUT LIST

- **Wilson-bound halo on the support-frequency map** — at N=20 every interval is ~±0.2 so halos are near-uniform noise; dash-cytoscape lacks the primitive; keep only the one-line "12/20 runs (95% CI 0.39–0.78)" tooltip string, which the team should add when building the map anyway.
- **Slot-Erasure Gate Attribution** — placeholder-substituted hypotheses are out-of-distribution for the NLI gate, so the deltas measure artifacts while the encoding presents calibrated saliency: trust-washing on a verifier whose logic the Provenance Card already exposes fully; redundant with the slot diff in the same h/r/t vocabulary.

## 4. COHERENCE CHECK

The five items compose into **one layered trust story rather than fragments**, because they share a single spine: *global instrument calibration → per-claim verdict uncertainty → auditable provenance → honestly-labelled causal demos*. The Trust strip (Analytics panel, right) becomes the anchor hosting four co-located things: per-path error rates (existing), the coverage gauge (item 1), the entry point to the τ-lens drawer (item 2), and the three-glyph epistemic legend (item 5). The Answer panel (left) carries all per-claim marks; the entity-detail sub-pane (bottom-middle, SPEC 4.5 #7) hosts the Provenance Card; the Subgraph (middle) carries only intervention badges (scissors/plus), hub rings, and the existing path highlight. The demos (item 4) live in the Analytics single-run area and inherit their honesty badges from item 5's grammar — nothing invents a new caveat mechanism.

**One real fragmentation risk, with a ruling:** the per-claim status badge now attracts up to four marks (hatch, dashed border, wrench, spurious glyph). Enforce a channel discipline — hatch is the *pattern* channel (out-of-slice only), dashed border is the *border* channel (borderline only), and there is exactly **one glyph slot** with priority wrench > spurious > none; the Provenance Card shows everything the badge had no room for. The hue invariant survives untouched in every adopted item.

## 5. THE TRUST NARRATIVE

The instrument never asks the user to trust it — it shows its own error budget first: an always-visible Trust strip reports each verifier path's empirically measured error on an adversarial per-slice gold set, the fraction of claims that never reached the gate at all, and a fixed three-glyph grammar declaring whether any number on screen is observed, intervened, or a single sample. Every verdict then carries its own uncertainty: a deterministic margin to the frozen threshold flags knife-edge decisions, out-of-slice hatching separates "unsupported by this frozen slice" from "false in the world", and spurious-path detectors warn where symbolic support is structurally gameable. Every verdict is also auditable: a template-verbalized proof chain reconstructs extraction, linking, path search, and the entailment margin from persisted trace fields — with an explicit mark whenever the ground truth itself was edited mid-session by the analyst's repair. Finally, the causal claims are kept honest by construction: withholding and repair are shown as juxtaposed factual/counterfactual runs graded against an unchanged reference, single-shot demos are stamped n=1, and aggregate causal estimates appear only from the offline sweep with intervals and an indeterminate class — so the user always knows not just what the system concluded, but how sure it is, how it got there, and what kind of evidence the conclusion rests on.

## Appendix: per-theme proposal counts and skeptic adopt-nows

```json
[
  {
    "theme": "trust",
    "proposed": 6,
    "adopt_now": [
      "Margin-to-tau borderline chips",
      "Out-of-slice hatching + gate-coverage gauge ('fabricated is not false')",
      "Verdict lineage popover with repaired-evidence glyph"
    ]
  },
  {
    "theme": "causality",
    "proposed": 6,
    "adopt_now": [
      "Counterfactual Twin View for the REMOVE demo",
      "Repair Diff Slopegraph (ADD demo)",
      "Epistemic Channel Grammar (observed / intervened / n=1 glyphs)",
      "Instrument Causal Diagram (do-operator legend)"
    ]
  },
  {
    "theme": "verifier",
    "proposed": 6,
    "adopt_now": [
      "Tau-sensitivity flip band (verdict-robustness lens)",
      "Trust-strip drill-down: reliability diagram + Squares-style confusion view",
      "Spurious-path forensics: detector breakdown + hub-sensitivity bar"
    ]
  },
  {
    "theme": "interpretability",
    "proposed": 5,
    "adopt_now": [
      "Proof-Chain Provenance Card (template-verbalized verification trace)",
      "Why-Fabricated Contrastive Card (nearest-miss evidence with slot diff)",
      "Spurious-Reason Glyph Badges (detector provenance on Supportable claims)"
    ]
  }
]
```
