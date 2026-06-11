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
- **Two interactive demos** on the KG-edits strip: **REMOVE** evidence from the
  generation context → re-run → the affected claim fabricates (qualitative RQ2); **ADD**
  a missing true fact to the KG → re-run → it flips to grounded (repair). See below.

**MULTI-RUN mode** — re-run the query **N times** (N selectable, **default 20**) under the
**FULL condition** (no condition selector).
- **(a) Status distribution = mean ± SE** of the per-run answer-level fraction of claims
  in each grade — the **reproducibility of grounding** on this question. The error bars
  are the **SE of a proportion** `sqrt(p(1-p)/N)` — *not* the ~0.5 Bernoulli per-draw
  std. A **prominent small-N caveat** states *"N=20 is a floor; small differences are
  within noise."* → `screenshots/05-multirun.png`
- **(b) Support-frequency** — for each KG **node** and each **triplet**, the fraction of
  the N runs in which it was **used** to ground a claim (it lies on the support path of
  ≥1 grounded claim that run). Surfaced as **node-size / edge-weight on the subgraph**
  plus a **ranked list**. It is **observational importance** ("how often grounding routes
  through this item") — explicitly **NOT** causal leverage.
- **Select KG items → highlight in the graph.** Click a row in the support-frequency
  list (a ● node or ◆ triplet); it is highlighted on the subgraph with an accent
  outline / thick accent edge — the same brush behaviour as selecting claims.
  → `screenshots/05-multirun.png`

There is **no condition selector** in multi-run: it shows only the FULL-condition
distribution (the reproducibility of grounding on this question). The
content-vs-knowledge RQ2 contrast is an **offline aggregate** over the question bank
(SPEC §8), not an interactive per-question toggle.

## KG editing — two operations (the bottom KG EDITS strip)
The perturbation surface is exactly **two operations**; there is **no scope toggle** and
**no generation-only add**. Scope is fixed by the operation:

- **REMOVE** (a triplet or an entity's description) → withholds it from the model's
  **generation context** only. The verifier / grading reference is **always full and is
  never ablated**, so the claim fabricates only if the model actually couldn't recover it
  — the qualitative **RQ2** demo ("does the model NEED this evidence?"). The removed edge
  shows **dashed + dimmed** ("withheld from the model, still in the verifier's reference").
- **ADD** (a true missing fact: a triplet or an entity) → adds it to the **KG** (both the
  generation context and the grading reference). This **repairs**.

**The two single-run demos (on this one answer):**
- **(a) REMOVE demo (RQ2):** tap a triplet's edge → **✕ remove from the generation
  context** (or remove an entity's description in its detail pane) → the affected claim
  **fabricates** (e.g. remove `father (P22)` → c1 and the France-via-father path flip to
  Fabricated). Withheld base triples come back via **"+ re-add"**.
- **(b) ADD demo (RQ3 / gap-repair):** the date claim (c3) is fabricated because the KG
  has **no usable birth-date fact** (a genuine gap). Add the pre-filled date (**✚ add
  triplet**) → c3 flips to **retrieved** and **repair-leverage +1 (c3)**, grounded 5/6 → 6/6.
  → `screenshots/07-repair-loop.png`

Also: **add an entity** (label + optional description → a new node); the **edits log**
lists each op (e.g. "remove ... [from generation context]", "add ... [to KG]") with a **✕**
to undo it.

> The graph encodes the edit: solid = present; **dashed-dim** = withheld from the model
> (a REMOVE — still in the verifier's reference, never ablated). REMOVE never changes the
> reference; ADD does.

## Subgraph interactions (shared by both modes)
- **Multi-select → brush.** Click claim rows (or coloured answer spans). Each gets a
  numeric badge; the subgraph highlights each one's support path in its status hue with an
  accent ring on its anchor node. → `screenshots/03-multiselect-brush.png`
- **1st-degree neighbourhood under a node cap** (`config.SUBGRAPH_NODE_CAP` = 40); the
  Chopin graph is small, so all nodes show.
- **Tap a node → zoom + entity-detail** (bottom-middle): static placeholder image +
  label/description, and a **✕ remove this entity's content** button (withholds the
  description from the generation context). → `screenshots/04-node-zoom-detail.png`
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
| `screenshots/01-overview.png` | Single-run mode: status %/counts (no SE), the KG-edits strip below |
| `screenshots/05-multirun.png` | Multi-run: FULL-condition mean±SE distribution + small-N caveat + clickable support-frequency list; a selected triplet/node highlighted on the subgraph (which is sized by support-frequency). No condition selector. |
| `screenshots/03-multiselect-brush.png` | Multi-selected claims brushed onto the subgraph with badges + readable edge labels |
| `screenshots/04-node-zoom-detail.png` | Node tapped → zoom + entity-detail pane |
| `screenshots/06-generation-settings.png` | ⚙ generation-settings panel open (mock LLM params) |
| `screenshots/07-repair-loop.png` | ADD the date to the KG → date node added, c3 grounded, repair-leverage +1 (c3), grounded 5/6 → 6/6 |

## Authored design details (where the spec left them open)
- **Node cap:** `SUBGRAPH_NODE_CAP = 40` (`src/ivg_kg/config.py`).
- **Status palette (hex):** Retrieved `#8fd9a8`, Supportable `#f2d08a`, Fabricated
  `#f4a6c0`; claim selection-outline accent `#58a6ff`; KG-item selection `#ff9d4d`
  (`app/theme.py`).
- **Spurious-path reason (c5):** *"relation/value illegitimacy: the path reaches France
  via the father's place of birth (P22→P19→P17), not the subject's own birthplace (P19) —
  Chopin was born in Żelazowa Wola, Poland."*
- **N choices:** {5, 10, 20}, default 20. FULL-condition per-fact run outcomes
  (`_OUTCOME_COUNTS` in `fixtures.py`: ok / fab / absent counts over 20 runs) drive the
  multi-run distribution; grounded claims carry support paths so support-frequency
  aggregates over stable KG-item IDs (`diagnostics.aggregate_runset`). The
  content-vs-knowledge RQ2 contrast is computed offline over the bank (SPEC §8), not here.
- **Support-frequency** is observational: node size scales 40→96 px and edge width
  1.5→8.5 with the fraction of runs the item grounded a claim (`app/panels/subgraph.py`).
- **Two operations / grading:** a claim grounds iff its evidence is in BOTH the generation
  context AND the verification reference (`fixtures.apply_edits` / `statuses_with_reasons`).
  REMOVE withholds from the generation context only (the reference is never ablated);
  ADD adds to the KG (both). The date is a GAP (absent from the base KG); ADDing it repairs
  c3, so **repair-leverage = +1 (c3)** vs the original answer.
- **Graph styling:** a REMOVE leaves the edge dashed + dimmed (withheld from the model,
  still in the reference); a dashed node border = added entity / content-removed entity
  (`app/panels/subgraph.py` BASE_STYLESHEET).
