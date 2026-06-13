# Artwork non-redundancy gate — PRELIMINARY partial run

> STATUS: **PRELIMINARY / PARTIAL gate.** This run rigorously executes gate parts
> **(a)** "fact not entailed by any triple (incl. P180)" and **(b)** "fact not in the
> textual description", plus a **rough proxy** of part **(c)** "a VLM can read the fact
> from the image" (the proxy here is *this assistant* reading downscaled Commons JPEGs
> with the Read tool — NOT the project's target VLM). The real **(c)** check on the
> team's target VLM (Qwen2.5-VL-7B / Qwen3-VL via MLX on the 48 GB Mac) is **STILL
> PENDING** and remains a required pre-lock step. Run date: 2026-06-12. No git commit.

> SCOPE NOTE: this gate concerns **RELATIONAL / COMPOSITIONAL** facts (spatial layout,
> who-holds-what, who-is-seated, foreground/background, gesture/action *between* figures),
> NOT mere object presence. This is the distinction that separates this gate from the
> earlier 0-3 refutation of "P180 makes depicted facts redundant"
> (`2026-06-08-multimodal-deep-research.md`, claim re P180): that refutation was about
> *which objects are present*, which P180 does capture. P180 is a **bag of depicted
> entities** (+ a handful of abstract concepts); it does **not** encode the *relations
> or positions among* those entities. This gate tests precisely that residual.

---

## 1. Population

WDQS REST query (single COUNT, User-Agent `ivg-kg-research/1.0 (academic course
project)`, returned without timeout):

```sparql
SELECT (COUNT(DISTINCT ?p) AS ?cnt) WHERE {
  ?p wdt:P31 wd:Q3305213 ; wdt:P18 ?img ; wdt:P180 ?depicts ;
     wikibase:sitelinks ?sl .
  FILTER(?sl >= 5 && ?sl <= 40)
}
```

**Population = 4,184 paintings** (instance-of painting Q3305213, having BOTH P18 image
AND P180 depicts, sitelink count in the 5-40 band). This confirms the earlier scan
estimate of ~4,180. The band is large enough to support stratified sampling and an
offline-safe precomputed demo.

## 2. Sample

A single grouped WDQS query returned 40 such paintings with English label, English
`schema:description`, concatenated P180 depicted-entity labels, and the P18 Commons
`Special:FilePath` URL. From these, **10** were selected for the image audit, biased
toward multi-figure narrative scenes (where relational facts are most likely) but
deliberately including 2 landscapes and 1 Futurist work as adversarial "weak" cases.

**Salient population property (this is the headline finding for redundancy risk):**
across all 40 sampled rows, the Wikidata `description` is a **bare attribution stub** —
"painting by X", optionally "+ in the Louvre" / "+ at the Kunsthistorisches Museum".
**Not one** description in the band contained any compositional or relational content.
The 5-40 sitelink band mitigates the famous-work redundancy risk exactly as hoped: these
works are notable enough to be curated but not so famous as to attract a rich
Wikidata prose description. **Part (b) is therefore near-trivially satisfied for this
band** — the redundancy contest is essentially (a) "vs. the triples / P180" alone.

## 3. Non-redundancy audit (8-10 images read)

Images downloaded via `curl -L` from Commons `Special:FilePath`, downscaled to <=1400 px
with `sips`, read with the Read tool. For each painting I extracted 1-3 candidate
**relational/compositional** facts and classified each:

- **NON-REDUNDANT (NR):** the *relation/position* is absent from BOTH P180 and the
  description (P180 may list the participating entities, but not how they relate).
- **REDUNDANT (R):** the relation/action itself is named by a P180 value or the description.
- **PARTIAL (P):** P180 names the action/relation abstractly (e.g. "kiss", "cannibalism")
  so the *core* relation is redundant, but a more specific spatial residual remains NR.
  Scored as 0.5 for the rate.

