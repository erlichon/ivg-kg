# Course Distillation -- Multimedia Analytics 2025/26

Organized for the ivg-kg project. Each item tagged with source and implication.
All section refs (e.g. "p.89") refer to slide page numbers in pdftotext output.

---

## 1. The MMA Model / Framework

### 1.1 Canonical model name and citation

**"Multimedia and Visual Analytics in the Agentic Era"**
Worring, Zahalka, van den Elzen, Fischer, Keim. arXiv:2504.08138 (revised 2026).
In-course citation: [Worring2026]. See `MMA-MODEL.md` for full extraction.

The model is the course's **central theoretical framework**. Projects are expected to position their design within it.

Source: `1-introduction.pdf` p.89 ("The full model") and `MMA_model_BNI_arXiv_version.pdf`.

**Implication for ivg-kg**: The intermediate report REQUIRES "a simplified version of the main figure in the foundation model multimedia analytics paper" as the structural template for the system's interaction design figure. The figure must show how ivg-kg maps onto the model's zones (FM-based AI, Human-AI Teaming, Human Understanding).

### 1.2 The three zones and what ivg-kg maps to

| Zone | MMA model component | ivg-kg mapping |
|------|---------------------|----------------|
| Foundation model-based AI | FM + RAG agents + Expert modules | LLM/VLM answering from KG context; Wikidata KG as expert module; grounding backend as RAG-like |
| Human-AI Teaming / VA Agents | Action-specific agents (Query, Analysis); Strategy loop; Coordinator | The perturbation + grounding pipeline; claim classifier as Analysis agent; repair loop as strategy |
| Human Understanding / User Interface | Four UI pillars (Outputs/Process/Knowledge/Trust); Guidance and Trust loop | Three panels: Answer (Outputs), Subgraph (Knowledge), Analytics (Process+Trust) |

Source: `MMA_model_BNI_arXiv_version.pdf` Sections 4-6; `1-introduction.pdf` p.83-86.

**Implication for ivg-kg**: The analytics panel's Trust pillar (explanations, confidence, performance) is where the classifier error rates and repair leverage belong. The provenance of grounding paths (which evidence supported which claim) directly satisfies the Knowledge/Provenance sub-pillar. These mappings should be explicit in the intermediate report.

### 1.3 The four VA actions (Munzner 2015 extended for FMs)

In VA: Query, Analyze, Search, Generate.
For FMs extended to: Discover (hypothesis gen), Present (personalized output), Annotate (semi-automatic), Derive (new abstractions), and Search/Query now handled more directly by FMs.

Source: `1-introduction.pdf` p.67-70.

**Implication for ivg-kg**: ivg-kg's three panels cover the Query action (user asks about a claim) and Analyze action (grounding, repair leverage). Generation is also exercised in the repair loop. The scientific paper contribution list should align to these four action categories.

### 1.4 Design criteria for the MMA model and where ivg-kg stands

