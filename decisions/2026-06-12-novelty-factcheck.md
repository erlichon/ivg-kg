# Fact-check: ivg-kg novelty & prior-art claims

> Method: ARS deep-research **fact-check mode** (source-verification; IRON RULE: unconfirmable = FAIL,
> not "uncertain"). 5 verification agents, each required to find and quote the actual paper.
> Run 2026-06-12. Grounded additionally by two community awesome-lists (zjukg/KG-LLM-Papers,
> machuangtao/LLM-KG4QA) and six user-supplied sources (see end).
>
> BOTTOM LINE: the novelty claim SURVIVES, but must be RE-FRAMED. The causal-attribution *primitive*
> and the cited-but-not-needed *phenomenon* are NOT new; ivg-kg's novelty is the COMPOSITION
> (agreement-over-KG-triples + deterministic verifier + interactive VA + repair loop) and the
> KG-triple GRANULARITY + quadrant taxonomy. Two prior works must now be cited as closest prior art:
> ContextCite and "Attention is not Explanation."

## Per-claim verdicts

| Claim | Verdict | Threat? |
|---|---|---|
| C1 — no single work does the whole agreement+verifier+VA+repair combo | confirmed (via awesome-lists; no counterexample found) | no |
| C2 — KGLens / Mallen = per-fact knowledge probing, not agreement/ablation | **confirmed** | no |
| C3 — ContextCite / Wallat = cited != relied-upon, not KG/VA/agreement | **confirmed** | **YES — ContextCite (causal-attribution half)** |
| C4 — Agrawal 2512.00663 = nearest VA competitor, no ablation/repair | partially-confirmed (exists; see corrections) | low (closest VA competitor) |
| C5 — KGR/CogMG/GraphEval/VeGraph don't do agreement/ablation | confirmed (via awesome-lists) | no |
| C6 — AbstentionBench / TruthRL = answer-level abstention, not KG/visual | **confirmed** | no (answer-grain corroboration) |
| C7 — "redundant scaffold" is unclaimed | **partially-novel** (phenomenon known in text-RAG; KG-triple grain + taxonomy is new) | **YES — phenomenon is not new** |

## Corrected prior-art characterizations (with verified citations)

- **KGLens** = Zheng et al. (Apple), "KGLens: Towards Efficient and Effective Knowledge Probing of LLMs
  with KGs," **arXiv:2312.11539**, ACL 2024 workshop. Knowledge-probing via graph-guided question
  generation + Thompson-sampling edge selection. "Importance" = sampling efficiency, NOT causal
  evidence importance. No ablation, no VA, no agreement. NOT a threat.
- **Mallen et al.** = "When Not to Trust Language Models," **arXiv:2212.10511**, ACL 2023 (PopQA, 14k
  long-tail questions). Popularity-vs-parametric-recall; observational only, answer-level. NOT a threat.
- **ContextCite** = Cohen-Wang, **Shah, Georgiev**, Madry, "ContextCite: Attributing Model Generation
  to Context," **arXiv:2409.00729**, NeurIPS 2024. CORRECTION: our verdict mis-listed authors as
  "Engstrom, Ilyas" — actual are Shah & Georgiev. Method: sparse linear surrogate over random
  context-ablations -> per-source CAUSAL effect. **THREAT: it already does causal evidence attribution
  via ablation** — the causal-importance half of ivg-kg is NOT novel as a primitive. Differs by:
  text-span (not KG-triple) grain; a single attribution score (not an observational-vs-causal
  AGREEMENT); no deterministic KG verifier; no VA interface; no repair loop.
- **Wallat et al.** = "Correctness is not Faithfulness in RAG Attributions," **arXiv:2412.18004**,
  ICTIR 2025. Up to 57% of citations are unfaithful ("post-rationalization"). Supports cited!=relied;
  no KG, no VA, no agreement. NOT a threat.
