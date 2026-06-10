"""Hand-authored MOCK data for the IVG-KG dashboard mockup (offline, deterministic).

One coherent scenario — *"When was Frédéric Chopin's father born?"* — authored to
exercise every status (Retrieved / Supportable / Fabricated), the spurious path,
the gap-repair, and the §4.8 single-run and multi-run diagnostics across
{full, content-absent, knowledge-absent} over N in {5, 10, 20} runs.

This is MOCK ONLY: no model, no SPARQL, no network. The grounding backend stays a
stub; these fixtures stand in for what the real precompute would emit. Claims are
NOT aligned across runs (§4.8); only stable KG-item IDs are.

Public surface:
  mock_grounding_run()           -> the displayed single-run answer (rich claims)
  mock_single_run_summary()      -> SingleRunStatusSummary for that answer (no SE)
  mock_subgraph_elements()       -> dash-cytoscape elements (via the real graph_store)
  mock_grading_reference()       -> the never-ablated reference (KG-full + content labels)
  build_condition_runset(n,cond) -> list[GroundingRun] : the N runs of one condition
  build_runset(n)                -> list[GroundingRun] : N runs x the three conditions
  mock_answer_diagnostics(n,cond)-> multi-run AnswerDiagnostics for one condition
  mock_condition_diagnostics(n)  -> {condition: AnswerDiagnostics} : the withhold shift
  repair_result(present,injected)-> RepairResult : the edit-the-KG flip count
  CLAIM_SPANS                    -> {claim_id: substring of answer_text} for inline colouring
  QUESTION, ANSWER_TEXT, ERROR_RATES, N_CHOICES
"""
from __future__ import annotations