| Criterion | ivg-kg current coverage | Gap / risk |
|-----------|------------------------|------------|
| D1 Consistency: align with established VA models | Cites Pirolli-Card (sensemaking) and Brehmer-Munzner (task typology). | Should also explicitly reference the Sacha 2014 Knowledge Generation Model (the course's cognitive cycle) and connect the repair loop to it. |
| D2 AI Functionality: adapt to FMs | Uses LLM/VLM for generation; RAG-like context assembly. | OK. |
| D3 AI Limitations: address hallucinations via HAIT | The entire project is about hallucination detection and repair. | Strong alignment -- this is the project's core. State explicitly in the paper. |
| D4 Visualization: concise, complete, understandable, truthful | Three coordinated panels, colour-coded claims, path highlighting. | Need to verify each UI element maps to a clear user need; "truthfulness" means not misleading -- classifier error rates must be visible (currently in GroundingRun.error_rates but needs a UI display). |
| D5 Interaction Channels: seamless, timeliness, data/knowledge flow | Coordinated dcc.Store; live repair call; precomputed store for demo safety. | The "timeliness" aspect (user waiting for repair regeneration) should be addressed -- progress indicator during the live repair call. |
| D6 Shift in Analytical Reasoning: provenance, attribution | Per-claim support_source; active_perturbations; repair leverage log. | Good alignment. Add explicit provenance visualization in the Analytics panel -- a session history of repairs and their attribution. |

Source: `MMA_model_BNI_arXiv_version.pdf` Sections 3, 6; `1-introduction.pdf` p.49-63.

### 1.5 Human Understanding: the Knowledge Generation cycle

Expert users: hypothesis -> tasks (actions) -> findings -> insights -> knowledge (externalized).
"Findings are local observations tied to particular data and views; insights represent more coherent and generalized conclusions."

Source: `MMA_model_BNI_arXiv_version.pdf` Section 5.1; also `1-introduction.pdf` p.27-29.

**Implication for ivg-kg**: The project's sensemaking narrative (Pirolli-Card cited in project_statement.md) should be cross-mapped to the Knowledge Generation Model as well, since the course uses both. The repair loop is explicitly a "knowledge generation" cycle: the analyst generates new knowledge (the repaired triple/content) and externalizes it back into the KG.

---

## 2. Visualization and Projection Design Principles

### 2.1 Core visualization principles from lecture 2

| Principle | Source | Implication for ivg-kg |
|-----------|--------|----------------------|
| Bar charts MUST start at y=0 | `2-visualization.pdf` p.10 | Analytics panel bar/histogram for claim-status distributions must start at 0. Grader will notice if not. |
| Scatter plot: for projection-based viz, x and y axes must have same dimension | `2-visualization.pdf` p.12 | If a projection panel is added, both axes must be the same reduced dimension (not two different features). |
| Bubble chart: use area not diameter for size encoding | `2-visualization.pdf` p.13 | If node size encodes a quantity in the subgraph, use area. |
| Heatmap: choose row/column order carefully; don't use rainbow color scale | `2-visualization.pdf` p.15 | Any heatmap (e.g., claim-status by entity) needs principled ordering and a perceptually valid palette. |
| Glyphs: only valuable when designed properly with the 7 desirable characteristics | `2-visualization.pdf` p.21-27 | If glyphs are used on nodes to encode multiple variables, they must satisfy typedness, visual orderability, channel capacity, separability, searchability, learnability, attention balance. |
| Graph layouts: use task-appropriate aesthetics (Kamada-Kawai, Fruchterman-Reingold) | `2-visualization.pdf` p.67-68 | The subgraph panel's force-directed layout (dash-cytoscape default) is defensible; should mention the aesthetic criterion used. |
| Multimodal visualization: four strategies (semantic fusion, visual integration, visual juxtaposition, cross-view linking) | `2-visualization.pdf` p.52-57 | ivg-kg uses cross-view linking (clicking a claim links to the subgraph panel). Should name this explicitly in the paper. The three-panel design with coordinated selection is "cross-view linking" in the Wang 2025 taxonomy. |
| Progressive visualization: meaningful partial results with quality measures | `2-visualization.pdf` p.90-91; `MMA_model_BNI_arXiv_version.pdf` Section 5.2 | The repair loop could show intermediate status as claims are re-graded. Relevant to the demo's "technical complexity" rubric criterion. |

### 2.2 Graph visualization specifically

The course devotes substantial time to graph visualization, directly relevant to the subgraph panel.

- Node-link vs adjacency matrix: choice depends on task. Node-link is standard for exploration; adjacency matrix for pattern detection in typed/weighted graphs.
- For KG subgraphs: node-link with force-directed layout is standard and justified.
- Hypergraph visualization (the course covers this): not relevant for ivg-kg.
- Pattern repository / explainer (Shu 2025): interactive pattern explanation for network visualizations. Relevant inspiration for the subgraph panel.

Source: `2-visualization.pdf` p.59-78.

**Implication for ivg-kg**: The paper should justify the node-link choice for the subgraph panel explicitly in terms of the user task (path exploration, not pattern statistics). The path-highlighting approach (stylesheet selectors in dash-cytoscape) should be described as a task-driven aesthetic criterion.

### 2.3 Projections / dimensionality reduction

The course teaches PCA, t-SNE, UMAP, TriMap, PaCMAP in depth (lecture 3), with evaluation metrics (trustworthiness, continuity, normalized stress, neighborhood hit, Shepard diagram).

**UMAP is the current recommended method** (t-SNE is "standard of the past decade").

Key warnings:
- Cluster sizes in UMAP mean nothing
- Distance between clusters may not be meaningful
- Hyperparameters matter greatly; try multiple settings
- Must preserve aspect ratio
- Always use the same dimension for both axes

Source: `3-projections.pdf` throughout.

**Implication for ivg-kg -- FLAG**: **ivg-kg currently has NO projection / dimensionality reduction component.** The course dedicates an entire lecture to projections and positions them as a core MMA technique ("Projections of Latent Spaces" -- lecture 3). The demo rubric rewards **technical complexity** and going beyond off-the-shelf components. Adding a UMAP projection of claim embeddings (colored by grounding status) or entity embeddings (colored by coverage/hallucination rate) would address this gap and score on the "advanced connection between visualization and model" criterion. This is the single most technically addressable gap between current ivg-kg and what the course rewards.

### 2.4 Glyph-projection hybrid

The course explicitly teaches combining dimensionality reduction with glyph encoding for remaining dimensions (Kammer 2020 Glyphboard approach: project to 2D, encode selected variables as shape/color/glyph).

Source: `3-projections.pdf` p.95-97.

**Implication for ivg-kg**: A claim-embedding UMAP projection where each point is a claim glyph colored by status (retrieved/reasoned-supportable/fabricated) and shaped by perturbation type would satisfy both the projection lecture AND go beyond off-the-shelf components in the demo rubric.

---

## 3. Evaluation Methodology

### 3.1 Evaluation approaches taught (from the lecture references cited in assignment instructions)

The course references the following evaluation approaches (cross-referenced from assignment instructions + model paper + intro):

| Approach | Description | Applicability to ivg-kg |
|----------|-------------|------------------------|
| Insight-based evaluation (North 2006) | Measures insight as deep, complex, qualitative, relevant, unexpected; not accuracy | Primary framework for ivg-kg evaluation (the project IS about insight into LLM grounding) |
| Analytic Quality / simulated actors (Zahalka 2015) | Simulates user evaluation runs; measures performance + efficiency | Referenced in intermediate report instructions as explicit option ("analytic quality based approach using simulated actors") |
| User task analysis (Pike 2009 "science of interaction") | High-level and low-level interaction taxonomy | MANDATORY -- the intermediate report explicitly requires following this paper |
| Quantitative UI metrics (NASA-TLX, task completion time, error rate) | Standard HCI evaluation | Mentioned in model paper Section 7; optional for project scope |
| Benchmark-driven (accuracy-based) | Not appropriate for MMA goals | Explicitly rejected by the course ("the users don't care if accuracy is 85.4 or 86.1%", intro p.24) |

Source: `MMA_model_BNI_arXiv_version.pdf` Section 7; `1-introduction.pdf` p.24-29; assignment instruction files.

### 3.2 What the scientific report rubric says about evaluation

"Has the method been evaluated following one of the techniques described in the lectures? OR if that was not feasible is there a clear description how future work could best evaluate the tool?"

This is an explicit escape hatch -- a clear description of future evaluation is acceptable.

**Implication for ivg-kg**: The project's current evaluation design (analytic/simulated primary + qualitative walkthroughs) is well-aligned. The project_statement.md already states "a full user study is stated as future work -- standard and defensible for a VIS short-paper scope." This is the correct framing. Explicitly label the quantitative claim-status distributions as "analytic quality" evaluation in Zahalka 2015 terms.

### 3.3 The "insight" definition as evaluation frame

North (2006) characteristics: complex (involves all data synergistically), deep (accumulates over time), qualitative (uncertain/subjective), relevant (domain knowledge connected), unexpected (serendipitous).

From Law 2020 interview study: actionable, interconnecting, unexpected, confirmatory, spontaneous, collaboratively refined, trustworthy.

**Implication for ivg-kg**: The repair loop's role in generating insights (the analyst discovers a fabrication, repairs it, and gains new knowledge about LLM behavior) should be explicitly framed using North's insight characteristics in the scientific paper. This directly satisfies the "Motivation and Relevance" rubric criterion for both intermediate and final reports.

---

## 4. Deliverable Requirements and Grading Rubrics

See `DELIVERABLE-RUBRICS.md` for the exact extractions.

Summary of the most grading-critical items:

### 4.1 Intermediate report (20%) -- three near-term risks

1. **Interaction design figure is mandatory and MUST reference the MMA model figure.** The instruction says: "A simplified version of the main figure in the foundation model multimedia analytics paper... could be a good starting point." This is a strong hint that the grader will look for this.
2. **Pike 2009 "science of interaction" paper is explicitly required** as the framing for the interaction design section. The project_statement.md cites Brehmer-Munzner task typology but NOT Pike 2009. Add the Pike framework to the interaction design.
3. **Three contributions as a bullet list** in the Introduction is a format requirement. These must match the final paper's contribution list.

### 4.2 Demo (30%) -- the feedback loop is the core

The rubric explicitly states: "The feedback loop between visualization, the model, and the relation with the users and their interaction is the core of visual analytics." This is verbatim from the demo instructions. The repair loop IS this feedback loop -- make this explicit in the demo video narration.

Also: "Functionality: Don't overwhelm the users with visualizations that may look nice but aren't focused on solving the problem at hand." The three-panel design with focused interactions is well-aligned; do not add extraneous panels.

### 4.3 Scientific report (50%) -- the highest-stakes deliverable

Equal weighting: Writing/presentation, Complexity, Implementation, Scientific excellence.

The "Complexity" criterion is explicitly about problem difficulty + solution adequacy. ivg-kg's three-way classification (retrieved/reasoned-supportable/fabricated) and the content/structure non-redundancy design are genuine complexity; make sure this is communicated.

"Implementation" requires "motivated choices for components and their interaction rather than specific details." The paper should not describe the code in detail; it should explain WHY dash-cytoscape was chosen over alternatives, WHY the three-panel coordination pattern was used, etc.

---

## 5. Gaps and Risks

### 5.1 The projection gap (HIGH priority)

**Finding**: The course dedicates an entire lecture to projections (UMAP, t-SNE, PaCMAP) and positions them as a core visualization technique for latent spaces. ivg-kg has NO projection component. The demo rubric rewards "advanced connection between visualization and the model" and going "beyond off-the-shelf components."

**Recommendation**: Add a fourth mini-panel (or a tab in the analytics panel) showing a UMAP projection of claim embeddings colored by grounding status. Each point = one claim; color = retrieved/reasoned-supportable/fabricated; interactive: click a point to navigate to that claim in the answer panel. This would:
- Satisfy the projections lecture requirement
- Score on "technical complexity" in the demo rubric
- Give a dataset-level view (not just per-question) for the analytics panel
- Be implementable with the existing schema (ClaimRecord has all needed attributes)

Implementation note: embed claims using a sentence transformer; project with UMAP; color by status. This is a post-M-BOOKS addition with no dependency on the critical path.

### 5.2 The Pike 2009 "science of interaction" reference (MEDIUM priority)

**Finding**: The intermediate report instructions explicitly require the interaction design section to follow "the 'science of interaction' paper" (Pike 2009). The project_statement.md uses Brehmer-Munzner (task typology, mentioned in passing) but does NOT mention Pike 2009. The intermediate report will be graded on this.

**Recommendation**: Map ivg-kg's interactions to Pike 2009's taxonomy. Pike's categories include: select, explore, reconfigure, encode, abstract/elaborate, filter, connect. The repair loop covers "connect" (link claim to evidence), "explore" (traverse the subgraph), "abstract/elaborate" (zoom in on a claim's support path), "filter" (filter by perturbation condition).

