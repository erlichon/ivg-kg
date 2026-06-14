# UI6 -- Honesty Layer: implementation plan (Stage B)

> Prep artifact authored while the M-BOOKS sweep runs. **DO NOT BUILD until M-BOOKS
> is declared** (strictly-sequential hard gate). This turns SPEC-text sec 4.9 +
> the Stage-B brief into a concrete, file-level, subagent-executable plan so we
> start immediately once the gate opens. SPEC: sec 4.5, sec 4.7, sec 4.9.

## Goal
C1's defining property: the instrument shows its own error first; correlation never
reads as causation. Data-agnostic by design (renders for any loaded KG; degrades the
deployment tier gracefully for BYO-KG). Built onto the existing three-panel app
(`app/panels/{answer,subgraph,analytics}.py`) + mock fixtures FIRST, then shown on the
real post-M-BOOKS data.

## LOCKED encoding invariant (every task)
**Hue = STATUS only** (the fixed 3-grade palette in `app/theme.py`: Retrieved/Supportable/
Fabricated). Every new honesty mark rides an ORTHOGONAL channel and NEVER recolors:
- `fabricated != false` -> **pattern (diagonal hatch)**, out-of-slice claims only.
- epistemic glyphs -> **shape** (open circle / filled triangle+interval / outlined "n=1").
- borderline/margin -> **border** (dashed border + chip).
- per-claim badge -> **one glyph slot** (priority: repaired-evidence wrench > spurious-reason > none).
Reserve the word **"calibrated"** for the deployment tier ONLY.

## Data inputs (already available -- verified against schema.py + reliability_report.json)
Per-claim (`ClaimRecord`): `status`, `support_source` (cascade rung), `grounding_path`
(`GroundingPath` of `PathEdge{subject,property,object,traversed_forward}` = the winning
premise/path), `entailment_score` (margin = `|score - tau|`), `spurious_path` +
`spurious_reason`, `unresolved_entities` (-> hatch), `linked_entities`, `active_perturbations`.
Run (`GroundingRun`): `error_rates` (per-modality), `condition`, `baseline_run_id`.
Slice trust artifact (`reliability_report.json`): `gate` (NLI benchmark name -> instrument
prior), `calibrated`, `frozen_tau`, `overall_error_rate`, `per_modality_error[{modality,error_rate,n}]`,
`reliability_curve[{margin_lo,margin_hi,accuracy,n}]`, `linking_coverage`,
`adversarial_negative_accuracy`. Schema enum `EpistemicLevel` {OBSERVATIONAL,
INTERVENTIONAL_AGGREGATE, SINGLE_SAMPLE} drives the glyphs.

### Schema/CoT notes (resolve in task 0, coordinate if a field is truly needed)
- **Extraction (h,r,t) trace** is NOT a stored ClaimRecord field (ExtractedClaim is
  verifier-internal). The Provenance Card renders the extraction line from `text` +
  `linked_entities` ("claim text -> linked QIDs"); only add a stored field if faithfulness
  demands the literal (h,r,t) (coordinated additive change, announce first).
- **Generator CoT** ("stated, not necessarily faithful"): use `GroundingRun.answer_text`
  as the stated text beside the faithful card; the `BaseAIClient` evidence-trace seam can
  later carry a real CoT. No schema change for the mock-driven build.

## Tasks (ordered; each Tier-1 + Playwright screenshot; build on mock first)

### UI6-0 -- Mock honesty fixtures + Trust-strip data adapter (foundation)
Extend `src/ivg_kg/mock/fixtures.py` so the C1 honesty UI is demoable pre-real-data:
an out-of-slice claim (`unresolved_entities` set), a borderline claim (`entailment_score`
near tau), a `spurious_path`+`spurious_reason` claim, a multi-hop Supportable claim with a
`grounding_path`, a wrench claim (support path traversing an analyst-ADDed triplet), a
populated `error_rates`, and a committed mock `reliability_report` reader. Add a pure
`trust_strip_model(run, reliability, tau)` helper (no Dash) computing: instrument prior
(gate benchmark acc) + per-claim margin-to-tau + borderline flags; deployment calibrated
error (when `calibrated`); gate-coverage (linking_coverage); the 3-glyph legend data.
Unit-test the helper. *(Files: mock/fixtures.py, a new `app/honesty.py` pure-model module,
tests.)*

