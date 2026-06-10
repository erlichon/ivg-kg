# IVG-KG dashboard — mockup walkthrough

A polished, **offline mock** of the ivg-kg grounding dashboard for the intermediate
report. No LLM/VLM, no SPARQL, no network, no entailment model — all data is
hand-authored (`src/ivg_kg/mock/fixtures.py`). The grounding backend is still a stub.

**Scenario:** *"When was Frédéric Chopin's father born?"* The displayed answer contains
a **fabricated date** (17 June 1771) — the KG holds no usable birth-date fact for the
father, so the date claim cannot ground. That gap is what the **gap-repair** demo fixes.

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
>>VERIFY → status` trace merged into the claim list.

## Generator vs verifier (the variance model)
The **verifier** is a *deterministic* measurement instrument: it always grades against
the **full** grading reference, so it is **never** the source of any spread. The
**generator** is the stochastic system under test. So when we re-run a query N times,
every difference across runs is **generation variance** — we draw the *generator* N
times, never "run the verifier N times". Claims are **not aligned across runs**; only
stable KG-item IDs (entities, triplets) are.

## Analytics: two modes (a mode toggle)

**SINGLE-RUN mode** (default) — one generated answer.
- Status **counts + percentages** over that answer's ~6 claims, with **NO error bars**
  (it is a single sample). → `screenshots/01-overview.png`
- Per-claim status lives in the Answer panel; select a claim to highlight its
  **support path** on the subgraph ("what this verdict rests on").

**MULTI-RUN mode** — re-run the query **N times** (N selectable, **default 20**).
- **(a) Status distribution = mean ± SE** of the per-run answer-level fraction of claims
  in each grade. The error bars are the **SE of a proportion** `sqrt(p(1-p)/N)` — *not*
  the ~0.5 Bernoulli per-draw std. A **prominent small-N caveat** states *"N=20 is a
  floor; small differences are within noise."* → `screenshots/05-multirun.png`
- **(b) Support-frequency** — for each KG **node** and each **triplet**, the fraction of
  the N runs in which it was **used** to ground a claim (it lies on the support path of
  ≥1 grounded claim that run). Surfaced as **node-size / edge-weight on the subgraph**
  plus a **ranked list**. It is **observational importance** ("how often grounding routes
  through this item") — explicitly **NOT** causal leverage.
- **Withhold-from-context selector** {full · content-withheld · knowledge-withheld} — see
  the next section; it shows the **distribution shift**.

## Two perturbation layers (distinct grading semantics)

**1. Withhold-from-context (RQ2 absence experiment) — Analytics, multi-run.**
Hide a description (content) or a triplet (structure) from the **generation context
only**. The item **stays in the grading reference**; grading is always against the
**full** reference. So withholding shifts the multi-run status distribution toward
fabrication **without relabelling true claims**. The result is the **shift** across
{full, content-withheld, knowledge-withheld} — shown as the per-condition fabrication
rate. In the mock: full ≈ 26% fabricated, content-withheld a mild rise, knowledge-withheld
≈ 84% (structure withheld hurts most). **This layer never changes the grading reference.**

**2. Edit-the-KG (gap-repair / exploration) — the bottom GRAPH EDITS strip.**
This **genuinely changes the KG / grading reference**, and grading then uses the
**current (edited)** KG. → `screenshots/07-repair-loop.png`
- **Gap-repair beat:** the date claim (c3) is fabricated because the KG holds no usable
  birth-date fact. **Inject** the curated date (the form is pre-filled with a model
  **↻ suggestion**, fully editable; **✚ inject**) → re-run → c3 flips to **retrieved**.
- **Repair-leverage** = the **COUNT** of claims that flip FABRICATED → grounded on that
  restore + re-run (RQ3). The strip shows e.g. **"+1 repaired: c3"** and replaces the bare
  "grounded X/6" with a before→after framing (the absolute "grounded N/6 now" is kept too).
- **Remove** a triple by tapping its **edge** in the Subgraph panel (free exploration) →
  the edge leaves the KG and the answer recolours (e.g. remove `father (P22)` → c1 and the
  France-via-father path flip to Fabricated). Removed triples come back via **"+ re-add"**.

> A caption on both surfaces states the difference: **withhold-from-context never changes
> the grading reference; edit-the-KG deliberately does.**

## Subgraph interactions (shared by both modes)
- **Multi-select → brush.** Click claim rows (or coloured answer spans). Each gets a
  numeric badge; the subgraph highlights each one's support path in its status hue with an
  accent ring on its anchor node. → `screenshots/03-multiselect-brush.png`
- **1st-degree neighbourhood under a node cap** (`config.SUBGRAPH_NODE_CAP` = 40); the
  Chopin graph is small, so all nodes show.
- **Tap a node → zoom + entity-detail** (bottom-middle): static placeholder image +
  label/description. *⟲ reset view* restores the overview. → `screenshots/04-node-zoom-detail.png`
- In **multi-run** mode the node sizes / edge widths reflect **support-frequency**.

## Header controls
- **Slice selector** (top-left): the one books scenario (Chopin) is selected; the gated
  `taxa` / `artwork` image slices are shown disabled (built post-M-BOOKS).
- **⚙ generation** (top-right): toggles a presentational **generation-settings** panel
  (temperature, top-p, max-new-tokens, model) for the live multi-run path. The on-stage
  figures run off precomputed offline run-sets (§4.6/§10). → `screenshots/06-generation-settings.png`

## Status filter
- **Status filter (3 grades)** in the Answer panel narrows the claim list; clearing it
  shows all ("proposed" is the universe, not a fourth grade).

## Screenshots
| file | shows |
| --- | --- |
| `screenshots/01-overview.png` | Single-run mode: status %/counts (no SE), the edit-the-KG strip below |
| `screenshots/05-multirun.png` | Multi-run mode: mean±SE distribution + small-N caveat + withhold-from-context shift + support-frequency ranked list (subgraph sized by support-frequency) |
| `screenshots/03-multiselect-brush.png` | Multi-selected claims brushed onto the subgraph with badges + readable edge labels |
| `screenshots/04-node-zoom-detail.png` | Node tapped → zoom + entity-detail pane |
| `screenshots/06-generation-settings.png` | ⚙ generation-settings panel open (mock LLM params) |
| `screenshots/07-repair-loop.png` | Edit-the-KG: inject the curated date → c3 flips to grounded → "+1 repaired: c3" repair-leverage |

## Authored design details (where the spec left them open)
- **Node cap:** `SUBGRAPH_NODE_CAP = 40` (`src/ivg_kg/config.py`).
- **Status palette (hex):** Retrieved `#8fd9a8`, Supportable `#f2d08a`, Fabricated
  `#f4a6c0`; selection-outline accent `#58a6ff` (`app/theme.py`).
- **Spurious-path reason (c5):** *"relation/value illegitimacy: the path reaches France
  via the father's place of birth (P22→P19→P17), not the subject's own birthplace (P19) —
  Chopin was born in Żelazowa Wola, Poland."*
- **N choices:** {5, 10, 20}, default 20. Per-condition, per-fact run outcomes
  (`_OUTCOME_COUNTS` in `fixtures.py`: ok / fab / absent counts over 20 runs) drive the
  multi-run distribution and its shift; grounded claims carry support paths so
  support-frequency aggregates over stable KG-item IDs (`diagnostics.aggregate_runset`).
- **Support-frequency** is observational: node size scales 40→96 px and edge width
  1.5→8.5 with the fraction of runs the item grounded a claim (`app/panels/subgraph.py`).
- **Repair-leverage** is measured vs the original full-graph answer (only the date claim
  is fabricated there), so injecting the curated date reports **+1 repaired: c3**.
