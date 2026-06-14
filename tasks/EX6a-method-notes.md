# EX6a -- Method / backend section: draft notes

> Backend-stream notes for the scientific report (due 2026-06-25). Draft scaffolding,
> not final prose. Faithful to what is actually built on `itay/m-books-honesty`. ASCII.
> SPEC: sec 4.3, sec 4.7, sec 4.9.

## 1. Generator vs verifier (the methodological spine)
Two systems with opposite goals, never blurred. **Generator** (system under test): a sampled
local LLM -- Qwen2.5-7B-Instruct served via Ollama through the `BaseAIClient` abstraction
(no provider SDK in business logic). Stochastic on purpose: temperature ~0.7, drawn N times
per condition, **seeded** `seed = f(question_id, condition, sample_index)` for reproducibility;
all per-draw variance is GENERATION variance. **Verifier** (measurement instrument):
deterministic, a DIFFERENT model family (Bespoke-MiniCheck-7B offline / DeBERTa-v3-large
live), not an LLM-as-judge, no chain-of-thought, and it ALWAYS grades against the FULL
grading reference. No self-verification: a verifier sharing the generator's family inherits
correlated blind spots and would pass the generator's own hallucinations. This is the KGR
deviation -- KGR uses the LLM itself as verifier; we replace that stage with a deterministic
entailment gate over symbolically selected evidence, so generation is the only stochastic stage.

## 2. The deterministic, non-steering verifier is a feature, not a limitation
Licensed by L6 ("guidance can easily lead to bias"). The verifier does not steer the
generator and emits no narration; its "reasoning" is a faithful deterministic proof chain
(the Provenance Card), contrasted on-stage with the generator's CoT labelled "stated, not
necessarily faithful" -- the fallible-vs-faithful contrast IS the lesson and visualizes
system-under-test (Generate agent) vs instrument (Analysis VA-Agent, an L5 analysis agent
whose contract is a trustworthy rationale).

## 3. The grounding cascade (extract -> link -> classify)
Per claim, deterministic: (A) **extraction** -> structured (h,r,t) triplets (verifier-side,
pinned greedy); (B) **entity linking** (LabelAliasIndex default / ReFinED opt) with a
property-alias + inverse-pair canonicalization so stable KG-item IDs key identically
regardless of surface phrasing/direction (out-of-slice -> `unresolved_entities`, distinct
from FABRICATED); (C) **classification** decision order: direct triple entailing ->
RETRIEVED/DIRECT_TRIPLE; content fact (description/curated label) entailing ->
RETRIEVED/TEXT_CONTENT; **undirected** multi-hop path 2..k (literal nodes excluded as
waypoints, highest-entailment path) -> REASONED_SUPPORTABLE/MULTI_HOP_PATH; else FABRICATED,
`spurious_path=True` if evidence existed but failed entailment. The **entailment gate is
value-sensitive and asymmetric** (premise = serialized reference evidence, hypothesis = claim;
do not invert): a claim asserting a value the evidence contradicts/omits fails -> FABRICATED.
Three evidential statuses (retrieved / reasoned-supportable / fabricated), not a process claim.

## 4. Evidence vs grading-reference split (sec 3.2 correctness spine)
A perturbation withholds evidence from the GENERATION CONTEXT only; classification always
grades against the full grading reference (KG-full triples + curated content labels), never
the ablated context. Two perturbation operations, distinct grading: REMOVE
(withhold-from-context, the controlled absence manipulation -- grade vs FULL) vs ADD
(edit-the-KG repair -- grade vs the current KG). A fact hidden from the generator stays
gradable; that is why content-only probes must target description-only facts (no surviving
triple), or absence induces no fabrication.

## 5. Classifier-error calibration + the reliability curve (deployment trust tier)
Error on a curated gold QA set per slice, INCLUDING adversarial value-swapped negatives
(so an entity-match-only grader is caught), reported **per modality path** (text-NLI gate
and structure path search separately). tau/k are frozen on a disjoint calibration fold and
never tuned post-hoc. The **reliability curve** (margin-bin `|score - tau|` vs empirical
accuracy on the gold set) converts trust from asserted to demonstrated -- the per-claim margin
is shown to track accuracy. The gold-QA-set error is the deployment-level CALIBRATED number;
"calibrated" is reserved for this tier. (Books demo: computed with the real MiniCheck-7B.)

