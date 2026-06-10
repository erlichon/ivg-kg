"""Hand-authored MOCK data for the IVG-KG dashboard mockup (offline, deterministic).

One coherent scenario — *"When was Frédéric Chopin's father born?"* — authored to
exercise every status, both Supportable variants, the value-mismatch fabrication,
and the §4.8 per-claim/answer diagnostics across {full, knowledge-absent,
content-absent} over N ∈ {5, 10, 20} draws.

This is MOCK ONLY: no model, no SPARQL, no network. The grounding backend stays a
stub; these fixtures stand in for what the real precompute would emit.

Public surface:
  mock_grounding_run()        -> the displayed FULL draw #0 (rich claims)
  mock_subgraph_elements()    -> dash-cytoscape elements (via the real graph_store)
  mock_grading_reference()    -> the never-ablated reference (KG-full + content labels)
  build_runset(n)             -> list[GroundingRun] : the N draws x conditions
  mock_answer_diagnostics(n)  -> AnswerDiagnostics aggregated from build_runset(n)
  CLAIM_SPANS                 -> {claim_id: substring of answer_text} for inline colouring
  QUESTION, ANSWER_TEXT, ERROR_RATES, N_CHOICES
"""
from __future__ import annotations

from ivg_kg.data.graph_store import nx_to_cyto_elements
from ivg_kg.diagnostics import aggregate_runset
from ivg_kg.schema import (
    ABSENT,
    AnswerDiagnostics,
    ClaimRecord,
    ClaimStatus,
    Condition,
    ContentLabel,
    GradingReference,
    GroundingPath,
    GroundingRun,
    KGEdge,
    KGNode,
    KGSnapshot,
    LinkedEntity,
    Modality,
    PathEdge,
    SupportSource,
    ValueType,
)

# ---------------------------------------------------------------------------
# Scenario constants
# ---------------------------------------------------------------------------
QUESTION = "When was Frédéric Chopin's father born?"
ANSWER_TEXT = (
    "Frédéric Chopin's father was Nicolas Chopin, who was born on "
    "17 June 1771 in Marainville-sur-Madon, France. Chopin is known for his "
    "Nocturnes."
)

# Entities (QIDs are illustrative; this is mock data).
FCHOPIN = "Q1268"
NCHOPIN = "Q260763"
MARAIN = "Q1392501"
FRANCE = "Q142"
NOCT = "Q207591"

# The reference-correct date of birth (the grader holds THIS; the answer says 17 June).
DOB_TRUE = "15 April 1771"
DOB_FALSE = "17 June 1771"

# Properties.
P_FATHER = ("P22", "father")
P_DOB = ("P569", "date of birth")
P_POB = ("P19", "place of birth")
P_COUNTRY = ("P17", "country")
P_NOTABLE = ("P800", "notable work")

# Fact SLOTS (head + canonical relation; SPEC-text §4.8). The diagnostics are
# anchored on these; a claim_key is slot_key + "|" + normalized_value (the VARIANT).
SLOT_FATHER = f"{FCHOPIN}|P22"  # Chopin -> father
SLOT_FPOB = f"{NCHOPIN}|P19"  # father -> place of birth
SLOT_FDOB = f"{NCHOPIN}|P569"  # father -> date of birth  (the multi-variant slot)
SLOT_FCOUNTRY = f"{NCHOPIN}|P19+P17"  # father -> born in <country> (multi-hop)
SLOT_CPOB = f"{FCHOPIN}|P19"  # Chopin -> own place of birth (the spurious France)
SLOT_NOTABLE = f"{FCHOPIN}|P800"  # Chopin -> notable work

# Normalized values for the FALSE variants the generator hallucinates (mock,
# opaque value tokens; they never enter the reference KG).
VAL_DOB_TRUE = "1771-04-15"  # the reference-correct birth date variant
VAL_DOB_FALSE = "1771-06-17"  # the displayed wrong-value variant
_FALSE_FATHER = "Q-false-father"
_FALSE_FPOB = "Q-false-fpob"
_FALSE_COUNTRY = "Q-false-country"
_FALSE_NOTABLE = "lit:false-notable"

# Per-modality classifier error for the Trust strip (SPEC-text §4.7).
ERROR_RATES: dict[str, float] = {"text-nli": 0.06, "structure-path": 0.09}

