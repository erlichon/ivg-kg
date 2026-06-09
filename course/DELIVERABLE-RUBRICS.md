# Deliverable Rubrics -- ivg-kg Project

Exact extraction from the three assignment instruction files. Use this as the primary grading checklist.

Sources:
- `course_assignment_instructions/intermediate_report_instructions` (ASCII text)
- `course_assignment_instructions/demo_instructions` (UTF-8 text)
- `course_assignment_instructions/scientific_report_instructions` (ASCII text)

---

## 1. Intermediate Report

**Weight in final grade: 20%**
**Due: Friday by 16:00**
**Format: PDF, IEEE VIS template, 3-4 pages EXCLUDING references**
**Submission: file upload**

### Required sections (all mandatory)

| Section | Requirement |
|---------|-------------|
| Teaser image | Two-column spanning image; in this initial report may be a sketch of the final interface showing planned visualizations |
| Introduction | 1-2 paragraphs: problem, data, target user, why relevant, main innovations; THEN a bullet list of the THREE main contributions you aim to make in the final scientific paper |
| Related work | 10 most relevant references; AT LEAST 5 must be from lecture slides/papers; each reference gets a 1-2 line description of why relevant and how you use or improve it |
| Methodology | Pointwise description of relevant steps; for complex preprocessing, add a figure with main processing blocks and data flow |
| Interaction design | Describe high-level and low-level interactions following the "science of interaction" paper (Pike 2009); explain how they help gain insight; FIGURE showing main components and their connections; "A simplified version of the main figure in the foundation model multimedia analytics paper (or the version discussed in the lectures for Multimedia Analytics for AI) could be a good starting point" |
| Evaluation design | How you will evaluate following the evaluation lecture techniques; recruted users OR analytic quality / simulated actors? |
| Implementation design | Motivated choice for Dash/Plotly architecture; take the provided demo system as starting point |
| Planning | How to realize in time for demo + report deadline; balance innovation vs feasibility |

### Grading dimensions (equal weighting implied)

1. **Motivation and Relevance** -- All major decisions clearly motivated? Idea embedded in relevant related work? Target users clear and why system is relevant to them (or what systems benefit if methodological)?
2. **Complexity** -- How complex is the problem? Does the proposed solution have the complexity needed to address challenges?
3. **Implementation** -- Clear design sketch, interaction scheme, and planning?
4. **Scientific excellence** -- How innovative with respect to published work?

### Key mandatories
- The "science of interaction" (Pike 2009) MUST be referenced in the interaction design section
- The MMA model main figure MUST inform the interaction design figure
- At least 5 references from lecture slide lists
- Three contributions stated explicitly as bullets

---

## 2. Demo

**Weight in final grade: 30%**
**Due: 23 Jun by 23:59 (available until 24 Jun 23:59)**
**Submission: website URL or file upload**
**Presentation: Friday June 27 (mandatory joint event)**
**Also required: screen recording up to 5 minutes showing ALL features (backup + evaluation aid)**

### Grading dimensions (equal weighting -- each 1/4 of 30%)

1. **Data processing**
   - Does the demo go beyond mere use of existing data?
   - Are advanced analysis tools used to bring out interesting parts?
   - Are multiple channels of information integrated to find patterns?
   - Focus on batch-based data processing (not interactive data processing)

2. **Technical complexity**
   - Advanced connection between visualization and the model?
   - Visualization goes beyond off-the-shelf components?
   - Core of visual analytics: feedback loop between visualization, model, user interaction
   - Requires interactive learning / data mining on dynamic, user-defined subsets
   - Efficient solutions (fluent interactions)

3. **Functionality**
   - Does the system provide means to get interesting insights (application area) OR clearly show how solutions work (methodological area)?
   - How rich is the set of functionalities?
   - Challenge: many options but all DIRECTLY related to the task -- do NOT overwhelm with visualizations that look nice but are not focused on the problem

4. **Aesthetics**
   - How attractive is the visualization?
   - Colors used consistently and pleasingly?
   - Layout chosen properly with good decomposition (tabs if appropriate)?
   - All choices ADD to functionality -- go beyond decoration?
   - Visualizations appropriate to show underlying data, patterns, models?

### Additional requirements
- Code available via GitHub (link in final scientific report)
- Starter from https://github.com/GoncaloBFM/mma2026

---

## 3. Scientific Report

**Weight in final grade: 50%**
**Due: 25 Jun by 23:59 (available until 28 Jun 23:59)**
**Format: IEEE VIS conference format and guidelines**
**Submission: PDF**

### Target areas (choose one)
- Area 2: applications
- Area 4: representations and interactions
- Area 5: data transformations
- Area 6: analytics & decisions

Reference: https://ieeevis.org/year/2026/info/call-participation/area-model/

### Grading dimensions (equal weighting -- each 1/4 of 50%)

1. **Writing and presentation**
   - Clear storyline?
   - All major decisions clearly motivated?
   - Main concepts and results illustrated with clear graphical representations?
   - Well embedded in related work?
   - Target users clear? Why would system be relevant to them? (or what systems benefit if not application area)

2. **Complexity**
   - How complex is the problem being addressed?
   - Does the solution have the complexity needed to address the challenges?

3. **Implementation**
   - How advanced is the software architecture?
   - Appropriate tools used?
   - Description covers motivated choices for components and their interaction, NOT specific details

4. **Scientific excellence**
   - How innovative with respect to published work?
   - Interesting quantitative OR qualitative results reported?
   - Will the paper have impact on the multimedia analytics community?
   - Has the method been evaluated following one of the techniques described in the lectures?
   - OR if not feasible: clear description how future work could best evaluate the tool

### Mandatory inclusions
- GitHub link to software + demo code
- Appendix: contribution of each group member to the overall project (incl. AI tools used -- ChatGPT, Gemini, Claude etc.)
- Scientific paper scope (6-8 pages in IEEE VIS format, as stated in course intro slides)

---

## Cross-cutting requirements from the intro lecture

- **Grade composition**: 20% intermediate + 30% demo + 50% final report (intro slide p.102)
- **Final event**: Friday June 27 -- mandatory -- demo presentations
- **IEEE VIS areas** the project should position toward: Area 4 (representations & interactions) or Area 6 (analytics & decisions) fit ivg-kg best
- **Two lenses the course offers** (intro p.95-96):
  - "Multimedia Analytics for AI" = targeting the AI developer: "a multimedia analytics solution where a user can interactively explore a complex AI architecture, its data and results to get a better understanding of its inner working and/or optimize its performance" -- THIS IS ivg-kg's framing
  - "AI for Multimedia Analytics" = targeting the expert user (the other lens, less applicable)
- The project must produce a **work statement** specifying every group member's contribution including AI tool use