| # | QID | Painting | Candidate relational fact (read from image) | P180 entities present | Relation in P180/desc? | Class |
|---|-----|----------|----------------------------------------------|----------------------|------------------------|-------|
| 1 | Q536094 | Democritus | Man points his **index finger down at** the globe, which sits on a stand on the table **to his right**; brown drape over left arm | man, globe, index finger, table | "index finger" is an entity; "points at globe" relation absent | **NR** |
| 2 | Q14940739 | St Sebastian Attended by St Irene | Sebastian lies **prone in the foreground**; arrow **piercing his torso**; Irene **kneels holding a torch aloft**; a woman **weeps into a cloth** at upper right | Saint Sebastian, arrow, torch, Irene, woman, tear | entities only; "arrow in his body", "kneeling", "torch held up", "weeping into cloth" absent | **NR** |
| 3 | Q1150997 | Saturn Devouring His Son | Saturn **grips a headless body in both hands and bites its left arm**; body held **head-downward** | Saturn, blood, human body, cannibalism, filicide | "cannibalism"/"filicide" name the act -> core relation REDUNDANT; the *grip + head-down posture* is a NR residual | **P (0.5)** |
| 4 | Q389198 | Three Musicians | **Boy holds out a wine glass**; **monkey perched behind the boy** at far left; center man **sings (mouth open)** while a man in yellow **plays the fiddle with a bow**; bread+cheese on table | boy, man, monkey, wine, glass, musical instrument | "smile"/"laughter" are entities; who-holds-glass, monkey-behind-boy, who-plays-what all absent | **NR** |
| 5 | Q603751 | The Peasant Wedding | **Two men carry a door-as-tray** of porridge bowls; **bride seated before green cloth** under a hung paper crown; **child eating from a bowl on the floor**, foreground-left; bagpiper gazes at the food | human, bagpipe, wedding (only 3 values) | description = "painting by Brueghel"; P180 has nothing relational. All compositional facts NR | **NR** |
| 6 | Q1195035 | The Kiss (Hayez) | Man **cradles woman's face**; woman **rests one foot on the bottom stair**; a **shadowy figure lurks in the left archway** | kiss, couple, hug, stairs, tread, man, woman | "kiss"/"hug"/"couple" name the act -> core REDUNDANT; foot-on-stair + lurking figure are NR residuals (lurker not in P180 at all) | **P (0.5)** |
| 7 | Q1247110 | Landscape with the Fall of Icarus | **Ploughman dominates foreground and works, ignoring** Icarus, whose **legs splash unnoticed in the lower-right corner**; galleon sails past | plough, horse, Icarus, free fall, ship, sheep | P180 lists "Icarus"+"free fall" as entities; the entire point — *Icarus tiny/peripheral while the ploughman ignores him* — is absent | **NR** |
| 8 | Q587514 | The City Rises (Boccioni) | **Several men strain to restrain a rearing red horse**; construction scaffolding behind | horse, man, building, wheelbarrow | entities only; the men-pulling-horse struggle relation absent | **NR** (but see (c) caveat: Futurist abstraction lowers VLM legibility) |
| 9 | Q3661546 | A Waterfall in a Rocky Landscape | **House sits atop the rocky outcrop above the falls**; **footbridge crosses above the cascade** | house, mountain, waterfall, footbridge, pine tree | P180 captures all objects; only spatial *above/atop* relations are residual, and they are weak/inferable | **P (0.5)** — weakest case |
| 10 | Q1025704 | Café Terrace at Night | **Patrons seated under the yellow awning**, **waiter standing among the tables**; **cobbled street recedes diagonally** with figures walking away | café, table, chair, lamp, star, night, tree | entities only; seated-under-awning, waiter-among-tables, diagonal-street layout absent | **NR** |

### Rate

Counting PARTIAL as 0.5 (the conservative scoring — it credits P180 for naming the
abstract action while still recognizing the spatial residual):

- Full NON-REDUNDANT: #1, #2, #4, #5, #7, #8, #10 = **7**
- PARTIAL (0.5): #3, #6, #9 = **3 x 0.5 = 1.5**
- REDUNDANT: **0**

**Non-redundancy rate = (7 + 1.5) / 10 = 0.85 (85%).**

Bounds for honesty:
- **Strict** (PARTIAL counted as redundant): 7/10 = **70%**.
- **Lenient** (PARTIAL counted as non-redundant, since a spatial residual does survive):
  10/10 = **100%**.
- Reported headline: **~85% (range 70-100% depending on how the 3 partials are scored).**

This sits **above** the de-risked taxa range-map floor (~62% non-redundant, already
verified) — i.e. on parts (a)+(b) the artwork-relational modality looks at least as
non-redundant as the verified fallback, and the band kills the description-redundancy risk.

## 4. Caveats (honest)

1. **Small sample (n=10 read, n=40 fetched, N=4,184).** No confidence interval is
   meaningful at this size; treat 85% as a point estimate with wide uncertainty. The
   full pre-registered run needs a larger stratified sample.