# N-generation choices the Analytics selector offers.
N_CHOICES: list[int] = [5, 10, 20]
_MAX_DRAWS = 20

_NODE_LABELS = {
    FCHOPIN: "Frédéric Chopin",
    NCHOPIN: "Nicolas Chopin",
    MARAIN: "Marainville-sur-Madon",
    FRANCE: "France",
    NOCT: "Nocturnes",
}
_NODE_DESCRIPTIONS = {
    FCHOPIN: "Polish composer and virtuoso pianist of the Romantic era (1810–1849).",
    NCHOPIN: "French-born father of Frédéric Chopin; émigré tutor in Poland (1771–1844).",
    MARAIN: "Commune in the Vosges department, Grand Est, France.",
    FRANCE: "Country in Western Europe.",
    NOCT: "Set of solo piano pieces by Frédéric Chopin.",
}


# ---------------------------------------------------------------------------
# Knowledge graph (snapshot → NetworkX → cytoscape via the real graph_store)
# ---------------------------------------------------------------------------
def chopin_snapshot() -> KGSnapshot:
    """The KG-full books snapshot for the Chopin scenario (fresh each call)."""
    nodes = [
        KGNode(id=qid, label=label, description=_NODE_DESCRIPTIONS.get(qid))
        for qid, label in _NODE_LABELS.items()
    ]
    edges = [
        KGEdge(
            subject_id=FCHOPIN, property_id=P_FATHER[0], property_label=P_FATHER[1],
            object_id=NCHOPIN, object_label="Nicolas Chopin", value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id=NCHOPIN, property_id=P_DOB[0], property_label=P_DOB[1],
            object_id=None, object_label=DOB_TRUE, value_type=ValueType.TIME,
        ),
        KGEdge(
            subject_id=NCHOPIN, property_id=P_POB[0], property_label=P_POB[1],
            object_id=MARAIN, object_label="Marainville-sur-Madon", value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id=MARAIN, property_id=P_COUNTRY[0], property_label=P_COUNTRY[1],
            object_id=FRANCE, object_label="France", value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id=FCHOPIN, property_id=P_NOTABLE[0], property_label=P_NOTABLE[1],
            object_id=NOCT, object_label="Nocturnes", value_type=ValueType.ITEM,
        ),
    ]
    return KGSnapshot(
        snapshot_id="chopin-mock-v1", slice="books", domain_qid=FCHOPIN,
        nodes=nodes, edges=edges, meta={"scenario": "chopin-father-dob"},
    )


def mock_subgraph_elements() -> list[dict]:
    """dash-cytoscape elements for the Chopin subgraph (literal date node included)."""
    return nx_to_cyto_elements(chopin_snapshot())


def mock_grading_reference() -> GradingReference:
    """The never-ablated grading reference (KG-full + a content-only label)."""
    return GradingReference(
        snapshot=chopin_snapshot(),
        content_labels=[
            ContentLabel(
                entity_id=NCHOPIN, modality=Modality.TEXT,
                fact="Nicolas Chopin was a French émigré who settled in Poland.",
                source="description",
            )
        ],
    )


def _ent(qid: str) -> LinkedEntity:
    return LinkedEntity(id=qid, label=_NODE_LABELS[qid], description=_NODE_DESCRIPTIONS.get(qid))


def _pe(subj: str, prop: tuple[str, str], obj: str, obj_label: str) -> PathEdge:
    return PathEdge(
        subject_id=subj, subject_label=_NODE_LABELS[subj],
        property_id=prop[0], property_label=prop[1],
        object_id=obj, object_label=obj_label, traversed_forward=True,
    )


