# MMA peer-review panel + multimedia-novelty verification

> Two ARS runs, 2026-06-12, gating the project_statement commit.
> (1) academic-paper-reviewer (5 personas: EIC + VA + Eval/Trust + ML/NLP skeptic + Devil's Advocate)
> on project_statement.md + FOCUS.md. (2) Focused multimedia-novelty fact-check (2 verifiers, web-grounded).
> STATUS: framing fixes applied to the statement/FOCUS from this record; deferred items are a roadmap.

## Editorial verdict: MINOR REVISION — it SURVIVES the MMA novelty check

Scores (course-calibrated): EIC 84; VA reviewer 78; Eval/Trust 78; ML/NLP 78 (72 science / 88 novelty-honesty).
Four independent "minor revision"; one Devil's-Advocate CRITICAL (addressable). Consensus: this is a
GENUINE multimedia-analytics contribution (the instrument C1), not an NLP-tool-with-a-dashboard; the
narrowed novelty is SUFFICIENT because the contribution is the instrument; the honesty (conceding
ContextCite / Attention-is-not-Explanation) is a graded STRENGTH.

### The CRITICAL (Devil's Advocate, echoed by skeptic + EIC)
The multimodal axis -- what makes it *Multimedia* Analytics -- is load-bearing on paper but
back-loaded / gated-on-unverified-artwork / VLM-noisy / self-labelled, and the only unconfounded
cross-modality CONTRAST (Phase B) is first-to-cut. The statement OVER-PROMISES a contrast (§18/§22)
that §23/§53/§54 walk back. Over-repeating "committed, not contingent" reads as protesting-too-much.

## Multimedia-novelty verification (the pre-commit gate)

- **Instrument combination NOVEL (guaranteed):** no prior work combines interactive VA + per-claim KG
  grounding/classification + multi-layer KG/text/image attribution + image-ablation + KG-repair.
  Nearest competitor *Graphing the Truth* (arXiv:2512.00663) is TEXT-ONLY. Claim the COMPOSITION, not
  the primitives: visual source attribution = VISA [2]; image-withholding ablation = VDGD/M3ID (prior
  art); multimodal citation = MCiteBench. The image-ablation *mechanic* is NOT novel; the integration is.
- **Fact-bearing image modality GUARANTEED but THIN:** taxa range-maps verified ~62% non-redundant
  (live SPARQL) -> a real non-redundant image modality ships. Caveats: one narrow fact type (range);
  VLM range-map reading is a weak spatial skill.
- **Rich version (artwork) contingent-but-SECURABLE:** run a pre-registered 3-way non-redundancy check
  on ~150 band artworks before locking (fact NOT in triples, NOT in description, VLM reads it at a
  pre-set rate). This is the "work harder" task that converts thin-floor -> robust. Risk: rich
  descriptions may already narrate composition; VLM relation-hallucination is the weakest axis.

## Framing fixes APPLIED to the statement + FOCUS (pre-commit)

1. **Multimodal floor + quarantine the contrast:** robust claim = WITHIN-modality absence induces
   fabrication per slice; the cross-modality CONTRAST is Phase-B/future UPSIDE, not promised. Soften
   "load-bearing" -> "instrumented and analyzed."
2. **Multimedia novelty honesty:** claim the instrument COMPOSITION; cite Graphing the Truth (text-only
   threat), VISA, VDGD/M3ID, MCiteBench as closest prior art; anchor the guaranteed floor (taxa +
   multi-layer attribution); artwork = securable upside gated on the pre-registered check.
3. **C3 novelty-tension reframe:** novelty = instrument + taxonomy-as-a-lens (in C1 by construction)
   vs the populated quadrant (cuttable finding); promote repair_leverage as standalone delivered
   novelty (vs CogMG).
4. **Verb/term scoping:** evidential status terms; "calibrate trust" / "legible to non-expert" =
   design intent pending the user study; instrument-tier trust = "uncalibrated reliability prior" (not
   "calibrated" -- reserve that for the deployment tier).
5. **Reference hygiene:** flag implausible/future arXiv IDs ([7] 2605.xxxxx is not a valid year-month;
   verify [9]/[20]); add VDGD + MCiteBench for the multimedia positioning.

## Deferred to build + final report (roadmap, not statement-blocking)

- Build the honesty layer + coordinated views + repair on a STUBBED backend (5-10 pre-graded answers)
  FIRST, swap in the real verifier later -- guarantees the VA contribution ships if the NLP slips (R1).
- DRAW the two novel views (epistemic-glyph legend on a real node; agreement quadrant as a brushable
  scatter with brush-back to the subgraph).
- Analysis integrity (skeptic): no-repair re-run BASELINE so repair_leverage is net of generator
  variance; PROPAGATE verifier error as a noise floor on the C2 shift; hand-validate the
  reasoned-supportable bucket + report path multiplicity (consider "path-supportable" in prose); use
  knowledge-withheld as the hard-entity control for the content-absence confound.
- RELIABILITY CURVE (margin-bin vs empirical accuracy on the books gold set) -- converts trust from
  asserted to demonstrated; labels already exist.
- **Run the artwork non-redundancy gate** (the "work harder" task above) before the image phase locks.