### UI6-a -- Always-on two-tier Trust strip (sec 4.9a)
Host in the Analytics column (always visible). **Instrument-level** (any KG): NLI gate
published benchmark accuracy (uncalibrated reliability prior) + per-claim **margin to tau**
(`|entailment_score - tau|`, a confidence proxy NOT calibration) + borderline dashed-border
chip + optional read-only **tau-sweep** what-if lens (status counts vs a virtual threshold,
frozen tau drawn as a locked rule). **Deployment-level** (when labels exist): error
**calibrated** on the gold QA set (books: from `reliability_report.json` per_modality_error).
BYO-KG degrade: instrument prior + "not calibrated to your KG" + "label N claims" affordance.
*(Files: app/panels/analytics.py, app/honesty.py, app/charts/ for the tau-sweep + reliability
curve; reads the trust_strip_model.)* Playwright: both tiers + margin chips render; word
"calibrated" only on the deployment tier.

### UI6-b -- Provenance Card (faithful, NO LLM narration; sec 4.9b)
Per-claim collapsible card in the entity-detail sub-pane (Subgraph panel), shown BESIDE the
generator CoT (CoT labelled "stated, not necessarily faithful"). Every sentence a TYPED
TRACE FIELD over the deterministic proof chain: extraction (text -> linked_entities) ->
link outcome (incl. "unresolved -> never reached the gate") -> cascade **rung**
(`support_source`) -> **winning premise** (`grounding_path` PathEdges verbalized) ->
**score / tau / margin** -> KG revision graded against. Carries the **why-fabricated
slot-diff**: VALUE-mismatch ("KG holds (Chopin, born, 1810) -> value mismatch") vs
MISSING-fact ("KG silent -> repairable") with an "add this fact?" link into the sec 4.6
repair flow (disabled stub + note if UI5/EX3 absent). Propagates two badges to Answer/Subgraph
(one glyph slot): **wrench** on any claim whose support path traverses an analyst-ADDed
triplet; **spurious-reason glyph** (verbatim `spurious_reason`). **NEVER generate the
rationale with an LLM -- faithfulness by construction.** *(Files: app/panels/subgraph.py,
app/panels/answer.py, app/honesty.py templates.)* Playwright: card opens beside the CoT with
typed fields, no narration; wrench + spurious badges show on the right claims.

### UI6-c -- "fabricated != false" overlay + gate-coverage gauge (sec 4.9c)
Out-of-slice claims (`unresolved_entities` set) keep the fabricated HUE but get a
**diagonal-hatch pattern overlay** (pattern channel, not a hue change) + tooltip
("unsupported by this KG slice -- entities not in slice; may be true in the world").
Render sec 4.7 **alignment/linking coverage** as a **gate-coverage gauge** in the Trust
strip, visually distinct from gate error (coverage = did the claim reach the gate; error =
how it was graded). *(Files: app/panels/answer.py for the hatch on claim chips, app/theme.py
for the hatch pattern, app/panels/analytics.py for the gauge.)* Playwright: an out-of-slice
claim shows the hatch + tooltip and KEEPS the fabricated hue; the gauge renders distinct
from error.

### UI6-d -- Epistemic glyph grammar (exactly 3 glyphs, 1 legend; sec 4.9d)
**open circle** = observational (support-frequency map, sec 4.8); **filled triangle +
interval** = interventional aggregate (the sweep / RQ2, sec 8); **outlined "n=1" triangle**
= single-sample demo (single-run REMOVE/ADD delta). Driven by the schema `epistemic_level`
fields (`SingleRunStatusSummary.SINGLE_SAMPLE`, `AnswerDiagnostics.OBSERVATIONAL`); the
sweep figure is stamped INTERVENTIONAL_AGGREGATE (EX4, already done, static). Legend lives in
the Trust strip; NO per-view variants; causal/quadrant language only past the uncertainty
gate. *(Files: app/theme.py glyph shapes, app/panels/analytics.py legend, wired into the
support-frequency map + single-run delta.)* Playwright: exactly 3 glyphs + 1 legend present;
correct glyph per view.

## Execution
- superpowers:subagent-driven-development: one fresh implementer per task (UI6-0 -> a -> b ->
  c -> d), TDD, then Opus spec + quality review (Tier-1), then **Playwright app-verification
  with a screenshot per task** (launch the mock-driven app; later re-verify on the real
  post-M-BOOKS run via `IVG_KG_RUN_ID`). CI green each commit; ASCII; hue=STATUS.
- Build mock-driven FIRST (UI6-0..d on `mock/fixtures.py`); finalize on real data after
  M-BOOKS using the run_source shim. The cosmetic follow-ups from earlier (header reads
  "(offline mock data)" in real mode; add-triplet Chopin pre-fill) can be folded in here.
- No image-axis code (books-first hard gate still applies).
