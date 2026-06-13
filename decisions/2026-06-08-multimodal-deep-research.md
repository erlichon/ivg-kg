# Deep-research report: making ivg-kg genuinely multimodal

> Workflow: deep-research | run 2026-06-08 | saved 2026-06-12.
> STATUS NOTE: this report drove the artwork-primary / taxa-fallback image-axis pivot
> already applied to project_statement.md and the spec/ split. Saved for provenance.

## Question

RESEARCH QUESTION: How can the "ivg-kg" research project be made genuinely MULTIMODAL — adding images as a *fact-bearing* (not decorative) content modality that can be ablated exactly like textual descriptions, potentially using a locally-runnable open VLM as the answer generator and/or claim grounder instead of a text-only LLM — without breaking the project's scientific spine? Produce a concrete, cited recommendation.

PROJECT CONTEXT (constraints the recommendation MUST respect):
- The project is an interactive visual-analytics tool (Plotly/Dash) that grounds each LLM claim against a FROZEN LOCAL slice of Wikidata and classifies it retrieved / reasoned-supportable / fabricated. Scientific spine = "absence-induced hallucination": fabrication when needed evidence is NOT in the model's context. The core experiment is a controlled comparison of CONTENT-absence (currently textual descriptions) vs KNOWLEDGE-absence (structural triples withheld from context), measuring whether the MODALITY of missing evidence changes fabrication (RQ2). Generation is in-context/RAG: evidence is assembled into the prompt; ablation = withholding evidence from the generation context; classification is always against the FULL KG (ground truth).
- CRITICAL non-redundancy constraint: an image only counts as a content modality if it carries QUERYABLE FACTS that are NOT already encoded in the entity's triples OR its textual description. The project statement already asserts that general-purpose KG images (e.g. Wikidata P18) are usually DECORATIVE / identity-confirming for the current domain (books, Q571). ADVERSARIALLY VERIFY this claim, and find where it is FALSE.
- Domain is currently locked to books (Wikidata Q571) via an empirical content/structure-overlap check. Entities are sampled in a sitelink band (~5-40) so descriptions add info and structure stays trustworthy. Demo must be reproducible and offline-safe (precomputed); runtime on the author's hardware: Apple Silicon MacBook Pro, 48 GB RAM, 12 cores, MPS backend, possibly a local GPU later.

DELIVER A CITED REPORT COVERING:
1. FACT-BEARING IMAGES IN WIKIDATA. Inventory image-type properties beyond P18 (e.g. page banners, document scans, frontispieces, diagrams, maps, coats of arms, etc.). For which entity classes do images encode QUERYABLE facts absent from triples/description? For BOOKS specifically: are ANY book-related images fact-bearing (cover/genre cues, title pages showing volume count, illustrated plates, manuscript pages)? Verify the "decorative" claim with evidence.
2. ALTERNATIVE / ADDITIONAL DOMAINS where images are DEMONSTRABLY fact-bearing AND that still fit the project (sparse-enough structure, rich content, sitelink-band sampling, controlled testbed, non-redundancy). Evaluate concrete candidates such as: visual artworks/paintings (what is depicted, style), maps, botanical/zoological taxa (morphology), heraldry/coats of arms, buildings/architecture, manuscripts, postage stamps/currency, scientific figures. For each: example questions whose answer lives ONLY in the image; how ablating the image would change answers; risks.
3. LOCAL/OPEN VLMs runnable on Apple Silicon (MPS, 48 GB) and optionally a later GPU. Compare Qwen2-VL / Qwen2.5-VL, Llama-3.2-Vision-11B, LLaVA-1.6, InternVL2/2.5, Molmo, MiniCPM-V, Phi-3.5-Vision, SmolVLM: parameter size, license, MPS/Metal support (llama.cpp, MLX, Ollama, transformers), grounded-VQA quality, and suitability for (a) generating an answer from image+text context and (b) acting as an image-grounded claim verifier. Recommend specific models that run well on this hardware.
4. OPERATIONALIZING AN IMAGE CONTENT-ABSENCE ABLATION analogous to description ablation: how to present the image in the VLM's context vs withhold it; how to GROUND an image-derived claim against ground truth (image carries a fact that is also independently known/labelled, so KG-full grounding still works); how the three-way classification (retrieved / reasoned-supportable / fabricated) extends when the supporting evidence is an image (is there an "image entails claim" check — VLM-as-judge, image-text NLI, CLIP-style — analogous to the text MiniCheck entailment gate?).
5. PRIOR ART & REUSE: multimodal KGs (MMKG, Richpedia, VisualSem), multimodal claim verification / VLM hallucination grounding and benchmarks (e.g. POPE and successors), VISA (visual source attribution) relevance, any multimodal KGQA datasets. What is reusable vs reference-only; licenses.
6. RECOMMENDATION: a concrete, MINIMAL multimodal design that keeps the spine and adds a genuinely fact-bearing image axis. State explicitly: (a) stay-in-books-with-an-image-subcase, OR add a second fact-bearing domain, OR switch domain — with the tradeoff; (b) the specific VLM; (c) how the image ablation + image-grounding works end to end; (d) the non-redundancy verification to run BEFORE locking; (e) a fallback if images again prove decorative. Flag what would need to change in the project's framing/title and method.

Prefer permissively-licensed, offline-capable tooling. Be honest where multimodality is hard to justify rather than forcing it.

