"""GR6 -- Entity linking + property-alias/inverse canonicalization (SPEC-text 4.3(B)).

This module is the SEAM between claim extraction (GR5) and the classifier (GR8)
on the verifier side. Two coupled responsibilities:

  1. EntityLinker: resolves surface mention strings to stable KG node QIDs in the
     snapshot. Linking aligns KG-ITEM IDs, NOT claims. Out-of-slice mentions ->
     None (unresolved, distinct from FABRICATED status).

  2. PropertyCanon: maps relation surface strings and property IDs to one canonical
     property ID, and flips INVERSE-PAIR triples to a single canonical orientation.
     This gives phrasing-stable and direction-stable triplet keys so that
     support-frequency (section 4.8) aggregates the SAME triplet across runs
     regardless of how the surface string or edge direction varies.

Design invariants (SPEC-text 4.3(B)):
  - DETERMINISTIC: identical inputs -> identical outputs. No random, no I/O in the
    default path. Per-instance caches.
  - OFFLINE DEFAULT: LabelAliasIndex builds an in-memory index once at construction;
    never downloads anything. ReFinEDLinker lazy-loads the model only on first call
    when no resolve= seam is provided; the module is fully importable without it.
  - BOOKS-FIRST: no image-axis imports or code.
  - ASCII only: no unicode in identifiers, comments, or docstrings.

Canonical triplet key format: "{subject_id}|{property_id}|{object_id}" -- format-
identical to diagnostics.triplet_key, but computed over the CANONICALIZED triple.
Once the classifier stores canonical-oriented edges, the existing diagnostics.triplet_key
over them is already stable. GR6 is purely additive; diagnostics.py is NOT modified.
"""

from __future__ import annotations

import json
import re
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ivg_kg.schema import KGSnapshot, LinkedEntity

__all__ = [
    "PropertyCanon",
    "BaseEntityLinker",
    "LabelAliasIndex",
    "ReFinEDLinker",
    "make_entity_linker",
]

# ---------------------------------------------------------------------------
# Default path resolution (mirrors gold_qa.py pattern)
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__)
# Resolve from the installed package location up to the repo root, then into data/.
# The package lives at src/ivg_kg/grounding/link.py; data is at <repo>/data/.
# Walk up four levels: grounding -> ivg_kg -> src -> <repo_root>.
_DEFAULT_SLICE_DIR = (
    _THIS_FILE.parent.parent.parent.parent / "data" / "frozen" / "books" / "books-p0-v1"
)


# ---------------------------------------------------------------------------
# PropertyCanon -- artifact loader and canonicalization helper
# ---------------------------------------------------------------------------


class _InversePairEntry(BaseModel):
    """One declared inverse pair from the canon table JSON."""

    property: str  # non-canonical PID (e.g. P156 "followed by")
    inverse: str  # canonical PID (e.g. P155 "follows")