### 5.3 The MMA model figure in the interaction design (MEDIUM priority)

**Finding**: The intermediate report requires "a simplified version of the main figure in the foundation model multimedia analytics paper" as a starting point for the interaction design figure. No such figure exists in the current project docs.

**Recommendation**: Create a simplified Figure 1 variant where the left zone (FM-based AI) is "Wikidata KG + LLM/VLM," the middle zone (Human-AI Teaming) is "Grounding Pipeline + Perturbation Interface + Repair Loop," and the right zone (Human Understanding) is "Three Panels + Analyst." Show the data flow arrows explicitly.

### 5.4 The Knowledge Generation Model connection (LOW priority)

**Finding**: The course's core cognitive model is Sacha 2014 (Knowledge Generation Model), which the intro lecture calls "a comprehensive VA model integrating several, previously isolated, models." The project_statement.md cites Pirolli-Card sensemaking but not Sacha 2014. For the scientific paper, connecting to Sacha 2014 would show broader awareness of the course's theoretical framework.

**Recommendation**: In the related work and evaluation sections, map the repair loop to the Sacha 2014 knowledge generation cycle: hypothesis (analyst spots fabrication) -> task (repair action) -> finding (repair changes claim status) -> insight (analyst learns which KG gaps cause fabrication) -> externalized knowledge (the repaired triple).