## 6. RQ2 absence aggregate (the interventional contribution)
The {full, content-withheld, knowledge-withheld} x N-run offline sweep over the fixed
question bank aggregates to the claim-status distribution shift across conditions -- a static
report figure stamped INTERVENTIONAL_AGGREGATE (filled triangle + interval). The GR10
per-modality classifier error is propagated as a **noise floor**: a shift counts only when it
clears the gate's own error. **Hard-entity control:** knowledge-withheld is the
intrinsic-difficulty control for the content-absence/obscurity confound, so a fabrication
shift is attributable to absence, not baseline entity difficulty. Aggregation is answer-level
(per-run claim-status fractions, then mean +/- SE across runs; SE of a proportion
sqrt(p(1-p)/N); N=20 is a floor).

## 7. repair_leverage (RQ3, standalone delivered novelty)
A COUNT of claims that flip FABRICATED -> grounded when the analyst restores missing evidence
(edit-the-KG) and re-runs, paired within one answer's before/after by claim-text SEMANTIC
matching (not raw claim_id; the re-run regenerates the answer), reported NET of a matched
no-repair re-run baseline (FULL_NO_EDIT_RERUN) so flips from re-sampling alone are subtracted.
Differentiates from CogMG (repairs but does not measure which repairs matter).

## 8. The honesty layer (trust + interpretability + causality, one spine)
Two-tier data-agnostic trust (instrument-level uncalibrated prior = NLI benchmark accuracy +
per-claim margin-to-tau; deployment-level calibrated error on the gold set); "fabricated !=
false" hatch overlay for out-of-slice claims; the faithful Provenance Card (typed trace
fields, no LLM narration) with the why-fabricated slot-diff (value-mismatch vs missing-fact ->
repairable); and the epistemic glyph grammar (exactly 3 glyphs: observed circle / intervened
triangle+interval / n=1 outlined triangle) that prevents reading correlation as causation --
the disciplined-encoding causality contribution (not a new causal method).

## 9. Reproducibility note (honest methods detail)
ALL reported/figure numbers come from the OFFLINE precompute with MiniCheck-7B; the live
DeBERTa path verifies live but never sources reported numbers, so the verifier-model choice
does not affect reproducibility. Classification is deterministic given a fixed answer text, so
a frozen scenario re-renders identically; the sweep is crash-safe + resumable (per-grounding
incremental writes). **Environment pin:** Bespoke-MiniCheck-7B is an InternLM2 decoder-only
model whose remote modeling code targets transformers 4.x; under transformers 5.x it loads but
its forward path is broken (no GenerationMixin, removed legacy-cache API, silently
non-value-sensitive logits), so we pin transformers >=4.48,<4.50 and score via a single
forward pass over the canonical chat-template prompt (system prompt + "Document:/Claim:"),
reading first-token P("yes"). Determinism: greedy, fixed model state, bf16 on MPS (bit-stable
within the one cached offline run).

## 10. Three explicit contribution bullets (for the abstract/intro)
- **C1 (instrument):** an interactive MMA4AI tool that makes LLM knowledge-graph grounding
  inspectable, trustworthy, and repairable, via a deterministic calibrated verifier + the
  Overview->Inspection->Repair loop wrapped in the honesty layer.
- **C2 (absence finding):** controlled absence-induced hallucination reported as a
  modality-resolved distribution shift (within-modality claim; cross-modality contrast
  quarantined).
- **C3 (agreement taxonomy-as-a-lens + repair_leverage):** observational support-frequency vs
  interventional absence-shift at KG-triple grain, with repair_leverage as a standalone
  delivered measure (the populated quadrant is the cuttable empirical finding).

## 11. Related work mapping (novelty honesty)
Frame as the COMPOSITION + KG-triple granularity + agreement taxonomy, NOT inventing causal
attribution (cite ContextCite) nor the cited!=relied phenomenon (Attention is not
Explanation). Map the interface onto Worring's MMA build recipe and the Sacha 2014
knowledge-generation cycle (exploration/verification loops); the verifier as an L5 Analysis
VA-Agent; Perez-Messina guidance ladder (Orienting + Directing, deliberately not
Prescriptive). Reuse dossier: KGR (reimplemented stages, split supported -> retrieved/
reasoned-supportable), RefChecker (LLMExtractor), VeGraph (MIT prompts), MiniCheck (asymmetric
NLI gate), ReFinED (opt EL).