class PropertyCanon:
    """Property-alias and inverse-orientation canonicalization table.

    Load with PropertyCanon.load(slice_dir) to read the committed JSON artifact
    for a slice. The table maps:
      - relation surface strings to canonical property IDs
      - property IDs to themselves (identity entries in the JSON)
    and declares inverse pairs so that both directions of a reversible edge
    (e.g. P155 "follows" / P156 "followed by") collapse to one stable key.

    Canonical direction rule: the canonical member of an inverse pair is the
    one declared as 'inverse' in the JSON (i.e. the LOWER-numbered PID). The
    non-canonical member is declared under 'property'. When a triple carries the
    non-canonical PID, canonical_triple() swaps subject<->object and replaces the
    PID with the canonical one.

    canonical_triplet_key() is format-compatible with diagnostics.triplet_key:
    both produce "{subject_id}|{property_id}|{object_id}", but this method
    operates on the canonicalized triple.
    """

    def __init__(
        self,
        alias_map: dict[str, str],
        non_canonical_to_canonical: dict[str, str],
    ) -> None:
        # Maps any alias/pid surface -> canonical pid.
        self._alias_map = alias_map
        # Maps non-canonical PID -> canonical PID (for inverse-pair swap).
        self._nc_to_c = non_canonical_to_canonical

    @classmethod
    def load(cls, slice_dir: Path | str | None = None) -> PropertyCanon:
        """Load and validate the property_canon.json artifact for a slice.

        Parameters
        ----------
        slice_dir:
            Directory containing property_canon.json. Defaults to the
            books-p0-v1 slice directory inside data/frozen/books/books-p0-v1/.
            Mirrors the path-resolution pattern used by gold_qa.load_gold_qa_set.

        Returns
        -------
        PropertyCanon
            Populated from the JSON artifact.

        Raises
        ------
        FileNotFoundError
            When property_canon.json is absent from slice_dir.
        json.JSONDecodeError
            When the file cannot be parsed.
        """
        dir_path = Path(slice_dir) if slice_dir is not None else _DEFAULT_SLICE_DIR
        artifact = dir_path / "property_canon.json"
        text = artifact.read_text(encoding="utf-8")
        data = json.loads(text)

        alias_map: dict[str, str] = dict(data.get("relation_aliases", {}))

        # Build the non-canonical -> canonical PID map from inverse_pairs.
        nc_to_c: dict[str, str] = {}
        for entry_raw in data.get("inverse_pairs", []):
            entry = _InversePairEntry.model_validate(entry_raw)
            nc_to_c[entry.property] = entry.inverse

        return cls(alias_map=alias_map, non_canonical_to_canonical=nc_to_c)

    def canonical_property(self, relation_surface_or_pid: str) -> str | None:
        """Map a relation surface string or property ID to the canonical property ID.

        Parameters
        ----------
        relation_surface_or_pid:
            A relation surface string (e.g. "written by") or a property ID
            (e.g. "P50"). Property IDs are present as identity entries in the
            alias map (P50 -> P50).

        Returns
        -------
        str | None
            Canonical property ID, or None if the input is not in the table.
        """
        return self._alias_map.get(relation_surface_or_pid)

    def canonical_triple(
        self,
        subject_id: str,
        property_id: str,
        object_id: str | None,
    ) -> tuple[str, str, str | None]:
        """Return the canonical form of (subject, property, object).

        If property_id is the non-canonical member of a declared inverse pair
        (e.g. P156 "followed by"), the triple is FLIPPED:
          - subject and object are swapped
          - property_id is replaced with the canonical inverse (e.g. P155)
        so that (A, P156, B) and (B, P155, A) produce the same canonical triple
        (B, P155, A).

        If property_id is already canonical (or not in any inverse pair), the
        triple is returned unchanged.

        This method is IDEMPOTENT: applying it twice gives the same result as
        once.

        Parameters
        ----------
        subject_id, property_id, object_id:
            The raw triple to canonicalize. object_id may be None (non-item
            values such as quantities/times).

        Returns
        -------
        tuple[str, str, str | None]
            The canonical (subject, property, object) triple.
        """
        canon_pid = self._nc_to_c.get(property_id)
        if canon_pid is not None and object_id is not None:
            # Flip: promote object to subject, use the canonical (inverse) PID.
            return object_id, canon_pid, subject_id
        return subject_id, property_id, object_id

    def canonical_triplet_key(
        self,
        subject_id: str,
        property_id: str,
        object_id: str | None,
    ) -> str:
        """Return the pipe-separated triplet key for the canonical triple.

        Format: "{subject_id}|{property_id}|{object_id}". This is format-
        identical to diagnostics.triplet_key but computed over the canonicalized
        triple, giving stable keys regardless of surface phrasing or edge
        direction.

        Parameters
        ----------
        subject_id, property_id, object_id:
            The raw triple (before canonicalization).

        Returns
        -------
        str
            Canonical triplet key in the form "s|p|o".
        """
        s, p, o = self.canonical_triple(subject_id, property_id, object_id)
        return f"{s}|{p}|{o}"


# ---------------------------------------------------------------------------
# Shared text normalization (mirrors slice._normalise_text exactly)
# ---------------------------------------------------------------------------


def _normalise_text(s: str) -> str:
    """Lowercase, strip, NFC-normalise. Mirrors slice._normalise_text."""
    return unicodedata.normalize("NFC", s.strip().lower())


# ---------------------------------------------------------------------------
# BaseEntityLinker ABC
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "was",
        "were",
        "are",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "and",
        "or",
        "but",
        "with",
        "by",
        "from",
        "it",
        "its",
        "this",
        "that",
        "which",
        "who",
        "whom",
        "what",
        "when",
        "where",
        "how",
        "not",
        "no",
        "as",
        "also",
        "both",
    }
)