## Summary

Add P181 taxon range maps; see findings and caveats.

## Findings

### claim

Add P181 taxon range maps as a fact-bearing image domain; book P18 images are redundant since facts are already triples; P180 makes depicted facts redundant.

### confidence

high

### sources

['https://www.wikidata.org/wiki/Property:P181']

### evidence

Claims 0-9 mostly 3-0; claims 6 and 4 are 2-1; the P180 non-redundancy rival was refuted 0-3.

## Caveats

Use Qwen2.5-VL-7B or Qwen3-VL via MLX (vllm-mlx) on the 48GB Mac for generation and verification (DocVQA 95.7 vs 88.4; claims 10-19 all 3-0; the llama.cpp no-VLM claim was refuted, so MLX is on suitability). A VLM judge is unreliable out of the box (MFC-Bench, POPE object hallucination), so use a POPE fixed-template binary probe as the image analogue of the text MiniCheck gate, grounded against the full KG via an independent label; image ablation mirrors description ablation by including or withholding the image. VISA region bounding-box attribution needs fine-tuning. MMKG, Richpedia, and VisualSem are reference-only. Non-redundancy is not proven by any claim; run the gate per domain before locking. Recommendation: add P181 range maps, keep books as the text-content anchor, and let image-absence extend RQ2 to a third modality; the fallback is the current text-content versus knowledge-absence spine, and Multimodal is load-bearing only if the second domain passes the gate.

## Refuted claims

- {"claim": "The RfC explicitly frames the design question as whether distinct image types represent genuinely different facts versus merely decorative variations of a single image slot, surfacing the decorative-vs-fact-bearing distinction at the schema level.", "vote": "0-3", "source": "https://www.wikidata.org/wiki/Wikidata:Requests_for_comment/Image_properties:_many_properties_or_many_qualifiers"}
- {"claim": "For the books domain specifically, the template documents essentially no fact-bearing book image properties \u2014 only generic document/written-work media properties (P996 document file, P3030 sheet music) appear, and the page does NOT document page banner (P948), title page, frontispiece, or scanned-manuscript properties, supporting the project's claim that book images are largely decorative/identity-confirming.", "vote": "0-3", "source": "https://commons.wikimedia.org/wiki/Template:Wikidata_Infobox/doc/properties"}
- {"claim": "For paintings/artworks, the depicted facts (style, what is shown) live in the visual content and are captured by P180 rather than in a textual description \u2014 supporting the case that artworks are a non-redundant fact-bearing image domain unlike decorative book P18 images.", "vote": "0-3", "source": "https://www.wikidata.org/wiki/Property:P180"}
- {"claim": "The generic image property P18 is recommended identically for both works and editions as merely 'an illustration of the subject', with no guidance that it should depict the actual cover or title page, which supports the project's claim that P18 book images are decorative/identity-confirming rather than fact-bearing.", "vote": "0-3", "source": "https://www.wikidata.org/wiki/Wikidata:WikiProject_Books"}
- {"claim": "llama.cpp delivers strong text-model performance on Apple Silicon but does NOT support vision-language models, meaning a VLM deployment on the author's Mac must use a different backend (MLX, vLLM-MLX, transformers/MPS).", "vote": "0-3", "source": "https://arxiv.org/html/2601.19139v2"}

## Sources

- {"url": "https://www.wikidata.org/wiki/Wikidata:Requests_for_comment/Image_properties:_many_properties_or_many_qualifiers", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 4}
- {"url": "https://commons.wikimedia.org/wiki/Template:Wikidata_Infobox/doc/properties", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 5}
- {"url": "https://www.wikidata.org/wiki/Property:P181", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 4}
- {"url": "https://www.wikidata.org/wiki/Property:P180", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 5}
- {"url": "https://www.wikidata.org/wiki/Property:P18", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 4}
- {"url": "https://www.wikidata.org/wiki/Wikidata:WikiProject_Books", "quality": "primary", "angle": "Wikidata fact-bearing images", "claimCount": 5}
- {"url": "https://arxiv.org/html/2601.19139v2", "quality": "primary", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://github.com/waybarrios/vllm-mlx", "quality": "primary", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://blog.roboflow.com/local-vision-language-models/", "quality": "blog", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://presenc.ai/research/best-open-weight-vision-language-models-2026", "quality": "blog", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://www.emergentmind.com/topics/pope-and-mmhal-bench-benchmarks", "quality": "secondary", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://apidog.com/blog/qwen2-5-vl-32b-locally-mlx/", "quality": "blog", "angle": "Open VLMs Apple Silicon", "claimCount": 5}
- {"url": "https://arxiv.org/abs/2406.11288", "quality": "primary", "angle": "Grounding ablation prior art", "claimCount": 5}
- {"url": "https://arxiv.org/pdf/2305.10355", "quality": "primary", "angle": "Grounding ablation prior art", "claimCount": 4}
- {"url": "https://arxiv.org/abs/2412.14457", "quality": "primary", "angle": "Grounding ablation prior art", "claimCount": 4}

## Stats

```json
{
  "angles": 3,
  "sourcesFetched": 15,
  "claimsExtracted": 70,
  "claimsVerified": 25,
  "confirmed": 20,
  "killed": 5,
  "afterSynthesis": 1,
  "urlDupes": 0,
  "budgetDropped": 3,
  "agentCalls": 95
}
```
