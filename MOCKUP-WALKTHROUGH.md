# IVG-KG dashboard — mockup walkthrough

A polished, **offline mock** of the ivg-kg grounding dashboard for the intermediate
report. No LLM/VLM, no SPARQL, no network, no entailment model — all data is
hand-authored (`src/ivg_kg/mock/fixtures.py`). The grounding backend is still a stub.

**Scenario:** *"When was Frédéric Chopin's father born?"* The mock answer deliberately
contains a **fabricated date** (17 June 1771; the grading reference holds 15 April 1771)
— the absence-induced hallucination the tool is about.

## Run it

```sh
task run            # background → http://127.0.0.1:8050   (task stop to stop)
# or:  uv run python -m app.app        (foreground, Ctrl-C to quit)
# or:  task dev                        (foreground, hot-reload)
```

Three columns: **Answer** (left) · **Subgraph** (middle, the focus) · **Analytics**
(right). Hue encodes claim **status** everywhere — Retrieved = green, Supportable =
amber/gold, Fabricated = magenta/red. Selected claims are told apart by an **accent
outline + numeric badge** (never by hue). The *Process* pillar is the `>>PROPOSED →
>>VERIFY → status` trace in the Answer column; the *Trust* pillar is the always-visible
per-modality classifier-error strip in Analytics.

## The eight interactions

1. **Status filter (3 grades).** Answer panel → untick e.g. *Retrieved* and *Supportable*
   in "filter by grade": the claim list narrows to **Fabricated** only. Clear all ticks →
   every claim shows again ("proposed" is the universe, not a fourth grade).
2. **Multi-select → brush onto the subgraph.** Click several claim rows (or the coloured
   spans in the answer). Each selected claim gets a numeric badge (Claim 1, 2, …); the
   subgraph highlights each one's support path in its **status hue** with an accent badge
   ring on its anchor node. → `screenshots/03-multiselect-brush.png`
3. **1st-degree neighbourhood under a node cap.** The subgraph shows each claim node plus
   its immediate neighbours (de-emphasised); neighbour expansion is skipped above
   `config.SUBGRAPH_NODE_CAP` (40). The Chopin graph is small, so all 6 nodes show.
4. **Click a claim → per-slot analytics.** Each selected claim gets its own collapsible
   card under PER-CLAIM (closed by default). The card is anchored on the **fact SLOT**
   (head + relation), not the single variant: expand it for the **variant breakdown**
   (every value the generator emitted for the slot, each with its ONE fixed status and
   its draw frequency), presence rate, stability, and leverage. Selecting several shows
   several cards. → `screenshots/02-fabricated-claim-perclaim.png`
5. **Full-answer analytics + N selector.** Top-right: the **claim-status distribution**
   (fraction **± SE**, where SE = sqrt(p(1-p)/N)) + the **fabrication rate**, computed over
   **N generation draws** under the FULL condition. The verifier is a *deterministic*
   instrument; the **generator** is the stochastic system under test, so the spread is
   **generation variance** — we draw the generator N times *per condition*, never "run the
   verifier N times". Switch **generation draws (N) = 5 / 10 / 20** — the distribution
   shifts. A prominent **small-N caveat** sits above it. → `01-overview`
6. **Per-slot stacked-bar + variant breakdown + stability + spurious chip.** Expand a
   card: the **variant breakdown** (e.g. the father's birth-date slot shows *15 April 1771
   · retrieved* and *17 June 1771 · fabricated* with their draw counts — fabrication is a
   **wrong value in the same slot**), a **per-condition stacked bar** (full /
   knowledge-absent / content-absent, stacked by {Retrieved, Supportable, Fabricated,
   Absent} over the N draws), the **stability** scalar (slot-level), the RQ2
   absence-leverage / fabrication-induction readouts, and — on Supportable slots only — a
   **⚠ "path suspect"** chip + reason. Every score has a click-to-open **ⓘ** with its
   definition + formula. → `02-fabricated-claim-perclaim`
7. **Tap a subgraph node → zoom + entity-detail.** Tapping a node zooms to it + its
   1st-degree neighbours and opens the **entity-detail pane** (bottom-middle) with a
   static placeholder entity image + label/description. *⟲ reset view* restores the
   overview. → `screenshots/04-node-zoom-detail.png`
8. **Full-answer subgraph (Overview).** On load (and after *reset view*) the subgraph is
   the overview: all claim nodes + their 1st-degree neighbours, including the distinctly
   styled **literal** node (the date of birth). → `screenshots/01-overview.png`

Plus: the **Process** pillar is merged into the claim list (each claim shows
`✓/✗ proposed → verified`, no separate trace block); and the persistent **Trust**
strip renders `error_rates` (text-NLI 6%, structure-path 9%).

## Header controls
- **Slice selector** (top-left): switch data slices. Mock — the one books scenario
  (Chopin) is selected; the gated `taxa` / `artwork` image slices are shown disabled
  (built post-M-BOOKS).
- **⚙ generation** (top-right): toggles a **generation-settings** panel — temperature,
  top-p, max-new-tokens, model — for the live N-generation path. Presentational in the
  mock; the on-stage figures run off precomputed offline run-sets (§4.6/§10).