# ---------------------------------------------------------------------------
# Canonical claims (the displayed FULL draw #0) — rich, with paths + diagnostics
# ---------------------------------------------------------------------------
def canonical_claims() -> list[ClaimRecord]:
    """The six canonical claims (fresh objects each call)."""
    empty_path = GroundingPath(edges=[], node_ids=[])
    return [
        # c1 — RETRIEVED via direct triple P22 (father).
        ClaimRecord(
            claim_id="c1",
            text="Frédéric Chopin's father was Nicolas Chopin",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            slot_key=SLOT_FATHER, claim_key=f"{SLOT_FATHER}|{NCHOPIN}",
            linked_entities=[_ent(FCHOPIN), _ent(NCHOPIN)],
            grounding_path=empty_path, entailment_score=0.97,
        ),
        # c2 — RETRIEVED via direct triple P19 (place of birth).
        ClaimRecord(
            claim_id="c2",
            text="Nicolas Chopin was born in Marainville-sur-Madon",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            slot_key=SLOT_FPOB, claim_key=f"{SLOT_FPOB}|{MARAIN}",
            linked_entities=[_ent(NCHOPIN), _ent(MARAIN)],
            grounding_path=empty_path, entailment_score=0.95,
        ),
        # c3 — FABRICATED: value mismatch (reference holds 15 April 1771).
        ClaimRecord(
            claim_id="c3",
            text="Nicolas Chopin was born on 17 June 1771",
            status=ClaimStatus.FABRICATED, support_source=SupportSource.NONE,
            slot_key=SLOT_FDOB, claim_key=f"{SLOT_FDOB}|{VAL_DOB_FALSE}",
            linked_entities=[_ent(NCHOPIN)],
            grounding_path=empty_path, entailment_score=0.18,
            spurious_path=False,
        ),
        # c4 — SUPPORTABLE, GENUINE path: father born in France (P19 → P17).
        ClaimRecord(
            claim_id="c4",
            text="Chopin's father was born in France",
            status=ClaimStatus.REASONED_SUPPORTABLE, support_source=SupportSource.MULTI_HOP_PATH,
            slot_key=SLOT_FCOUNTRY, claim_key=f"{SLOT_FCOUNTRY}|{FRANCE}",
            linked_entities=[_ent(NCHOPIN), _ent(FRANCE)],
            grounding_path=GroundingPath(
                edges=[
                    _pe(NCHOPIN, P_POB, MARAIN, "Marainville-sur-Madon"),
                    _pe(MARAIN, P_COUNTRY, FRANCE, "France"),
                ],
                node_ids=[NCHOPIN, MARAIN, FRANCE],
            ),
            entailment_score=0.86, spurious_path=False,
        ),
        # c5 — SUPPORTABLE but FLAGGED spurious: path reaches France via the FATHER's
        # birthplace, not Chopin's own (relation/value illegitimacy).
        ClaimRecord(
            claim_id="c5",
            text="Frédéric Chopin was born in France",
            status=ClaimStatus.REASONED_SUPPORTABLE, support_source=SupportSource.MULTI_HOP_PATH,
            slot_key=SLOT_CPOB, claim_key=f"{SLOT_CPOB}|{FRANCE}",
            linked_entities=[_ent(FCHOPIN), _ent(FRANCE)],
            grounding_path=GroundingPath(
                edges=[
                    _pe(FCHOPIN, P_FATHER, NCHOPIN, "Nicolas Chopin"),
                    _pe(NCHOPIN, P_POB, MARAIN, "Marainville-sur-Madon"),
                    _pe(MARAIN, P_COUNTRY, FRANCE, "France"),
                ],
                node_ids=[FCHOPIN, NCHOPIN, MARAIN, FRANCE],
            ),
            entailment_score=0.71,
            spurious_path=True,
            spurious_reason=(
                "relation/value illegitimacy: the path reaches France via the "
                "father's place of birth (P22→P19→P17), not the subject's own "
                "birthplace (P19) — Chopin was born in Żelazowa Wola, Poland."
            ),
        ),
        # c6 — RETRIEVED via direct triple P800 (notable work).
        ClaimRecord(
            claim_id="c6",
            text="Chopin is known for his Nocturnes",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            slot_key=SLOT_NOTABLE, claim_key=f"{SLOT_NOTABLE}|{NOCT}",
            linked_entities=[_ent(FCHOPIN), _ent(NOCT)],
            grounding_path=empty_path, entailment_score=0.93,
        ),
    ]


# Inline answer-text spans (substrings) per claim, for status-coloured highlighting.
# c5 is inferential (no contiguous span) → claim list only.
CLAIM_SPANS: dict[str, str] = {
    "c1": "Frédéric Chopin's father was Nicolas Chopin",
    "c3": "born on 17 June 1771",
    "c2": "Marainville-sur-Madon",
    "c4": "France",
    "c6": "Chopin is known for his Nocturnes",
}