class BaseEntityLinker(ABC):
    """Abstract entity linker.

    Subclasses implement _link(mention) -> LinkedEntity | None.
    link() wraps _link with a per-instance cache keyed by the normalized
    mention string. Out-of-slice mentions return None (unresolved).

    Contract:
      - link(mention) -> LinkedEntity | None; deterministic; cached.
      - Identical mention -> identical result every call.
      - None means unresolved (not in this slice); distinct from FABRICATED.
      - link_text(text) -> (linked, unresolved): scan free text for entity
        labels, return matched entities and uncovered content tokens.
    """

    def __init__(self) -> None:
        # Per-instance cache: normalized mention -> LinkedEntity | None.
        # Unbounded by design; one linker instance per pipeline sweep is fine.
        # Not thread-safe -- the pipeline is single-threaded and deterministic.
        self._cache: dict[str, LinkedEntity | None] = {}

    def link(self, mention: str) -> LinkedEntity | None:
        """Resolve a surface mention to a KGNode QID (cached).

        Parameters
        ----------
        mention:
            Surface entity mention string (e.g. "Beloved").

        Returns
        -------
        LinkedEntity | None
            Resolved entity with id, label, description, link_score; or None
            when the mention is unresolved (out-of-slice). The returned instance
            is a SHARED cached object; callers must treat it as read-only and
            must not mutate its fields.
        """
        key = _normalise_text(mention)
        if key in self._cache:
            return self._cache[key]
        result = self._link(mention)
        self._cache[key] = result
        return result

    @abstractmethod
    def _link(self, mention: str) -> LinkedEntity | None:
        """Resolve a surface mention without caching. Subclasses implement this."""
        ...

    def link_text(self, text: str) -> tuple[list[LinkedEntity], list[str]]:
        """Scan free text for entity label mentions and return matched + unresolved.

        Mirrors the semantics of slice.link_entities: node labels are found by
        substring scan (normalized); each matching node yields one LinkedEntity.
        Tokens in text not covered by any matched label are returned as
        unresolved strings (best-effort; not a FABRICATED verdict).

        Contrast with link(): link() returns a single best match with a graded
        substring score in (0, 1]; link_text() returns every label-overlap match
        at a flat score of 1.0 (mirrors slice.link_entities, not link()).

        Parameters
        ----------
        text:
            Free-form text (e.g. a claim sentence).

        Returns
        -------
        (linked, unresolved)
            linked: list[LinkedEntity] for each matched node.
            unresolved: list[str] content tokens not covered by any match.
        """
        if not text or not text.strip():
            return [], []

        norm_text = _normalise_text(text)
        linked: list[LinkedEntity] = []
        matched_labels: set[str] = set()

        # Iterate over nodes in stable order (snapshot.nodes order).
        for entity in self._iter_nodes():
            norm_label = _normalise_text(entity.label)
            if not norm_label:
                continue
            # Match: label is a substring of text, or text fragment is in label.
            if norm_label in norm_text or norm_text in norm_label:
                linked.append(
                    LinkedEntity(
                        id=entity.id,
                        label=entity.label,
                        description=entity.description,
                        link_score=1.0,
                    )
                )
                matched_labels.add(norm_label)

        # Collect tokens in the text not covered by any matched label.
        tokens = re.findall(r"[A-Za-z]+", norm_text)
        covered: set[str] = set()
        for lbl in matched_labels:
            for tok in re.findall(r"[A-Za-z]+", lbl):
                covered.add(tok)
        unresolved = sorted({t for t in tokens if t not in covered and t not in _STOP_WORDS})
        return linked, unresolved

    @abstractmethod
    def _iter_nodes(self) -> list[Any]:
        """Return the iterable of KGNode objects for this linker.

        Used by link_text to scan node labels. Subclasses provide this.
        """
        ...


# ---------------------------------------------------------------------------
# LabelAliasIndex -- offline deterministic linker (default)
# ---------------------------------------------------------------------------


