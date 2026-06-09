# MMA Model: Multimedia and Visual Analytics in the Agentic Era

Source: `MMA_model_BNI_arXiv_version.pdf` (Worring, Zahalka, van den Elzen, Fischer, Keim, 2026)
Canonical course reference: [Worring2026] arXiv:2504.08138

---

## Overview diagram (Figure 1)

Three nested zones, left to right:

```
+---------------------------------------+--------------------------------------------+-------------------+
|   Foundation model-based AI           |   Human-AI Teaming (strategy loop)         | Human             |
|                                       |                                            | Understanding     |
|  External Knowledge:                  |  +-------------------------------+         |                   |
|    Implicit Knowledge                 |  | Visual Analytics Agents       |         | Tasks             |
|    Factual Knowledge                  |  |   Action-Specific Agents:     | <-----> | Actions           |
|                                       |  |     Analysis                  | Interacting/  | Hypothesis  |
|  Data:                                |  |     Search                    | Responding|  Findings     |
|    Domain Specific Data               |  |     Query                     |         | Insights          |
|    Generic Data                       |  |     Generation                |         | Knowledge         |
|                                       |  |                               |         |                   |
|  AI Agents:                           |  |   Coordinator Agent           |         | User Interface:   |
|    Tool Use Agent                     |  |     Goals                     |   ^     |   Outputs (Results)|
|    Code Generation Agent              |  |     Knowledge                 |   |     |   Process (Progress|
|    Observation-Based Agents           |  |     Strategy                  |   |     |     Navigation)   |
|    RAG                                |  |                               |   |     |   Knowledge       |
|                                       |  | [Prompting / Strategy Loop]   |   |     |     (Structure,   |
|  Expert Modules                       |  |                               |   |     |     Provenance)   |
|  Foundation Models                    |  +-------------------------------+   |     |   Trust (Explan-  |
|                                       |                                    |     |     ations,       |
|  Prompt Templates                     |   Guidance and Trust Loop ----------+     |     Confidence,   |
|                                       |                                          |     Performance)  |
+---------------------------------------+------------------------------------------+-------------------+
```

Communication channels: Prompting (FM-based AI -> VA Agents), Responding (VA Agents -> FM), Interacting/Responding (VA Agents <-> User Interface).

---

## Six design criteria (D1-D6)

| ID | Name | Statement |
|----|------|-----------|
| D1 | Consistency and Integration | Align with established VA, MMA, HCI frameworks; adapt to agentic AI. |
| D2 | AI Functionality | Easily adapt to current/future FM capabilities (multimodal analysis, reasoning, autonomous behavior). |
| D3 | AI Limitations | Address hallucinations, tunnel vision, bias, lack of human values through human-AI teaming. |
| D4 | Visualization | Provide all task-relevant information concisely, completely, understandably, truthfully; give guidance for parallel analytical workflow. |
| D5 | Interaction Channels | Seamless, explicitly separable interaction channel; considers data/knowledge flow, implementation patterns, timeliness. |
| D6 | Shift in Analytical Reasoning | Capture collaborative nature of agentic AI; address steering, autonomy, knowledge generation, attribution, privacy, provenance. |

---

## Foundation Model-Based AI (Section 4)

### Knowledge and Data types (Section 4.1)
- **Implicit knowledge**: in FM weights (learned from generic data)
- **Factual knowledge**: in explicit external representations (knowledge graphs, databases)
- **Domain-specific data**: non-public or post-training data the FM has not seen
- **Generic data**: broad training corpus

### AI Agent types (Section 4.2)
- **Tool Use Agents**: decompose problems, aggregate outputs from tools
- **Code Generation Agents**: generate software code to answer queries or create visualizations
- **Observation-Based Agents**: observe world/websites/processes, act on conditions
- **RAG Agents**: continuously incorporate external database knowledge to improve accuracy

### Expert Modules
- Domain-specific knowledge ranging from calculators to domain KGs
- Curated by human domain experts; volume much lower than FM training data
- Agentic systems should marry expert-module quality with FM breadth

### Prompt Templates (Section 4.4)
Definition: "a function containing one or more variables to be replaced by some media (text, image, video, sound, or other) to create a prompt as an instance of the template and thus defining a contract between the action specific agent making the (multimodal) request and the collective functionality of the AI models responding as one virtual model with structured output and a rationale."

---

## Human Understanding (Section 5)

### Knowledge Generation cycle (Section 5.1) -- from Sacha 2014
1. User starts with **hypotheses** grounded in prior **knowledge**
2. Executes **tasks** (sequence of actions): Analysis, Search, Query, Generation
3. Tasks lead to **findings** (local observations) and **insights** (coherent generalizations)
4. Insights externalized as **knowledge** (annotations, reports, encoded models)
5. Knowledge is continuous resource, shapes new hypotheses

### User Interface pillars (Section 5.2)
The UI must support four pillars, all backed by interactive visualizations:

| Pillar | Components | Purpose |
|--------|-----------|---------|
| Outputs | Results + Guidance | Explore results, get guidance on what to explore next |
| Process | Progress + Navigation | Show progress toward goals (progressive visualization); navigate datasets efficiently |
| Knowledge | Structure + Provenance | Visualize knowledge with attention to who/what provided it (human vs AI, implicit vs factual) |
| Trust | Explanations + Confidence + Performance | Rationale of AI decisions, uncertainty, performance measures |