### 5.5 Progressive visualization (LOW priority / nice-to-have)

**Finding**: The course covers progressive visualization (Ulmer 2024) as important for agentic parallel workflows (Visualization lecture p.90-91; model paper Section 5.2 UI pillars). The repair loop makes a live LLM call; showing intermediate progress (partial re-grading as claims resolve) would align with this principle.

**Recommendation**: Add a simple progress bar or claim-status counter that updates as claims are re-graded during repair, rather than waiting for all to complete. Low implementation cost; high alignment with course material.

### 5.6 Trust / explainability visibility (MEDIUM priority)

**Finding**: The MMA model's Trust pillar (Explanations, Confidence, Performance) is a mandatory UI component. D4 (Visualization) explicitly requires "truthful" information. The project has `GroundingRun.error_rates` stored but no UI element showing the classifier's per-modality error rate to the user.

**Recommendation**: Add a small always-visible confidence/error indicator in the Analytics panel showing the current classifier error rates (text-NLI gate, structure-path gate). Label it clearly. This directly satisfies the Trust pillar and D4 (truthfulness).

### 5.7 "Multimedia Analytics for AI" positioning (LOW priority -- already done)

**Finding**: The course's "Lecture 6: Multimedia Analytics for AI" framing -- "targeting the AI developer: A multimedia analytics solution where a user can interactively explore a complex AI architecture, its data and results to get a better understanding of its inner working and/or optimize its performance" -- exactly matches ivg-kg.

