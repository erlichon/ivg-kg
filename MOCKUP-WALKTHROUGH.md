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
4. **Click a claim → per-claim analytics.** Each selected claim gets its own collapsible
   card under PER-CLAIM (closed by default); expand any card for that claim's diagnostics.
   Selecting several shows several cards. → `screenshots/02-fabricated-claim-perclaim.png`
5. **Full-answer analytics + N selector.** Top-right: the **claim-status distribution**
   (mean ± std error bars) + the **fabrication rate**, computed over **N verifier runs**
   (the answer is generated once; the verifier runs N times — the spread is *verifier*
   variance). Switch **verifier runs (N) = 5 / 10 / 20** — the distribution shifts. → `01-overview`
6. **Per-claim stacked-bar + stability + spurious chip.** Expand a claim's card: a
   **per-condition stacked bar** (full / knowledge-absent / content-absent, stacked by
   {Retrieved, Supportable, Fabricated, Absent}), the **stability** scalar, the RQ2
   absence-leverage / fabrication-induction readouts, and — on Supportable claims only —
   a **⚠ "path suspect"** chip + reason. Every score has a click-to-open **ⓘ** with its
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

## Repair loop — KG injection / restore (SPEC-text §4.6, RQ3 + CogMG)
The defining interaction, in the full-width strip at the bottom (**Overview →
Inspection → Repair → Overview**):
- Pick a **condition** (full / knowledge-absent / content-absent). Under
  **knowledge-absent** the dependent claims fabricate (absence-induced hallucination).
- Each withheld triple is a card: **↺ restore** (RQ3 — re-add to the *generation
  context*, regenerate, re-ground) or **✚ inject** (CogMG — add a genuinely-missing
  triple to the *KG-full reference*). Click one → the dependent claim(s) flip
  fabricated → grounded and the **repair-leverage** (+N claims re-grounded) updates.
- e.g. *restore* `place of birth (P19)` grounds "born in Marainville"; *inject*
  `date of birth (P569) = 15 April 1771` corrects the fabricated "17 June". →
  `screenshots/07-repair-loop.png`

## Reading aids
- **Variance model:** the answer is generated **once**; the **verifier** runs **N** times
  over its claims. So the distribution / stability / fabrication-rate spread is *verifier*
  variance (cross-condition contrasts like absence-leverage instead need one generation
  per condition — noted in their ⓘ).
- **Mean ± std error bars** on the distribution: bar = mean per-run fraction over the N
  verifier runs, whisker = ±1 std.
- **ⓘ info indicators** next to every score — **click** to open a persistent note with the
  definition + formula (stability spells out H, status, FULL, K; absence-leverage explains
  it needs a generation per condition; Trust explains the gold-set error measurement).
- **Pastel 3-grade palette** (hue = status), identical in every panel; selected claims are
  told apart by an outline + numeric badge, never by hue.

## Screenshots
| file | shows |
| --- | --- |
| `screenshots/01-overview.png` | Overview (#8), merged answer column, full-answer analytics with error bars + ⓘ (#5), header controls, Trust strip |
| `screenshots/02-fabricated-claim-perclaim.png` | Fabricated claim selected → per-claim stacked bar + leverage readouts (#4/#6) |
| `screenshots/03-multiselect-brush.png` | Three claims multi-selected, brushed onto the subgraph with badges + readable edge labels (#2) |
| `screenshots/04-node-zoom-detail.png` | Node tapped → zoom + entity-detail pane (#7) |
| `screenshots/06-generation-settings.png` | ⚙ generation-settings panel open (mock LLM params) |
| `screenshots/07-repair-loop.png` | Repair loop: knowledge-absent → restore P19 + inject P569 → claims re-ground, leverage +2 |

## Authored design details (where the spec left them open)
- **Node cap:** `SUBGRAPH_NODE_CAP = 40` (`src/ivg_kg/config.py`).
- **Status palette (hex):** Retrieved `#3fb950`, Supportable `#d29922`, Fabricated
  `#f7508d`; `Absent` (stacked-bar 4th segment) `#6e7681`; selection-outline accent
  `#58a6ff` (`app/theme.py`).
- **Spurious-path reason (c5):** *"relation/value illegitimacy: the path reaches France
  via the father's place of birth (P22→P19→P17), not the subject's own birthplace (P19) —
  Chopin was born in Żelazowa Wola, Poland."*
- **N choices:** {5, 10, 20}, default 20; per-claim draw distributions hand-authored in
  `fixtures.py` (`_DRAW_COUNTS`), aggregated by `src/ivg_kg/diagnostics.py` (§4.8).