# ---------------------------------------------------------------------------
# Per-SLOT variant draw model (counts over _MAX_DRAWS GENERATION draws).
#
# The verifier is deterministic and grades against the full KG, so a VARIANT (a
# fixed value for a slot) has ONE fixed status. What varies across the N draws is
# WHICH variant the generator emits for each slot (or none -> absent). The mock
# therefore tracks, per slot per condition, how often each variant value (and
# absent) is drawn. Story: structural slots are answered with the correct value
# under FULL but, under knowledge-absence, the generator more often emits a
# WRONG-VALUE variant (fabricated) or omits the slot; the father's birth-DATE
# slot is genuinely multi-variant even under FULL (the right date AND the
# displayed wrong date both appear) -- this is where "fabrication = a wrong value
# in the same slot" is visible. All variance is GENERATION variance (SPEC §4.8).
# ---------------------------------------------------------------------------
R = ClaimStatus.RETRIEVED
S = ClaimStatus.REASONED_SUPPORTABLE
F = ClaimStatus.FABRICATED
A = ABSENT

# Multi-hop supportable paths that the value-sensitive gate passes but that are
# illegitimate support (SPEC-text §4.8 spurious_path); the displayed c5 shares it.
_SPURIOUS_SLOTS = {SLOT_CPOB}
_SPURIOUS_REASON = (
    "relation/value illegitimacy: the path reaches France via the father's "
    "place of birth (P22→P19→P17), not the subject's own birthplace (P19) — "
    "Chopin was born in Żelazowa Wola, Poland."
)

# slot_key -> list of variants: (normalized_value, fixed status, surface text).
# The first entry is the variant shown in the displayed answer (canonical_claims).
_SLOT_VARIANTS: dict[str, list[tuple[str, ClaimStatus, str]]] = {
    SLOT_FATHER: [
        (NCHOPIN, R, "Frédéric Chopin's father was Nicolas Chopin"),
        (_FALSE_FATHER, F, "Frédéric Chopin's father was Marc Chopin"),
    ],
    SLOT_FPOB: [
        (MARAIN, R, "Nicolas Chopin was born in Marainville-sur-Madon"),
        (_FALSE_FPOB, F, "Nicolas Chopin was born in Nancy"),
    ],
    SLOT_FDOB: [
        (VAL_DOB_TRUE, R, "Nicolas Chopin was born on 15 April 1771"),
        (VAL_DOB_FALSE, F, "Nicolas Chopin was born on 17 June 1771"),
    ],
    SLOT_FCOUNTRY: [
        (FRANCE, S, "Chopin's father was born in France"),
        (_FALSE_COUNTRY, F, "Chopin's father was born in Poland"),
    ],
    SLOT_CPOB: [
        (FRANCE, S, "Frédéric Chopin was born in France"),
        (_FALSE_COUNTRY, F, "Frédéric Chopin was born in Poland"),
    ],
    SLOT_NOTABLE: [
        (NOCT, R, "Chopin is known for his Nocturnes"),
        (_FALSE_NOTABLE, F, "Chopin is known for his symphonies"),
    ],
}