from ivg_kg.data.graph_store import nx_to_cyto_elements
from ivg_kg.diagnostics import aggregate_runset, single_run_summary
from ivg_kg.schema import (
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
    RepairResult,
    SingleRunStatusSummary,
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
        # NB: the father's date of birth (P569) is a GAP -- absent from the base KG
        # (the gap-repair target). It enters only when the analyst adds it (§4.4).
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
    """dash-cytoscape elements for the base edited KG (the overview; date is a gap)."""
    return editable_elements(None)


_PROP_LABELS: dict[str, str] = {
    p[0]: p[1] for p in (P_FATHER, P_DOB, P_POB, P_COUNTRY, P_NOTABLE)
}


def kg_item_label(item: str) -> str:
    """Human-readable label for a support-frequency KG-item id (entity or triplet)."""
    if "|" in item:  # triplet key "<subj>|<prop>|<obj>"
        s, p, o = item.split("|")
        return f"{_NODE_LABELS.get(s, s)} -[{_PROP_LABELS.get(p, p)}]-> {_NODE_LABELS.get(o, o)}"
    return _NODE_LABELS.get(item, item)


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
# Canonical claims (the displayed single-run answer) — with support paths.
# Each grounded claim carries its SUPPORT PATH in grounding_path (the KG items
# the verdict rests on); a DIRECT_TRIPLE claim gets a single-edge path so that
# support-frequency (§4.8) reads uniformly. FABRICATED claims carry no path.
# ---------------------------------------------------------------------------
def _direct_path(subj: str, prop: tuple[str, str], obj: str, obj_label: str) -> GroundingPath:
    return GroundingPath(edges=[_pe(subj, prop, obj, obj_label)], node_ids=[subj, obj])


def canonical_claims() -> list[ClaimRecord]:
    """The six canonical claims of the displayed single-run answer (fresh each call)."""
    empty_path = GroundingPath(edges=[], node_ids=[])
    return [
        # c1 — RETRIEVED via direct triple P22 (father).
        ClaimRecord(
            claim_id="c1",
            text="Frédéric Chopin's father was Nicolas Chopin",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            linked_entities=[_ent(FCHOPIN), _ent(NCHOPIN)],
            grounding_path=_direct_path(FCHOPIN, P_FATHER, NCHOPIN, "Nicolas Chopin"),
            entailment_score=0.97,
        ),
        # c2 — RETRIEVED via direct triple P19 (place of birth).
        ClaimRecord(
            claim_id="c2",
            text="Nicolas Chopin was born in Marainville-sur-Madon",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            linked_entities=[_ent(NCHOPIN), _ent(MARAIN)],
            grounding_path=_direct_path(NCHOPIN, P_POB, MARAIN, "Marainville-sur-Madon"),
            entailment_score=0.95,
        ),
        # c3 — FABRICATED: the KG holds no usable birth-date fact, so the model's
        # date does not ground (the gap-repair target). No support path.
        ClaimRecord(
            claim_id="c3",
            text="Nicolas Chopin was born on 17 June 1771",
            status=ClaimStatus.FABRICATED, support_source=SupportSource.NONE,
            linked_entities=[_ent(NCHOPIN)],
            grounding_path=empty_path, entailment_score=0.18,
        ),
        # c4 — SUPPORTABLE, GENUINE path: father born in France (P19 → P17).
        ClaimRecord(
            claim_id="c4",
            text="Chopin's father was born in France",
            status=ClaimStatus.REASONED_SUPPORTABLE, support_source=SupportSource.MULTI_HOP_PATH,
            linked_entities=[_ent(NCHOPIN), _ent(FRANCE)],
            grounding_path=GroundingPath(
                edges=[
                    _pe(NCHOPIN, P_POB, MARAIN, "Marainville-sur-Madon"),
                    _pe(MARAIN, P_COUNTRY, FRANCE, "France"),
                ],
                node_ids=[NCHOPIN, MARAIN, FRANCE],
            ),
            entailment_score=0.86,
        ),
        # c5 — SUPPORTABLE but FLAGGED spurious: path reaches France via the FATHER's
        # birthplace, not Chopin's own (relation/value illegitimacy).
        ClaimRecord(
            claim_id="c5",
            text="Frédéric Chopin was born in France",
            status=ClaimStatus.REASONED_SUPPORTABLE, support_source=SupportSource.MULTI_HOP_PATH,
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
            spurious_reason=_SPURIOUS_REASON,
        ),
        # c6 — RETRIEVED via direct triple P800 (notable work).
        ClaimRecord(
            claim_id="c6",
            text="Chopin is known for his Nocturnes",
            status=ClaimStatus.RETRIEVED, support_source=SupportSource.DIRECT_TRIPLE,
            linked_entities=[_ent(FCHOPIN), _ent(NOCT)],
            grounding_path=_direct_path(FCHOPIN, P_NOTABLE, NOCT, "Nocturnes"),
            entailment_score=0.93,
        ),
    ]


_SPURIOUS_REASON = (
    "relation/value illegitimacy: the path reaches France via the father's "
    "place of birth (P22→P19→P17), not the subject's own birthplace (P19) — "
    "Chopin was born in Żelazowa Wola, Poland."
)


# Inline answer-text spans (substrings) per claim, for status-coloured highlighting.
# c5 is inferential (no contiguous span) → claim list only.
CLAIM_SPANS: dict[str, str] = {
    "c1": "Frédéric Chopin's father was Nicolas Chopin",
    "c3": "born on 17 June 1771",
    "c2": "Marainville-sur-Madon",
    "c4": "France",
    "c6": "Chopin is known for his Nocturnes",
}


def mock_grounding_run() -> GroundingRun:
    """The displayed single-run answer (FULL condition, the rich canonical claims)."""
    return GroundingRun(
        run_id="chopin-full-0", question=QUESTION, answer_text=ANSWER_TEXT,
        slice="books", phase="A", condition=Condition.FULL, sample_index=0,
        claims=canonical_claims(), grading_reference_id="chopin-mock-v1",
        error_rates=dict(ERROR_RATES),
    )


def mock_single_run_summary() -> SingleRunStatusSummary:
    """Single-run status counts + percentages for the displayed answer (no SE; §4.8)."""
    return single_run_summary(mock_grounding_run())


# ---------------------------------------------------------------------------
# Multi-run model (#5): N runs per condition. Claims are NOT aligned across runs;
# each run independently samples, per fact, whether the generator states it
# correctly ("ok" -> its grounded status + support path), states a WRONG value
# ("fab" -> FABRICATED, no support), or omits it ("absent"). Withholding evidence
# from the GENERATION context (content- / knowledge-absent) shifts the per-run
# status distribution toward fabrication WITHOUT relabelling true claims — grading
# is always against the FULL reference. This is the withhold-from-context layer
# (§4.4(a)); its result is the distribution SHIFT across conditions.
# ---------------------------------------------------------------------------
_OK, _FAB, _ABS = "ok", "fab", "absent"
_OUTCOME_ORDER = [_OK, _FAB, _ABS]

# Wrong-value surface text a run emits when a fact is fabricated.
_FAB_TEXT: dict[str, str] = {
    "c1": "Frédéric Chopin's father was Marc Chopin",
    "c2": "Nicolas Chopin was born in Nancy",
    "c3": "Nicolas Chopin was born on 17 June 1771",
    "c4": "Chopin's father was born in Poland",
    "c5": "Frédéric Chopin was born in Poland",
    "c6": "Chopin is known for his symphonies",
}

# fact id -> condition -> {ok|fab|absent: count} (each sums to _MAX_DRAWS). FULL is
# mostly grounded (c3 is the standing date fabrication); knowledge-absent collapses
# the structural / path facts into fabrication or omission; content-absent shifts
# only mildly (structure survives content withholding).
_OUTCOME_COUNTS: dict[str, dict[str, dict[str, int]]] = {
    "c1": {
        Condition.FULL.value: {_OK: 18, _FAB: 1, _ABS: 1},
        Condition.CONTENT_ABSENT.value: {_OK: 15, _FAB: 3, _ABS: 2},
        Condition.KNOWLEDGE_ABSENT.value: {_OK: 4, _FAB: 12, _ABS: 4},
    },
    "c2": {
        Condition.FULL.value: {_OK: 18, _FAB: 1, _ABS: 1},
        Condition.CONTENT_ABSENT.value: {_OK: 13, _FAB: 5, _ABS: 2},
        Condition.KNOWLEDGE_ABSENT.value: {_OK: 5, _FAB: 11, _ABS: 4},
    },
    "c3": {  # the date: fabricated under every condition (the KG lacks a usable date)
        Condition.FULL.value: {_FAB: 16, _ABS: 4},
        Condition.CONTENT_ABSENT.value: {_FAB: 16, _ABS: 4},
        Condition.KNOWLEDGE_ABSENT.value: {_FAB: 18, _ABS: 2},
    },
    "c4": {
        Condition.FULL.value: {_OK: 16, _ABS: 4},
        Condition.CONTENT_ABSENT.value: {_OK: 11, _FAB: 5, _ABS: 4},
        Condition.KNOWLEDGE_ABSENT.value: {_OK: 4, _FAB: 8, _ABS: 8},
    },
    "c5": {  # spurious-supportable France
        Condition.FULL.value: {_OK: 12, _FAB: 8},
        Condition.CONTENT_ABSENT.value: {_OK: 8, _FAB: 12},
        Condition.KNOWLEDGE_ABSENT.value: {_OK: 2, _FAB: 14, _ABS: 4},
    },
    "c6": {
        Condition.FULL.value: {_OK: 18, _FAB: 1, _ABS: 1},
        Condition.CONTENT_ABSENT.value: {_OK: 15, _FAB: 3, _ABS: 2},
        Condition.KNOWLEDGE_ABSENT.value: {_OK: 3, _FAB: 11, _ABS: 6},
    },
}

_WITHHOLD_CONDITIONS = [
    Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT,
]


def _spread(counts: dict[str, int], order: list[str]) -> list[str]:
    """Deterministically spread `counts` into a length-sum(counts) sequence.

    Lowest placed/target ratio wins each slot (ties broken by `order`), so a
    minority value is distributed across the sequence — making N-prefixes of
    5/10/20 give meaningfully different fractions (the N selector does something).
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


def build_condition_runset(n: int, condition: Condition) -> list[GroundingRun]:
    """The N runs for one condition (claims NOT aligned across runs; §4.8)."""
    n = max(1, min(n, _MAX_DRAWS))
    templates = {c.claim_id: c for c in canonical_claims()}
    outcome_seqs = {
        cid: _spread(_OUTCOME_COUNTS[cid][condition.value], _OUTCOME_ORDER)
        for cid in _OUTCOME_COUNTS
    }
    runs: list[GroundingRun] = []
    for j in range(n):
        claims: list[ClaimRecord] = []
        for cid in ("c1", "c2", "c3", "c4", "c5", "c6"):
            outcome = outcome_seqs[cid][j]
            if outcome == _ABS:
                continue
            tmpl = templates[cid]
            if outcome == _OK and tmpl.status != ClaimStatus.FABRICATED:
                claims.append(tmpl.model_copy(update={"claim_id": f"r{j}-{cid}"}))
            else:  # fab (or a fact whose template is itself fabricated, e.g. c3)
                claims.append(
                    ClaimRecord(
                        claim_id=f"r{j}-{cid}", text=_FAB_TEXT[cid],
                        status=ClaimStatus.FABRICATED, support_source=SupportSource.NONE,
                        linked_entities=list(tmpl.linked_entities),
                        grounding_path=GroundingPath(edges=[], node_ids=[]),
                    )
                )
        runs.append(
            GroundingRun(
                run_id=f"chopin-{condition.value}-{j}", question=QUESTION,
                answer_text=ANSWER_TEXT, slice="books", phase="A",
                condition=condition, sample_index=j, claims=claims,
                grading_reference_id="chopin-mock-v1", error_rates=dict(ERROR_RATES),
            )
        )
    return runs


def build_runset(n: int = _MAX_DRAWS) -> list[GroundingRun]:
    """All N runs under each withhold-from-context condition, concatenated."""
    runs: list[GroundingRun] = []
    for cond in _WITHHOLD_CONDITIONS:
        runs.extend(build_condition_runset(n, cond))
    return runs


def mock_answer_diagnostics(
    n: int = _MAX_DRAWS, condition: Condition = Condition.FULL
) -> AnswerDiagnostics:
    """Multi-run diagnostics for one condition's N runs (default FULL; §4.8)."""
    return aggregate_runset(build_condition_runset(n, condition))


def mock_condition_diagnostics(n: int = _MAX_DRAWS) -> dict[str, AnswerDiagnostics]:
    """Per-condition multi-run diagnostics — the withhold-from-context shift (#5)."""
    return {
        cond.value: aggregate_runset(build_condition_runset(n, cond))
        for cond in _WITHHOLD_CONDITIONS
    }


# ---------------------------------------------------------------------------
# Editing layer with PER-EDIT SCOPE (mock; SPEC-text §4.4 / §4.6)
# ---------------------------------------------------------------------------
# Every edit carries a SCOPE that decides what it touches:
#   - "gen"  (generation only): change ONLY the model's generation context; the
#            grading reference stays FULL. Withhold-from-context (RQ2): removing
#            induces absence-hallucination the verifier can still CATCH; ADDING a
#            fact lets the model state it but the verifier still cannot confirm it.
#   - "both" (generation + verification): change the real KG, so grading uses the
#            EDITED reference. Edit-the-KG (gap-repair): adding the missing date
#            grounds c3; removing blinds the verifier.
# A claim grounds iff its evidence is present in BOTH the generation context AND
# the verification reference; otherwise it is fabricated, with a reason naming the
# missing side. Edits are a single list of records, each:
#   {"op": "add"|"remove", "kind": "triplet"|"entity"|"content", "scope": "gen"|"both",
#    "id":..., "label":..., "description":..., "subject":..., "relation":..., "value":...}
# The father's birth DATE is a GAP -- absent from the base KG (the gap-repair target).
# Deterministic, offline.

# Base structure triples (present in BOTH generation + verification at baseline).
TRIPLES: list[dict] = [
    {"id": "P22", "subj": FCHOPIN, "prop_label": "father", "obj": NCHOPIN,
     "obj_label": "Nicolas Chopin", "literal": False},
    {"id": "P19", "subj": NCHOPIN, "prop_label": "place of birth", "obj": MARAIN,
     "obj_label": "Marainville-sur-Madon", "literal": False},
    {"id": "P17", "subj": MARAIN, "prop_label": "country", "obj": FRANCE,
     "obj_label": "France", "literal": False},
    {"id": "P800", "subj": FCHOPIN, "prop_label": "notable work", "obj": NOCT,
     "obj_label": "Nocturnes", "literal": False},
]
ALL_TRIPLE_IDS: list[str] = [t["id"] for t in TRIPLES]
_TRIPLE_BY_ID: dict[str, dict] = {t["id"]: t for t in TRIPLES}

# Evidence key for the (gap) date-of-birth fact added during repair.
DOB_KEY = "P569"

# Model suggestion that pre-fills the (editable) add-triplet form: the missing date.
SUGGESTED_INJECT: dict = {"subject": NCHOPIN, "relation": "date of birth", "value": DOB_TRUE}
ENTITY_OPTIONS: list[dict] = [
    {"label": _NODE_LABELS[q], "value": q} for q in (FCHOPIN, NCHOPIN, MARAIN, FRANCE, NOCT)
]
SCOPE_LABELS: dict[str, str] = {
    "gen": "generation only", "both": "generation + verification",
}

# claim -> evidence it needs to ground (a date-of-birth fact for c3; structure else).
CLAIM_DEPS: dict[str, frozenset[str]] = {
    "c1": frozenset({"P22"}),
    "c2": frozenset({"P19"}),
    "c3": frozenset({DOB_KEY}),
    "c4": frozenset({"P19", "P17"}),
    "c5": frozenset({"P22", "P19", "P17"}),
    "c6": frozenset({"P800"}),
}
_GROUNDED_STATUS: dict[str, ClaimStatus] = {
    "c1": ClaimStatus.RETRIEVED, "c2": ClaimStatus.RETRIEVED, "c3": ClaimStatus.RETRIEVED,
    "c4": ClaimStatus.REASONED_SUPPORTABLE, "c5": ClaimStatus.REASONED_SUPPORTABLE,
    "c6": ClaimStatus.RETRIEVED,
}


def _triple_key(e: dict) -> str:
    """Evidence key for a triplet edit (the date maps to DOB_KEY)."""
    if e.get("id"):
        return e["id"]
    rel = (e.get("relation") or "").lower()
    return DOB_KEY if "date" in rel else (e.get("relation") or "triple")


def apply_edits(edits: list[dict] | None) -> dict:
    """Fold the edit list into generation + verification views (deterministic).

    Returns the evidence sets seen by the generator vs the verifier, plus display
    bookkeeping (added triples/entities, per-entity content state).
    """
    gen: set[str] = set(ALL_TRIPLE_IDS)
    ver: set[str] = set(ALL_TRIPLE_IDS)
    content_state: dict[str, str] = {}  # entity -> "gen" (withheld) | "both" (removed)
    added_triples: list[dict] = []
    added_entities: list[dict] = []
    for e in edits or []:
        op, kind, scope = e.get("op"), e.get("kind"), e.get("scope", "both")
        if kind == "triplet":
            key = _triple_key(e)
            if op == "remove":
                gen.discard(key)
                if scope == "both":
                    ver.discard(key)
            else:
                gen.add(key)
                if scope == "both":
                    ver.add(key)
                added_triples.append({**e, "key": key})
        elif kind == "content" and op == "remove":
            ent = e.get("id")
            if ent:  # "both" supersedes a prior "gen" removal
                content_state[ent] = "both" if scope == "both" else content_state.get(ent, "gen")
        elif kind == "entity" and op == "add":
            added_entities.append(e)
    return {
        "gen": gen, "ver": ver, "content_state": content_state,
        "added_triples": added_triples, "added_entities": added_entities,
    }


def _status_and_reason(
    deps: frozenset[str], gen: set[str], ver: set[str], grounded: ClaimStatus
) -> tuple[ClaimStatus, str]:
    in_gen, in_ver = deps <= gen, deps <= ver
    if in_gen and in_ver:
        return grounded, "grounded"
    if in_ver and not in_gen:
        return ClaimStatus.FABRICATED, (
            "absence-induced: evidence withheld from the model, but the verifier "
            "still holds it (a wrong claim would be caught)"
        )
    if in_gen and not in_ver:
        return ClaimStatus.FABRICATED, (
            "unverifiable: the model states it, but the verifier's reference no "
            "longer holds it (the verifier is blinded)"
        )
    return ClaimStatus.FABRICATED, "fabricated: evidence absent from generation and verification"


def statuses_with_reasons(edits: list[dict] | None = None) -> dict[str, tuple[ClaimStatus, str]]:
    """Per-claim (status, reason) given the scoped edits (§4.4)."""
    st = apply_edits(edits)
    gen, ver = st["gen"], st["ver"]
    return {
        cid: _status_and_reason(deps, gen, ver, _GROUNDED_STATUS[cid])
        for cid, deps in CLAIM_DEPS.items()
    }


def statuses_for_graph(edits: list[dict] | None = None) -> dict[str, ClaimStatus]:
    """Re-verify the claims given the scoped edits (status only)."""
    return {cid: sr[0] for cid, sr in statuses_with_reasons(edits).items()}


def grounded_count(edits: list[dict] | None = None) -> int:
    """How many of the 6 claims currently ground (not Fabricated)."""
    return sum(1 for s in statuses_for_graph(edits).values() if s != ClaimStatus.FABRICATED)


def repair_result(edits: list[dict] | None = None) -> RepairResult:
    """Repair-leverage: claims that flip FABRICATED -> grounded vs the original answer.

    Baseline = the original answer (no edits): only the date claim (c3) is
    fabricated (the date is a gap). A *generation+verification* add of the date
    grounds c3 (+1); a *generation-only* add does NOT repair it (the verifier still
    cannot confirm it -- it stays fabricated/unverifiable). That contrast is the
    point of the scope toggle.
    """
    baseline = statuses_for_graph(None)
    current = statuses_for_graph(edits)
    repaired = [
        cid for cid, st in current.items()
        if baseline.get(cid) == ClaimStatus.FABRICATED and st != ClaimStatus.FABRICATED
    ]
    adds = [e for e in (edits or []) if e.get("op") == "add"]
    restored = "; ".join(
        f"{e.get('relation') or e.get('label', '?')}"
        f"{' = ' + e['value'] if e.get('value') else ''}"
        f" [{SCOPE_LABELS.get(e.get('scope', 'both'), e.get('scope'))}]"
        for e in adds
    ) or "(no KG additions yet)"
    return RepairResult(
        restored_item=restored, repair_leverage=len(repaired), repaired_claim_ids=repaired,
    )


def removed_triples(edits: list[dict] | None = None) -> list[dict]:
    """Base triples currently withheld from the GENERATION context (for re-add)."""
    gen = apply_edits(edits)["gen"]
    return [t for t in TRIPLES if t["id"] not in gen]


def editable_snapshot(edits: list[dict] | None = None) -> tuple[KGSnapshot, dict, dict]:
    """KGSnapshot for the edited KG + (edge scope_state map, node content_state map).

    Shows the union of generation- and verification-visible triples so that
    generation-only edits stay visible (styled distinctly), plus any added
    entities. scope_state per edge: "both" | "ver_only" (withheld from the model) |
    "gen_only" (model-only, unverified).
    """
    st = apply_edits(edits)
    gen, ver, content_state = st["gen"], st["ver"], st["content_state"]
    edges: list[KGEdge] = []
    edge_scope: dict[str, str] = {}
    node_ids: set[str] = {FCHOPIN}

    def _scope_state(key: str) -> str | None:
        in_g, in_v = key in gen, key in ver
        if in_g and in_v:
            return "both"
        if in_v and not in_g:
            return "ver_only"
        if in_g and not in_v:
            return "gen_only"
        return None  # gone from both -> not shown

    for t in TRIPLES:
        state = _scope_state(t["id"])
        if state is None:
            continue
        node_ids.update({t["subj"], t["obj"]})
        edges.append(KGEdge(
            subject_id=t["subj"], property_id=t["id"], property_label=t["prop_label"],
            object_id=t["obj"], object_label=t["obj_label"], value_type=ValueType.ITEM,
        ))
        edge_scope[f"{t['subj']}-{t['id']}-{t['obj']}"] = state

    for e in st["added_triples"]:
        subj = e.get("subject") or NCHOPIN
        node_ids.add(subj)
        pid = e.get("key", "INJ")
        val = e.get("value", "")
        lit_id = f"lit:string:{val}"
        edges.append(KGEdge(
            subject_id=subj, property_id=pid, property_label=e.get("relation", "added"),
            object_id=None, object_label=val, value_type=ValueType.STRING,
        ))
        edge_scope[f"{subj}-{pid}-{lit_id}"] = "both" if e.get("scope") == "both" else "gen_only"

    nodes: list[KGNode] = []
    for q in _NODE_LABELS:
        if q not in node_ids:
            continue
        # content (description) is dropped when removed from the true KG ("both");
        # a generation-only content removal keeps it in the reference (still shown).
        desc = None if content_state.get(q) == "both" else _NODE_DESCRIPTIONS.get(q)
        nodes.append(KGNode(id=q, label=_NODE_LABELS[q], description=desc))
    for e in st["added_entities"]:
        eid = e.get("id") or e.get("label", "new-entity")
        nodes.append(KGNode(id=eid, label=e.get("label", eid), description=e.get("description")))
    return (
        KGSnapshot(snapshot_id="chopin-edit", slice="books", domain_qid=FCHOPIN,
                   nodes=nodes, edges=edges, meta={}),
        edge_scope,
        content_state,
    )


def editable_elements(edits: list[dict] | None = None) -> list[dict]:
    """Cytoscape elements for the edited KG; edges/nodes tagged with scope state."""
    snap, edge_scope, content_state = editable_snapshot(edits)
    added_entity_ids = {
        (e.get("id") or e.get("label")) for e in apply_edits(edits)["added_entities"]
    }
    els = nx_to_cyto_elements(snap)
    for el in els:
        data = el["data"]
        if "source" in data:  # edge
            data["scope_state"] = edge_scope.get(data["id"], "both")
        else:  # node
            if data["id"] in content_state:
                data["content_state"] = content_state[data["id"]]
            if data["id"] in added_entity_ids:
                data["added"] = "1"
    return els


def claim_text_by_id() -> dict[str, str]:
    return {c.claim_id: c.text for c in canonical_claims()}
