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
- **Select KG items → highlight in the graph.** Click a row in the support-frequency
  list (a ● node or ◆ triplet); it is highlighted on the subgraph with an accent
  outline / thick accent edge — the same brush behaviour as selecting claims.
  → `screenshots/05-multirun.png`
- **Withhold-from-context selector** {full · content-withheld · knowledge-withheld} — see
  the next section; it shows the **distribution shift**.

## KG editing with per-edit SCOPE (the bottom KG EDITS strip)
Every edit chooses a **scope** (the toggle), which decides what it touches — this *is*
the SPEC §4.4 two-layer distinction, made interactive:

- **generation only** — change the model's **generation context** only; grading still
  uses the **FULL** reference (withhold-from-context, RQ2). Removing induces
  absence-hallucination the verifier can still **catch**; adding lets the model state a
  fact the verifier **cannot confirm**, so it does **not** repair the verdict.
- **generation + verification** — change the **real KG**, so grading uses the **edited**
  reference (edit-the-KG). Adding the missing date grounds c3 (gap-repair); removing
  **blinds** the verifier.

**The contrast in one move (the date gap):** the date claim (c3) is fabricated because the
KG holds no usable birth-date fact (a genuine gap). Add the pre-filled date (✚ add triplet):
- *generation+verification* → c3 flips to **retrieved**; **repair-leverage +1: c3**. → `screenshots/07-repair-loop.png`
- *generation only* → the date appears as a **green-dashed** (model-only, unverified) edge,
  but c3 stays **fabricated** ("unverifiable — the verifier's reference still lacks it") and
  **repair-leverage +0**. → `screenshots/08-edit-scope.png`

**Edit operations (all scoped):**
- **Add / remove a triplet.** Remove by tapping its **edge** (scope from the toggle); a
  generation-only removal leaves the edge **dashed + dimmed** ("withheld from the model,
  still in the verifier's reference"). Withheld base triples come back via **"+ re-add"**.
- **Add an entity** (label + **optional description**) → a new node.
- **Remove an entity's content** (description/image) from its **detail pane** (tap the
  node): clears only the node's content — the node and its triplets stay. Scoped too
  (generation-only = withheld from the model; generation+verification = removed from the KG).
- **Edits log + undo:** every edit is listed with its scope and a **✕** to undo it.
- **Repair-leverage** = the COUNT of claims that flip FABRICATED → grounded vs the original
  answer; the "grounded N/6 now" absolute is kept alongside.

> The graph encodes scope: solid = in both; **dashed-dim** = withheld from the model
> (still verifiable); **green-dashed** = model-only (unverifiable). Captions on the strip
> state: generation-only never changes the reference; generation+verification does.

## Withhold-from-context shift (Analytics, multi-run)
The multi-run **withhold** selector {full · content-withheld · knowledge-withheld} shows
the per-condition fabrication rate — the distribution **shift** without relabelling true
claims (grading stays against the full reference). In the mock: full ≈ 26% fabricated,
content-withheld a mild rise, knowledge-withheld ≈ 84% (structure withheld hurts most).

## Subgraph interactions (shared by both modes)
- **Multi-select → brush.** Click claim rows (or coloured answer spans). Each gets a
  numeric badge; the subgraph highlights each one's support path in its status hue with an
  accent ring on its anchor node. → `screenshots/03-multiselect-brush.png`
- **1st-degree neighbourhood under a node cap** (`config.SUBGRAPH_NODE_CAP` = 40); the
  Chopin graph is small, so all nodes show.
- **Tap a node → zoom + entity-detail** (bottom-middle): static placeholder image +
  label/description, and a **✕ remove this entity's content** button (scoped).
  → `screenshots/04-node-zoom-detail.png`
- **⟲ reset** clears all KG edits + selections and restores the overview (a full reset,
  not just the camera).
- In **multi-run** mode the node sizes / edge widths reflect **support-frequency**, and a
  click in the support list highlights the item on the graph (a bright orange node
  outline / thick orange edge — distinct from the blue claim-selection accent).

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
| `screenshots/01-overview.png` | Single-run mode: status %/counts (no SE), the scoped KG-edits strip below |
| `screenshots/05-multirun.png` | Multi-run: mean±SE distribution + small-N caveat + withhold shift + clickable support-frequency list; a selected triplet/node highlighted on the subgraph (which is sized by support-frequency) |
| `screenshots/03-multiselect-brush.png` | Multi-selected claims brushed onto the subgraph with badges + readable edge labels |
| `screenshots/04-node-zoom-detail.png` | Node tapped → zoom + entity-detail pane |
| `screenshots/06-generation-settings.png` | ⚙ generation-settings panel open (mock LLM params) |
| `screenshots/07-repair-loop.png` | Add the date *generation+verification* → date node added, c3 grounded, repair-leverage +1 (c3), grounded 5/6 → 6/6 |
| `screenshots/08-edit-scope.png` | Add the date *generation only* → green-dashed (model-only) edge, c3 still fabricated (unverifiable), "+0 repaired" — the scope contrast |

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
- **Scoped edits / grading:** a claim grounds iff its evidence is in BOTH the generation
  context AND the verification reference (`fixtures.apply_edits` / `statuses_with_reasons`).
  generation-only edits change only the generation view; generation+verification change
  both. The date is a GAP (absent from the base KG); only a generation+verification add
  repairs c3. **Repair-leverage** is measured vs the original answer, so the gap-repair
  reports **+1 repaired: c3** (and the generation-only add reports +0 — unverifiable).
- **Graph scope styling:** dashed-dim edge = withheld from the model (still in the
  reference); green-dashed edge = model-only (unverifiable); dashed node border = added
  entity / content-removed entity (`app/panels/subgraph.py` BASE_STYLESHEET).