# slot_key -> condition -> {normalized_value | ABSENT: draw count} (each sums to 20).
_SLOT_DRAW_COUNTS: dict[str, dict[str, dict[str, int]]] = {
    SLOT_FATHER: {
        Condition.FULL.value: {NCHOPIN: 18, _FALSE_FATHER: 1, A: 1},
        Condition.KNOWLEDGE_ABSENT.value: {NCHOPIN: 3, _FALSE_FATHER: 12, A: 5},
        Condition.CONTENT_ABSENT.value: {NCHOPIN: 18, A: 2},
    },
    SLOT_FPOB: {
        Condition.FULL.value: {MARAIN: 18, _FALSE_FPOB: 1, A: 1},
        Condition.KNOWLEDGE_ABSENT.value: {MARAIN: 4, _FALSE_FPOB: 10, A: 6},
        Condition.CONTENT_ABSENT.value: {MARAIN: 17, A: 3},
    },
    SLOT_FDOB: {  # the multi-variant star slot
        Condition.FULL.value: {VAL_DOB_TRUE: 8, VAL_DOB_FALSE: 7, A: 5},
        Condition.KNOWLEDGE_ABSENT.value: {VAL_DOB_TRUE: 1, VAL_DOB_FALSE: 16, A: 3},
        Condition.CONTENT_ABSENT.value: {VAL_DOB_TRUE: 7, VAL_DOB_FALSE: 8, A: 5},
    },
    SLOT_FCOUNTRY: {
        Condition.FULL.value: {FRANCE: 16, A: 4},
        Condition.KNOWLEDGE_ABSENT.value: {FRANCE: 4, _FALSE_COUNTRY: 8, A: 8},
        Condition.CONTENT_ABSENT.value: {FRANCE: 15, A: 5},
    },
    SLOT_CPOB: {  # spurious-France supportable; collapses when the father link is withheld
        Condition.FULL.value: {FRANCE: 12, _FALSE_COUNTRY: 8},
        Condition.KNOWLEDGE_ABSENT.value: {FRANCE: 2, _FALSE_COUNTRY: 14, A: 4},
        Condition.CONTENT_ABSENT.value: {FRANCE: 11, _FALSE_COUNTRY: 9},
    },
    SLOT_NOTABLE: {
        Condition.FULL.value: {NOCT: 18, _FALSE_NOTABLE: 1, A: 1},
        Condition.KNOWLEDGE_ABSENT.value: {NOCT: 3, _FALSE_NOTABLE: 11, A: 6},
        Condition.CONTENT_ABSENT.value: {NOCT: 18, A: 2},
    },
}

# Display claim_id (canonical_claims) -> slot_key, for the per-claim card lookup.
SLOT_BY_CLAIM_ID: dict[str, str] = {
    "c1": SLOT_FATHER, "c2": SLOT_FPOB, "c3": SLOT_FDOB,
    "c4": SLOT_FCOUNTRY, "c5": SLOT_CPOB, "c6": SLOT_NOTABLE,
}

# Per-slot status + text lookup for a drawn variant value.
_VARIANT_INFO: dict[str, dict[str, tuple[ClaimStatus, str]]] = {
    slot: {value: (status, text) for value, status, text in variants}
    for slot, variants in _SLOT_VARIANTS.items()
}


def _spread(counts: dict[str, int], order: list[str]) -> list[str]:
    """Deterministically spread `counts` into a length-sum(counts) sequence.

    Lowest placed/target ratio wins each slot (ties broken by `order`), so a
    minority value is distributed across the sequence — making N-prefixes of
    5/10/20 give meaningfully different fractions (the N-selector does something).
    The first declared value lands at index 0.
    """
    placed = dict.fromkeys(counts, 0)

    def _rank(k: str) -> int:
        return order.index(k) if k in order else len(order)

    seq: list[str] = []
    for _ in range(sum(counts.values())):
        best = min(counts, key=lambda k: (placed[k] / counts[k], _rank(k)))
        seq.append(best)
        placed[best] += 1
    return seq


def _slot_value_vectors(condition: str) -> dict[str, list[str]]:
    """slot_key -> per-draw drawn value (or ABSENT) under one condition."""
    vectors: dict[str, list[str]] = {}
    for slot, by_cond in _SLOT_DRAW_COUNTS.items():
        # Tie-break order: declared variant values first, then ABSENT.
        order = [v for v, _, _ in _SLOT_VARIANTS[slot]] + [A]
        vectors[slot] = _spread(by_cond[condition], order)
    return vectors


def mock_grounding_run() -> GroundingRun:
    """The displayed run: FULL condition, draw #0, the rich canonical claims."""
    return GroundingRun(
        run_id="chopin-full-0", question=QUESTION, answer_text=ANSWER_TEXT,
        slice="books", phase="A", condition=Condition.FULL, sample_index=0,
        claims=canonical_claims(), grading_reference_id="chopin-mock-v1",
        error_rates=dict(ERROR_RATES),
    )


def _support_for(status: ClaimStatus) -> SupportSource:
    if status == ClaimStatus.REASONED_SUPPORTABLE:
        return SupportSource.MULTI_HOP_PATH
    if status == ClaimStatus.RETRIEVED:
        return SupportSource.DIRECT_TRIPLE
    return SupportSource.NONE


