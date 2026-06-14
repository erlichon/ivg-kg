"""
Project-wide configuration constants for IVG-KG.

All values are module-level constants; no env-var overrides at P0.
Nothing here triggers network I/O or heavy imports.
"""

# ---------------------------------------------------------------------------
# Sitelink band (SPEC-text §4.1)
# Select books whose Wikipedia sitelink count falls in [BAND_LO, BAND_HI].
# ---------------------------------------------------------------------------
BAND_LO: int = 5
BAND_HI: int = 40
SITELINK_BAND: tuple[int, int] = (BAND_LO, BAND_HI)

# ---------------------------------------------------------------------------
# Graph traversal (SPEC-text §4.2)
# ---------------------------------------------------------------------------
K_HOPS: int = 2  # default; tunable 2-3

# Max nodes drawn in the subgraph panel; above this, 1st-degree neighbour
# expansion of claim nodes is skipped (SPEC-text §4.5, interactions #3/#8).
SUBGRAPH_NODE_CAP: int = 40

# ---------------------------------------------------------------------------
# Grounding threshold (SPEC-text §4.3)
# Entailment score must exceed TAU for a claim to be considered supported.
# ---------------------------------------------------------------------------
TAU: float = 0.5

# ---------------------------------------------------------------------------
# SPARQL endpoints (SPEC-text §4.1)
# ---------------------------------------------------------------------------
WDQS_ENDPOINT: str = "https://query.wikidata.org/sparql"
QLEVER_ENDPOINT: str = "https://qlever.dev/api/wikidata"

# Descriptive User-Agent required by WDQS fair-use policy.
WDQS_USER_AGENT: str = (
    "ivg-kg/0.1 (Interpretable Visual Grounding via Knowledge Graphs; "
    "https://github.com/erlichon/ivg-kg; itay@jazz.security)"
)

# ---------------------------------------------------------------------------
# Model identifiers (SPEC-text §7)
# These are config constants only; nothing is downloaded at P0.
# ---------------------------------------------------------------------------

# Local/open LLM (Llama family) kept as a named constant; not the active generator.
LOCAL_LLM_MODEL_ID: str = "meta-llama/Llama-3.2-3B-Instruct"

# Entailment models for the VERIFIER (deterministic measurement instrument, NOT
# the generator). Verifier choice is ACCURACY-FIRST (latency is second-order).
# TODO(verifier-model): decision FINALIZED (SPEC-text §4.3) -- DeBERTa-v3-large on
# the LIVE path (the live path does verify live), MiniCheck-7B for OFFLINE
# precompute / calibration; cache verification by distinct evidence-pair. The
# verifier must stay a DIFFERENT model family from the generator (no
# self-verification). Mock behavior is unaffected by these ids.
MINICHECK_MODEL_ID: str = "bespokelabs/Bespoke-MiniCheck-7B"  # offline precompute / calibration
DEBERTA_NLI_MODEL_ID: str = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"  # live

# post-M-BOOKS (gated image axis) — not used in P0
VLM_MODEL_ID: str = "Qwen/Qwen2.5-VL-3B-Instruct"

# ---------------------------------------------------------------------------
# AI client selection (SPEC-text SS4.3, GR1)
# Controls which BaseAIClient implementation is returned by make_client().
# Valid values: "local", "ollama", "cloud".
# ---------------------------------------------------------------------------

# Backend used by get_default_client() and the grounding pipeline (GR4+).
# Generator decision FINALIZED: Qwen2.5-7B-Instruct via Ollama (Invariant #14).
DEFAULT_CLIENT_BACKEND: str = "ollama"

# Ollama server config (used by OllamaClient).
OLLAMA_BASE_URL: str = "http://localhost:11434"
# Generator model: Qwen2.5-7B-Instruct served locally via Ollama.
OLLAMA_MODEL_ID: str = "qwen2.5"

# Generation sampling parameters (Invariant #14: stochastic generator, seeded).
# Callers override per-draw; these are the defaults exposed on generate_answer().
DEFAULT_GENERATION_TEMPERATURE: float = 0.7