## Graph editor + repair loop (SPEC-text §4.6, RQ3 + CogMG)
The defining interaction, and a **deterministic re-verification** — NOT a regeneration.
The claim text is held **fixed**; you edit the graph and the **same** claims re-grade
against the edited KG (instant, bit-stable). This is a *different question* from the
N-draw generation-variance distribution in Analytics, and is labelled distinctly on both
surfaces. Ablation is **per specific triple** — there is no global "knowledge-absent"
mode; you edit the **graph itself**. **Flow:** edit the graph → the fixed claims
re-verify against the full reference → **both the subgraph and the answer update**.
- **Remove on the graph:** tap an **edge** in the Subgraph panel → its triple shows in
  the entity-detail pane with **"✕ remove this triple"**. Removing it drops the edge
  *and* recolours the answer (e.g. remove `father (P22)` → "father was Nicolas Chopin"
  and the France-via-father path flip to Fabricated; "grounded 5/6 → 3/6").
- **Re-add (RQ3 repair):** removed triples appear in the bottom strip with **"+ re-add"**.
- **Inject (CogMG):** the bottom strip has an **editable inject form** — subject / relation /
  value, pre-filled with a model **↻ suggestion** but fully editable; **✚ inject** adds the
  new triple (green dashed edge) and corrects the value-error date claim.
  → `screenshots/07-repair-loop.png`

> Mock note: scripted + deterministic (no real generation/injection) — it shows the
> interface and the flow so you can inspect it.

## Reading aids
- **Variance model:** the **verifier** is a *deterministic* instrument (it always grades
  against the full KG), so it is **not** the source of any spread. The **generator** is the
  stochastic system under test: we draw it **N times per condition** {full,
  knowledge-absent, content-absent}. Every per-draw difference is **generation variance** —
  never "the verifier runs N times". A fact **slot** (head + relation) can be filled by
  different **variants** (values) across draws; a variant has exactly **one fixed status**
  (deterministic verifier), so a slot's mixed distribution reflects *which variant the
  generator emitted*, not a per-claim status flip.
- **Fraction ± SE error bars** on the distribution: bar = the fraction of claims in that
  grade over the N draws; whisker = the **SE of the proportion**, SE = sqrt(p(1-p)/N) —
  *not* the Bernoulli per-draw std. A **small-N caveat** is shown prominently: N=20 is a
  floor, and absence-leverage (a difference of proportions, SE ≈ 0.16 at N=20) is only
  meaningful above ~0.3.
- **Two distinct per-claim views, labelled apart:** (i) the per-slot **generation-variance
  distribution** over N draws (the experiment, in Analytics); (ii) the **deterministic
  graph-edit re-verification** of a *fixed* claim against the edited KG (instant, no
  regeneration; in the graph editor) — "what this verdict rests on".
- **ⓘ info indicators** next to every score — **click** to open a persistent note with the
  definition + formula (stability spells out H, the slot outcome, FULL, K; absence-leverage
  / fabrication-induction explain the N-draws-per-condition contrast + the small-N SE; Trust
  explains the curated-QA-gold-set error measurement).
- **Pastel 3-grade palette** (hue = status), identical in every panel; selected claims are
  told apart by an outline + numeric badge, never by hue.

## Screenshots
| file | shows |
| --- | --- |
| `screenshots/01-overview.png` | Overview (#8), full-answer analytics (error bars + ⓘ), gold-set verifier-reliability **above** per-claim, graph-editor strip |
| `screenshots/02-fabricated-claim-perclaim.png` | Selected claims → one collapsible per-claim card each, expanded for the stacked bar + leverage (#4/#6/#7) |
| `screenshots/03-multiselect-brush.png` | Multi-selected claims brushed onto the subgraph with badges + readable edge labels (#2) |
| `screenshots/04-node-zoom-detail.png` | Node tapped → zoom + entity-detail pane (#7) |
| `screenshots/06-generation-settings.png` | ⚙ generation-settings panel open (mock LLM params) |
| `screenshots/07-repair-loop.png` | Graph editor: tapped the `father (P22)` edge → removed it → subgraph edge gone + answer's c1/c5 recolour to Fabricated (grounded 3/6); editable inject form below |

## Authored design details (where the spec left them open)
- **Node cap:** `SUBGRAPH_NODE_CAP = 40` (`src/ivg_kg/config.py`).
- **Status palette (hex):** Retrieved `#3fb950`, Supportable `#d29922`, Fabricated
  `#f7508d`; `Absent` (stacked-bar 4th segment) `#6e7681`; selection-outline accent
  `#58a6ff` (`app/theme.py`).
- **Spurious-path reason (c5):** *"relation/value illegitimacy: the path reaches France
  via the father's place of birth (P22→P19→P17), not the subject's own birthplace (P19) —
  Chopin was born in Żelazowa Wola, Poland."*
- **N choices:** {5, 10, 20}, default 20; per-**slot** variant draw distributions
  hand-authored in `fixtures.py` (`_SLOT_VARIANTS` + `_SLOT_DRAW_COUNTS`: each slot's
  values and how often the generator emits each per condition), aggregated to slot-level
  diagnostics by `src/ivg_kg/diagnostics.py` (§4.8). The father's birth-date slot
  (`SLOT_FDOB`, Nicolas Chopin · P569) is deliberately **multi-variant** — both the correct
  *15 April 1771* (retrieved) and the displayed *17 June 1771* (fabricated) fill it, making
  "fabrication = a wrong value in the same slot" visible.