def build_runset(n: int = _MAX_DRAWS) -> list[GroundingRun]:
    """Materialize the RunSet: n GENERATION draws under each condition.

    For each condition, draw j fills each SLOT with whichever variant the
    generator emitted on that draw (or omits the slot when the drawn value is
    ABSENT). Each emitted claim carries the variant's FIXED status, its slot_key,
    and a claim_key of slot_key + "|" + value. Grading is deterministic against
    the full KG, so a variant's status never changes across draws/conditions; only
    which variant appears does. Deterministic; n is clamped to [1, 20].
    """
    n = max(1, min(n, _MAX_DRAWS))
    conditions = [
        Condition.FULL, Condition.KNOWLEDGE_ABSENT, Condition.CONTENT_ABSENT,
    ]
    empty_path = GroundingPath(edges=[], node_ids=[])
    runs: list[GroundingRun] = []
    for cond in conditions:
        vectors = _slot_value_vectors(cond.value)
        for j in range(n):
            draw_claims: list[ClaimRecord] = []
            for slot, values in vectors.items():
                value = values[j]
                if value == A:
                    continue
                status, text = _VARIANT_INFO[slot][value]
                spurious = slot in _SPURIOUS_SLOTS and status == ClaimStatus.REASONED_SUPPORTABLE
                draw_claims.append(
                    ClaimRecord(
                        claim_id=f"{slot}|{value}", text=text, status=status,
                        support_source=_support_for(status),
                        slot_key=slot, claim_key=f"{slot}|{value}",
                        linked_entities=[], grounding_path=empty_path,
                        spurious_path=spurious,
                        spurious_reason=_SPURIOUS_REASON if spurious else None,
                    )
                )
            runs.append(
                GroundingRun(
                    run_id=f"chopin-{cond.value}-{j}", question=QUESTION,
                    answer_text=ANSWER_TEXT, slice="books", phase="A",
                    condition=cond, sample_index=j, claims=draw_claims,
                    grading_reference_id="chopin-mock-v1", error_rates=dict(ERROR_RATES),
                )
            )
    return runs


def mock_answer_diagnostics(n: int = _MAX_DRAWS) -> AnswerDiagnostics:
    """Aggregate the n-draw RunSet into AnswerDiagnostics (§4.8)."""
    return aggregate_runset(build_runset(n))


# ---------------------------------------------------------------------------
# Graph editor (mock; SPEC-text §4.6 / RQ3 + CogMG augmentation)
# ---------------------------------------------------------------------------
# The subgraph IS the editable KG. Ablation is PER SPECIFIC TRIPLE (no global
# "knowledge-absent" mode): REMOVE a triple → it leaves the graph AND the answer
# is regenerated without it → the claims re-verify. INJECT lets the analyst enter
# a NEW triple (a model suggestion pre-fills it, but it is editable) — the CogMG
# case. Deterministic, offline.

# The editable edges of the graph (the books triples).
TRIPLES: list[dict] = [
    {"id": "P22", "subj": FCHOPIN, "prop_label": "father",
     "obj": NCHOPIN, "obj_label": "Nicolas Chopin", "literal": False},
    {"id": "P19", "subj": NCHOPIN, "prop_label": "place of birth",
     "obj": MARAIN, "obj_label": "Marainville-sur-Madon", "literal": False},
    {"id": "P17", "subj": MARAIN, "prop_label": "country",
     "obj": FRANCE, "obj_label": "France", "literal": False},
    {"id": "P800", "subj": FCHOPIN, "prop_label": "notable work",
     "obj": NOCT, "obj_label": "Nocturnes", "literal": False},
    {"id": "P569", "subj": NCHOPIN, "prop_label": "date of birth",
     "obj": None, "obj_label": DOB_TRUE, "literal": True},
]
ALL_TRIPLE_IDS: list[str] = [t["id"] for t in TRIPLES]
_TRIPLE_BY_ID: dict[str, dict] = {t["id"]: t for t in TRIPLES}

# Model suggestion that pre-fills the (editable) inject form.
SUGGESTED_INJECT: dict = {"subject": NCHOPIN, "relation": "date of birth", "value": DOB_TRUE}
ENTITY_OPTIONS: list[dict] = [
    {"label": _NODE_LABELS[q], "value": q} for q in (FCHOPIN, NCHOPIN, MARAIN, FRANCE, NOCT)
]