### Visual Analytics Grammar
Definition: "An explicit broad enough, yet machine-readable, description defining high level valid analytic workflows in visual analytic systems through API-like machine interfaces of visual encodings, interaction techniques, data transformations, tasks, and feedback mechanisms."

---

## Human-AI Teaming (Section 6)

### Visual Analytics Agents (Section 6.1)
Definition: "an agent specialized in a specific action capable of taking an incoming multimodal request through a visual interface and, following its visual analytics strategy, provides an optimal result in a multimodal structure suited for visualization, accompanied by a trustworthy, i.e. lawful, ethical, and robust, rationale that highlights the core (intermediate) results and the strategy to reach the goal explicitly to the user, while also being capable of improving itself and providing feedback from the user."

Action-specific types: Analysis, Search, Query, Generation

**VA Agent internal architecture (Figure 4):**
```
Action Model               Reasoning and      VA Mapper
  Action-specific goals    Optimization       
  Prompt Templates    <--> (strategy) <-->    Result (Multimodal Structure)
  Visual Grammar                              Rationale (Context of results)
  VA Knowledge                                Provision (Recommendation)
       |
  Parser <-- Response                      Session Memory
  Prompting --> Prompt                       (Prompts, Results, Contexts, Feedback)
                                          Feedback Translation (Implicit/Explicit)
```

**VA Mapper**: three mappings:
- `<visual analytics grammar> -> <prompt template>` (user spec + feedback -> right prompt)
- `<response> -> <visual analytics grammar>` (best way to present multimodal result)
- `<feedback> -> <provision>` (recommendations to reach goal)

### Coordinator Agent
- Special VA Agent at abstract level
- Receives overarching goal, decomposes into subgoals for action-specific agents
- Handles asynchronous parallel results
- Human is the central coordinator in the framework (agent observes human)

### Strategy Loop (Section 6.2)
- FM-based AI connects to human-AI teaming through the **strategy loop**
- Includes chain-of-thought strategies (single CoT, multiple CoT, tree of thoughts, graph of thoughts)
- Operates at two levels: individual action-based agent level + coordinating agent level
- Session memory optimized for human-in-the-loop reinforcement learning

### Guidance and Trust Loop (Section 6.3)
- Low-level: **specification-result loop** (user formulates query + actions, data, parameters)
- Structured result: multimodal structure in VA grammar elements
- Explicit feedback: user steers agents
- Coordinator forwards feedback to appropriate VA agent (interactive learning, personalization)
- **Recommendations**: orienting (support), directing (options), prescriptive (accept/reject)
- **Implicit feedback**: observations of user-system interactions, translated for strategy optimization

---

## Evaluation of Analytics Solutions (Section 7)

### Foundation model-based AI
- Benchmarks for FM analytic capabilities very limited
- AI agents benchmarked via reinforcement learning in well-defined environments
- "Analytics-tailored frameworks to support systematic and transferable assessment" needed

### Human Understanding
- Quantitative UI methods: task completion time, error rate, cognitive load (NASA-TLX)
- For cognitive aspects: **insight-based methods [North 2006]** far more appropriate than benchmarks
- Tailored evaluation model incorporating multimedia + VA grammar is missing

### Human-AI Teaming
- Remains open challenge: must evaluate a chain of multiple components, not isolated tasks
- **Insight-based methods [North 2006]** useful
- **Analytic Quality (AQ) [Zahalka 2015]**: simulates user evaluation runs, measures performance + efficiency metrics -- applicable but needs adaptation for FM era
- New evaluation paradigms needed

---

## Suggested Design Workflow (from paper Section 8 + intro slide p.90)

1. Specification of the high-level goal(s) and decomposition into the four actions (Analysis, Search, Query, Generation)
2. Selection of relevant prompt templates
3. Expressing abstract user interface in the visual analytics grammar
4. Inventory of implicit and explicit feedback VA agents can use + recommendations to provide
5. Definition of strategies and optimization

---

## FM Limitations addressed by Human-AI Teaming (Section 6.4)

| Limitation | Mitigation via human-AI teaming |
|------------|----------------------------------|
| Insufficient knowledge | RAG + user verification of external sources |
| Hallucinations | Condition RAG to strictly use KB; citation checking; verifier agent |
| Complexity of analytic tasks | Joint decomposition; human steers overall decomposition |
| Tunnel vision | Domain-specific instructions; multi-agent teams; human timely interventions |
| Limited communication channels | Text + MCP + VA grammar; rich multimodal UI |
| Bias and lack of human values | Human oversight + strong feedback; sensitivity domains always need human |
| Provider dependency | Smaller local models; shifts balance toward expert user; VA more important |

---

## Key prior models this framework builds on

| Model | Source | Role in MMA framework |
|-------|---------|----------------------|
| Knowledge Discovery pipeline | Fayyad 1996 | Data → features → knowledge, fully automated precursor |
| Information Visualization pipeline | Card 1999 | Interactive visualization component |
| Basic Visual Analytics model | Keim 2008 | Bringing together InfoVis + data mining |
| Sensemaking process | Pirolli-Card 2005 | Human analytic reasoning loop |
| Interaction Taxonomy | Pike 2009 | Science of interaction |
| Knowledge Generation Model | Sacha 2014 | Integrates cognitive processes with VA |
| First Multimedia Analytics Model | Zahalka 2014 | MMA predecessor |
| Guidance Model | Perez-Messina 2022 | Mixed-initiative visual analytics |

The MMA model is the **synthesis and extension** of all above into the foundation model / agentic AI era.
