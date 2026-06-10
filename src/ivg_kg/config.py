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

# Local/open LLM used as the POC default behind BaseAIClient.
LOCAL_LLM_MODEL_ID: str = "meta-llama/Llama-3.2-3B-Instruct"

# MiniCheck entailment model (Apache-2.0); used by BaseEntailmentGate.
MINICHECK_MODEL_ID: str = "bespokelabs/Bespoke-MiniCheck-7B"

# post-M-BOOKS (gated image axis) — not used in P0
VLM_MODEL_ID: str = "Qwen/Qwen2.5-VL-3B-Instruct"