class LabelAliasIndex(BaseEntityLinker):
    """Deterministic offline entity linker using a normalized-label index.

    Builds a mapping from normalized label -> KGNode ONCE at construction.
    No I/O or model downloads. Suitable for CI and offline use.

    _link(mention) algorithm:
      1. Exact normalized-label match: link_score = 1.0.
      2. Best-substring/containment match with a deterministic score in (0, 1]:
         score = len(norm_label) / max(len(norm_label), len(norm_mention)).
      3. No match: None (unresolved).

    For link_text(), all nodes whose normalized label appears in the text (or
    vice versa) are returned with score 1.0, mirroring slice.link_entities.
    """

    def __init__(self, snapshot: KGSnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot
        # Build normalized label -> node index once.
        self._label_index: dict[str, Any] = {}
        for node in snapshot.nodes:
            norm = _normalise_text(node.label)
            if norm:
                # On collision: first node wins (deterministic, stable order).
                if norm not in self._label_index:
                    self._label_index[norm] = node

    def _iter_nodes(self) -> list[Any]:
        return self._snapshot.nodes

    def _link(self, mention: str) -> LinkedEntity | None:
        """Resolve mention to a node via normalized-label lookup.

        Exact match first (score 1.0); then best-substring match (score in (0,1]).
        """
        norm = _normalise_text(mention)
        if not norm:
            return None

        # Exact match.
        if norm in self._label_index:
            node = self._label_index[norm]
            return LinkedEntity(
                id=node.id,
                label=node.label,
                description=node.description,
                link_score=1.0,
            )

        # Substring/containment match: find nodes whose label is contained in
        # the mention or vice versa. Pick the best score deterministically.
        best_node = None
        best_score = 0.0
        for norm_label, node in self._label_index.items():
            if norm_label in norm or norm in norm_label:
                # Score: length of the shorter string / length of the longer.
                score = len(norm_label) / max(len(norm_label), len(norm))
                if score > best_score or (
                    score == best_score and best_node is not None and node.id < best_node.id
                ):
                    best_score = score
                    best_node = node

        if best_node is not None and best_score > 0.0:
            return LinkedEntity(
                id=best_node.id,
                label=best_node.label,
                description=best_node.description,
                link_score=best_score,
            )

        return None


# ---------------------------------------------------------------------------
# ReFinEDLinker -- optional lazy seam for neural entity linking
# ---------------------------------------------------------------------------


class ReFinEDLinker(BaseEntityLinker):
    """Optional ReFinED-backed entity linker with an injectable resolve seam.

    When resolve= is provided (test/seam path), it is called directly and NO
    ReFinED model is imported or loaded. When resolve= is None, the ReFinED
    model is lazy-loaded on the first _link() call (live path, pragma: no cover).

    _link(mention) maps a mention string to a QID via the resolve function,
    then looks the QID up in the snapshot. QIDs not in the snapshot -> None
    (unresolved: the entity is not in this slice).

    Args:
        snapshot:  The KGSnapshot to look QIDs up in.
        resolve:   Optional callable(mention: str) -> str | None. If provided,
                   used as the resolve function; no ReFinED import occurs.
        model_id:  Optional ReFinED model ID for the lazy-load path. Ignored
                   when resolve= is provided.
    """

    def __init__(
        self,
        snapshot: KGSnapshot,
        *,
        resolve: Callable[[str], str | None] | None = None,
        model_id: str | None = None,
    ) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._resolve = resolve
        self._model_id = model_id
        self._refined_model: Any = None  # lazy-loaded only on live path
        # Build QID -> node index for fast lookup.
        self._qid_index: dict[str, Any] = {n.id: n for n in snapshot.nodes}

    def _iter_nodes(self) -> list[Any]:
        return self._snapshot.nodes

    def _load(self) -> None:  # pragma: no cover
        """Lazy-load ReFinED model. Only called when resolve= is None and
        _link() is first invoked. Imports are deferred so the module is
        importable with no model present.
        """
        from refined.inference.processor import Refined  # noqa: PLC0415 -- intentionally lazy

        model_id = self._model_id or "wikipedia_model_with_numbers"
        self._refined_model = Refined.from_pretrained(
            model_name=model_id,
            entity_set="wikidata",
        )

    def _link(self, mention: str) -> LinkedEntity | None:
        """Resolve mention -> QID via resolve seam or lazy ReFinED, then snapshot lookup."""
        if self._resolve is not None:
            qid = self._resolve(mention)
        else:  # pragma: no cover
            if self._refined_model is None:
                self._load()
            spans = self._refined_model.process_text(mention)
            qid = spans[0].predicted_entity.wikidata_entity_id if spans else None

        if qid is None:
            return None

        node = self._qid_index.get(qid)
        if node is None:
            return None  # QID not in this slice -> unresolved

        return LinkedEntity(
            id=node.id,
            label=node.label,
            description=node.description,
            link_score=1.0,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_entity_linker(name: str, snapshot: KGSnapshot, **kwargs: Any) -> BaseEntityLinker:
    """Return the entity linker selected by name.

    Valid selectors:
        "label_alias" -> LabelAliasIndex (offline, default per config.linker)
        "refined"     -> ReFinEDLinker (injectable seam or lazy ReFinED)

    Raises ValueError for unknown selectors.

    Parameters
    ----------
    name:
        Selector string. Matches GroundingConfig.linker values.
    snapshot:
        The KGSnapshot to link against.
    **kwargs:
        Forwarded to the concrete linker constructor (e.g. resolve= for
        ReFinEDLinker).

    Returns
    -------
    BaseEntityLinker
        Configured linker instance.
    """
    if name == "label_alias":
        return LabelAliasIndex(snapshot)
    if name == "refined":
        return ReFinEDLinker(snapshot, **kwargs)
    raise ValueError(
        f"Unknown entity linker selector: {name!r}. Valid options: 'label_alias', 'refined'."
    )