# Structural triples each claim needs PRESENT to ground; c3 (the date value-error)
# grounds only once a 'date of birth' triple is injected (the correction).
CLAIM_COVERAGE: dict[str, frozenset[str]] = {
    "c1": frozenset({"P22"}),
    "c2": frozenset({"P19"}),
    "c4": frozenset({"P19", "P17"}),
    "c5": frozenset({"P22", "P19", "P17"}),
    "c6": frozenset({"P800"}),
}
_GROUNDED_STATUS: dict[str, ClaimStatus] = {
    "c1": ClaimStatus.RETRIEVED,
    "c2": ClaimStatus.RETRIEVED,
    "c4": ClaimStatus.REASONED_SUPPORTABLE,
    "c5": ClaimStatus.REASONED_SUPPORTABLE,
    "c6": ClaimStatus.RETRIEVED,
}


def _date_injected(injected: list[dict] | None) -> bool:
    return any("date" in (inj.get("relation") or "").lower() for inj in (injected or []))


def statuses_for_graph(
    present: list[str] | None = None, injected: list[dict] | None = None
) -> dict[str, ClaimStatus]:
    """Re-verify the claims given the triples currently in the graph + injections.

    A structural claim grounds iff all its required triples are present; c3 (the
    date) grounds iff a 'date of birth' triple has been injected. Grading is always
    against the full reference — what changes is the model's regenerated answer
    under the edited graph.
    """
    pres = set(present if present is not None else ALL_TRIPLE_IDS)
    out: dict[str, ClaimStatus] = {}
    for cid in ("c1", "c2", "c3", "c4", "c5", "c6"):
        if cid == "c3":
            out[cid] = ClaimStatus.RETRIEVED if _date_injected(injected) else ClaimStatus.FABRICATED
        else:
            out[cid] = (
                _GROUNDED_STATUS[cid] if CLAIM_COVERAGE[cid] <= pres else ClaimStatus.FABRICATED
            )
    return out


def grounded_count(present: list[str] | None = None, injected: list[dict] | None = None) -> int:
    """How many of the 6 claims currently ground (not Fabricated)."""
    return sum(
        1 for s in statuses_for_graph(present, injected).values() if s != ClaimStatus.FABRICATED
    )


def removed_triples(present: list[str] | None) -> list[dict]:
    """The triples currently withheld from the graph (for the re-add list)."""
    pres = set(present if present is not None else ALL_TRIPLE_IDS)
    return [t for t in TRIPLES if t["id"] not in pres]


def editable_snapshot(
    present: list[str] | None = None, injected: list[dict] | None = None
) -> KGSnapshot:
    """A KGSnapshot containing only the present triples (+ injected triples)."""
    pres = set(present if present is not None else ALL_TRIPLE_IDS)
    edges: list[KGEdge] = []
    node_ids: set[str] = {FCHOPIN}  # always show the domain entity
    for t in TRIPLES:
        if t["id"] not in pres:
            continue
        node_ids.add(t["subj"])
        if not t["literal"]:
            node_ids.add(t["obj"])
        edges.append(KGEdge(
            subject_id=t["subj"], property_id=t["id"], property_label=t["prop_label"],
            object_id=None if t["literal"] else t["obj"], object_label=t["obj_label"],
            value_type=ValueType.TIME if t["literal"] else ValueType.ITEM,
        ))
    for inj in injected or []:
        subj = inj.get("subject") or NCHOPIN
        node_ids.add(subj)
        edges.append(KGEdge(
            subject_id=subj, property_id="INJ", property_label=inj.get("relation", "injected"),
            object_id=None, object_label=inj.get("value", ""), value_type=ValueType.STRING,
        ))
    nodes = [
        KGNode(id=q, label=_NODE_LABELS.get(q, q), description=_NODE_DESCRIPTIONS.get(q))
        for q in _NODE_LABELS
        if q in node_ids
    ]
    return KGSnapshot(snapshot_id="chopin-edit", slice="books", domain_qid=FCHOPIN,
                      nodes=nodes, edges=edges, meta={})


def editable_elements(
    present: list[str] | None = None, injected: list[dict] | None = None
) -> list[dict]:
    """Cytoscape elements for the current edited graph; injected edges are tagged."""
    els = nx_to_cyto_elements(editable_snapshot(present, injected))
    for e in els:
        if e["data"].get("property_id") == "INJ":
            e["data"]["injected"] = "1"
    return els


def claim_text_by_id() -> dict[str, str]:
    return {c.claim_id: c.text for c in canonical_claims()}