The project already identifies this framing. The scientific paper should use this verbatim as the positioning statement, since the grader (Worring) wrote this framing.

Source: `1-introduction.pdf` p.96.

---

## Appendix: lecture slide reference index

| Source | Key content extracted |
|--------|----------------------|
| `1-introduction.pdf` p.2-106 | Course overview, MMA definition, multimedia item model (content/annotations/metadata/features/similarity/statistics), insight definition (North/Law), history of VA models, FM limitations (RICE), 6 design criteria, full MMA model overview, course grading (p.102), project organization |
| `2-visualization.pdf` p.2-95 | Basic viz, bar chart rules, scatter/bubble, heatmap, Sankey, glyphs (7 criteria), multimedia viz taxonomy, multimodal viz 4 strategies (Wang 2025), graph viz (node-link/adjacency), force-directed layouts, hypergraph viz, progressive viz |
| `3-projections.pdf` p.2-100 | PCA, MDS, ISOMAP, SNE, t-SNE, UMAP (+ advanced: unseen data, inverse, aligned, non-Euclidean), TriMap, PaCMAP, evaluation metrics (trustworthiness/continuity/stress/neighborhood hit/Shepard), glyph+projection hybrid |
| `MMA_model_BNI_arXiv_version.pdf` p.1-18+A | Full model (6 criteria, 3 zones, 4 FM agent types, prompt templates, knowledge generation, UI 4 pillars, VA agents, coordinator, strategy loop, guidance+trust loop, evaluation discussion, 5 use cases) |
| `Workshop-1.pdf` | Plotly/Dash tutorial (Dash architecture, callbacks, stateless vs stateful, Snellius GPU access) |
| Intermediate report instructions | 8 mandatory sections, 4 grading criteria, format: IEEE VIS 3-4pp excl. refs |
| Demo instructions | 4 equal-weight grading criteria, GitHub required, 5-min screen recording required |
| Scientific report instructions | 4 equal-weight grading criteria, 4 IEEE VIS areas, GitHub + appendix required |