2. **Selection toward narrative scenes.** I deliberately over-sampled multi-figure works
   where relational facts are dense, and the rate would be lower on a pure-landscape /
   still-life stratum (case #9 is the canary: landscapes degrade to object-position
   relations that P180's object list nearly covers). The full run must **stratify by
   genre** (history/genre/portrait vs. landscape/still-life) and report per-stratum rates.
3. **Description-redundancy risk is the main theoretical threat, and the 5-40 band
   mitigates it well** — every description in the band was a bare attribution stub with
   zero compositional content. The risk would be real for famous works (sitelinks > 40),
   which is exactly the stratum the band excludes. This is the strongest part of the result.
4. **P180 partial-coverage of *actions*.** P180 occasionally encodes the abstract action
   ("kiss", "cannibalism", "wedding", "free fall"), which makes the *core* relation
   redundant (cases #3, #6). The genuinely safe non-redundant facts are **fine-grained
   spatial/gestural** ones (who-holds-what, foreground/background, who-is-seated,
   gaze direction), not the headline action. The fact-generation step in the real
   pipeline must target that fine-grained layer, or P180 will eat the easy facts.
5. **(c) is only a ROUGH PROXY here.** I read downscaled JPEGs with a frontier
   multimodal model (the Read tool), not the project's target VLM. Two consequences:
   (i) the **target-VLM reading reliability on this corpus is NOT verified** — a 7B MLX
   VLM will read these scenes less reliably than this proxy, especially the Futurist /
   abstract work (#8), dark tenebrist scenes (#2), and fine spatial relations; (ii) the
   POPE-style fixed-template binary probe planned as the image analogue of the MiniCheck
   gate has **not** been exercised. The real (c) must run on the 48 GB box before locking.
6. **No independent label / verifier yet.** The redundancy classification here is the
   assistant's own reading vs. the live P180 + description. The pre-registered gate
   requires an independent KG-grounded label and a deterministic verifier; this run does
   not provide that.

## 5. Verdict

**(i) Artwork-relational looks LOCKABLE pending the local-VLM (c)-check.**

On the two parts this environment can test rigorously:
- **(a) not-entailed-by-triples:** P180 is a bag of depicted *entities* + a few abstract
  actions; it does **not** encode relations/positions. 7/10 fully non-redundant, 3/10
  partial, 0/10 redundant.
- **(b) not-in-description:** the 5-40 sitelink band yields attribution-stub descriptions
  with **zero** compositional content — part (b) is essentially free in this band.

Estimated non-redundancy rate **~85% (70-100% by scoring convention)**, **above the
verified ~62% taxa floor**. Redundancy / description-coverage does **not** look like a
fatal problem for this band, *provided* the fact-generation step targets fine-grained
spatial/gestural relations rather than the abstract actions P180 sometimes names.

**This is NOT a green light to lock.** Two gates remain before the rich-multimodal claim
is safe:
1. **Run the real part (c)** on the target VLM (Qwen2.5-VL-7B / Qwen3-VL via MLX, 48 GB
   Mac) with the POPE-style fixed-template binary probe, on this exact corpus. The proxy
   here over-states legibility relative to a 7B model.
2. **Stratify by genre** in a larger pre-registered sample; report per-stratum rates so
   the landscape/still-life degradation (case #9) is quantified, not hidden by the
   narrative-scene over-sampling here.

If the local-VLM (c)-check holds up, artwork-relational is a genuinely non-redundant,
fact-bearing image modality and can headline the multimodal axis with taxa range-maps as
the verified floor. If the 7B VLM cannot reliably read the fine spatial relations (the
real risk, since that is precisely the non-redundant layer), **fall back to the verified
taxa floor** and treat artwork as a stretch domain.

---

### Reproducibility appendix

- WDQS endpoint: `GET https://query.wikidata.org/sparql?format=json` with
  `User-Agent: ivg-kg-research/1.0 (academic course project)`.
- Population query: as in 1 above (returned 4184, no timeout).
- Sample query: grouped SELECT over P31=Q3305213 + P18 + P180 + sitelinks 5-40, English
  label/description/depicts labels, LIMIT 40.
- Images: Commons `Special:FilePath` URLs, `curl -L`, downscaled with `sips -Z 1400`.
- 10 QIDs audited: Q536094, Q14940739, Q1150997, Q389198, Q603751, Q1195035, Q1247110,
  Q587514, Q3661546, Q1025704.
