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
            claim_key=f"{FCHOPIN}|P22|{NCHOPIN}",
            linked_entities=[_ent(FCHOPIN), _ent(NCHOPIN)],
            grounding_path=empty_path, entailment_score=0.97,
        ),
        # c2 — RETRIEVED via direct triple P19 (place of birth).
        ClaimRecord(
            claim_id="c2",
            text="Nicolas Chopin was born in Marainville-sur-Madon",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            claim_key=f"{NCHOPIN}|P19|{MARAIN}",
            linked_entities=[_ent(NCHOPIN), _ent(MARAIN)],
            grounding_path=empty_path, entailment_score=0.95,
        ),
        # c3 — FABRICATED: value mismatch (reference holds 15 April 1771).
        ClaimRecord(
            claim_id="c3",
            text="Nicolas Chopin was born on 17 June 1771",
            status=ClaimStatus.FABRICATED, support_source=SupportSource.NONE,
            claim_key=f"{NCHOPIN}|P569|1771-06-17",
            linked_entities=[_ent(NCHOPIN)],
            grounding_path=empty_path, entailment_score=0.18,
            spurious_path=False,
        ),
        # c4 — SUPPORTABLE, GENUINE path: father born in France (P19 → P17).
        ClaimRecord(
            claim_id="c4",
            text="Chopin's father was born in France",
            status=ClaimStatus.REASONED_SUPPORTABLE, support_source=SupportSource.MULTI_HOP_PATH,
            claim_key=f"{NCHOPIN}|P19+P17|{FRANCE}",
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
            claim_key=f"{FCHOPIN}|P19|{FRANCE}",
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
            claim_key=f"{FCHOPIN}|P800|{NOCT}",
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
# Per-claim per-condition draw distributions (counts over _MAX_DRAWS draws).
# Story: structural RETRIEVED claims collapse under knowledge-absence but survive
# content-absence; the fabricated date worsens under knowledge-absence; the genuine
# path drops when its structure is withheld; the spurious path is unstable.
# ---------------------------------------------------------------------------
R = ClaimStatus.RETRIEVED.value
S = ClaimStatus.REASONED_SUPPORTABLE.value
F = ClaimStatus.FABRICATED.value
A = ABSENT

_DRAW_COUNTS: dict[str, dict[str, dict[str, int]]] = {
    "c1": {  # retrieved father (structural)
        Condition.FULL.value: {R: 19, S: 1},
        Condition.KNOWLEDGE_ABSENT.value: {R: 3, F: 12, A: 5},
        Condition.CONTENT_ABSENT.value: {R: 18, S: 2},
    },
    "c2": {  # retrieved place of birth (structural)
        Condition.FULL.value: {R: 18, S: 2},
        Condition.KNOWLEDGE_ABSENT.value: {R: 4, F: 10, A: 6},
        Condition.CONTENT_ABSENT.value: {R: 17, S: 3},
    },
    "c3": {  # fabricated date (value mismatch)
        Condition.FULL.value: {F: 16, A: 4},
        Condition.KNOWLEDGE_ABSENT.value: {F: 20},
        Condition.CONTENT_ABSENT.value: {F: 15, A: 5},
    },
    "c4": {  # supportable genuine path (father → France)
        Condition.FULL.value: {S: 16, A: 4},
        Condition.KNOWLEDGE_ABSENT.value: {S: 4, F: 8, A: 8},
        Condition.CONTENT_ABSENT.value: {S: 15, A: 5},
    },
    "c5": {  # supportable spurious path (Chopin → France via father)
        Condition.FULL.value: {S: 12, F: 8},
        Condition.KNOWLEDGE_ABSENT.value: {S: 2, F: 14, A: 4},
        Condition.CONTENT_ABSENT.value: {S: 11, F: 9},
    },
    "c6": {  # retrieved notable work (structural)
        Condition.FULL.value: {R: 18, S: 2},
        Condition.KNOWLEDGE_ABSENT.value: {R: 3, F: 11, A: 6},
        Condition.CONTENT_ABSENT.value: {R: 18, S: 2},
    },
}

_SPREAD_ORDER = [R, S, F, A]  # tie-break priority for deterministic interleave


def _spread(counts: dict[str, int]) -> list[str]:
    """Deterministically spread `counts` into a length-sum(counts) sequence.

    Lowest placed/target ratio wins each slot (ties by _SPREAD_ORDER), so a
    minority status is distributed across the sequence — making N-prefixes of
    5/10/20 give meaningfully different fractions (the N-selector does something).
    The highest-priority present status lands at index 0 (= the canonical
    FULL draw-#0 status).
    """
    placed = dict.fromkeys(counts, 0)
    seq: list[str] = []
    for _ in range(sum(counts.values())):
        best = min(
            counts,
            key=lambda k: (placed[k] / counts[k], _SPREAD_ORDER.index(k)),
        )
        seq.append(best)
        placed[best] += 1
    return seq


def _draw_vectors(condition: str) -> dict[str, list[str]]:
    return {cid: _spread(_DRAW_COUNTS[cid][condition]) for cid in _DRAW_COUNTS}


def mock_grounding_run() -> GroundingRun:
    """The displayed run: FULL condition, draw #0, the rich canonical claims."""
    return GroundingRun(
        run_id="chopin-full-0", question=QUESTION, answer_text=ANSWER_TEXT,
        slice="books", phase="A", condition=Condition.FULL, sample_index=0,
        claims=canonical_claims(), grading_reference_id="chopin-mock-v1",
        error_rates=dict(ERROR_RATES),
    )


def build_runset(n: int = _MAX_DRAWS) -> list[GroundingRun]:
    """Materialize the RunSet: n draws under each of {full, knowledge-, content-absent}.

    Draw j clones the canonical claims, overriding each claim's status with its
    j-th drawn status under that condition; a drawn status of ABSENT omits the
    claim from that draw. Deterministic; n is clamped to [1, 20].
    """
    n = max(1, min(n, _MAX_DRAWS))
    conditions = [
        Condition.FULL, Condition.KNOWLEDGE_ABSENT, Condition.CONTENT_ABSENT,
    ]
    runs: list[GroundingRun] = []
    for cond in conditions:
        vectors = _draw_vectors(cond.value)
        for j in range(n):
            draw_claims: list[ClaimRecord] = []
            for canonical in canonical_claims():
                drawn = vectors[canonical.claim_id][j]
                if drawn == ABSENT:
                    continue
                draw_claims.append(canonical.model_copy(update={"status": ClaimStatus(drawn)}))
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