- **Agrawal** = Tanmay Agrawal (U Arizona), "Graphing the Truth," **arXiv:2512.00663** (29 Nov 2025).
  EXISTENCE CONFIRMED (was provisional ref [7]-adjacent). IS a VA-flavored KG-grounded hallucination
  tool (demo: github.com/tanmayagrawal21/RAGChecker) -> "nearest VA competitor" is defensible.
  CORRECTIONS for the report: it uses a **four-quadrant reliability spectrum, NOT a three-way
  classification** (do not differentiate on "three-way vs theirs" carelessly); evaluation is
  **automated-accuracy-only on SummEval, NO user study**. Confirmed: no ablation/withholding, no
  repair-leverage. Differentiate on: ablation, repair-leverage, observational-vs-causal agreement,
  KG-triple grain, and human-in-the-loop evaluation.
- **AbstentionBench** = arXiv:2506.09038 (Meta, Jun 2025), "Reasoning LLMs Fail on Unanswerable
  Questions." Answer-level abstention benchmark; reasoning FT degrades abstention ~24%. Not KG, not
  visual. **TruthRL** = arXiv:2509.25760 (Meta, Sep 2025), RL with a ternary correct/hallucinate/abstain
  reward. Answer-grain; conceptually parallel to ivg-kg's 3-way map but NOT per-fact/KG. Cite as
  answer-level corroboration of the hallucinate-vs-abstain tradeoff.

## Novelty threats (must be addressed in the report)

1. **ContextCite (arXiv:2409.00729).** Already operationalizes causal importance of context via
   ablation. ivg-kg must NOT claim to invent causal evidence attribution. Re-frame: *"we extend
   counterfactual context attribution (ContextCite) to KG-triple granularity in a grounded-verification
   setting, and contribute the agreement analysis against observational support-frequency."*
2. **The cited-but-not-needed phenomenon is old.** Lineage: Jain & Wallace, "Attention is not
   Explanation" (NAACL 2019, arXiv:1902.10186); Longpre et al. entity-substitution + Knowledge Conflicts
   survey (arXiv:2403.08319); RAG mechanistic-reliance (arXiv:2410.00857, arXiv:2410.05162, showing
   reduced reliance on retrieved evidence when parametric memory suffices = "redundant retrieval").
   ivg-kg must cite this lineage and claim only the **per-triple granularity + KG-grounded setting +
   four-cell quadrant taxonomy** (load-bearing / redundant-scaffold / hidden-dependency / inert) as new.

## Newly discovered work to cite / consider

- **MultiHal** (ICLR 2026 submission, openreview uDgDuVMpfW) — multilingual KG-grounded hallucination
  benchmark (25.9k KG paths). Related work + possible evaluation dataset; not a competitor.
- **ApresCoT** (EDBT 2025 demo) — explaining LLM answers with KGs; closest interpretability-angle demo.
- **Pusch & Conrad** (arXiv:2409.04181) — KG-RAG biomedical QA with a Cypher query-checker + web UI;
  related KG-RAG tool, no ablation/agreement/repair.
- KG-attribution benchmarks ("Towards Verifiable Generation"; "Benchmarking LLMs in Complex QA
  Attribution using KGs") — relevant to RQ1 attribution framing.

## Bottom line

The contribution is defensible against the prior art, but its honest novelty is NARROWER than the
planning workflow asserted: not "first to measure causal importance of evidence" (ContextCite did that),
and not "first to notice cited!=needed" (Attention-is-not-Explanation lineage). The genuinely
unclaimed square is the COMPOSITION at KG-triple granularity: an observational(support-frequency)-vs-
causal(absence-shift) AGREEMENT taxonomy over individual KG facts, produced by a deterministic
verifier, explored interactively, and closed by a repair loop. Cite ContextCite + Attention-is-not-
Explanation as closest prior art and frame ivg-kg as extending them, and the novelty claim is reviewer-safe.

## Limitations & disclosure

Verifications relied on abstracts, paper HTML, and venue metadata via web search (not full-text reads
of every paper); the "no counterexample exists" claims (C1, C5) are bounded by the two awesome-lists'
coverage and the agents' searches, not an exhaustive census. AI-assisted research tools (Claude, via
the ARS deep-research fact-check pipeline) were used to produce this report; all citations were
independently resolved to arXiv/venue and should be re-confirmed before final submission.
