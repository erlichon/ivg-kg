"""DA4 — Grading-reference assembly.

Builds the `GradingReference` — the never-ablated ground truth the classifier
grades every claim against (SPEC-text §3.2 invariant).  This module provides:

  - ``assemble_reference`` — construct a GradingReference from a KG-full
    snapshot plus curated ContentLabels.  The snapshot MUST be KG-full (never
    an ablated subgraph); perturbations act on the generation context elsewhere.

  - ``make_text_content_label`` — low-level helper to stamp a single content-
    only TEXT fact as a ContentLabel.

  - ``author_books_content_labels`` — batch authoring helper for curators.
    Accepts ``list[tuple[entity_id, fact, source]]`` and returns TEXT
    ContentLabels in the same order as the input.  Books-only, TEXT modality
    only (Invariant #8).

  - ``reference_id`` — a stable, deterministic id for a GradingReference,
    derived from snapshot_id + a sorted hash of the content labels.

  - ``freeze_reference`` / ``load_reference`` — JSON-only persistence that
    mirrors the SPEC-text §3.3 frozen-slice layout:
        <dir>/snapshot.json          (via DA2's freeze_snapshot)
        <dir>/content_labels.json    (deterministic JSON array)

Invariant #1 (SPEC-text §3.2): this module builds the FULL, never-ablated
reference.  No withhold/ablate API is exposed here.

Books-first gate: only TEXT modality labels are authored in P0 (books slice).
IMAGE labels are image-axis concerns (artwork-primary / taxa-fallback) handled
post-M-BOOKS in the separate image specs/tasks.

Imports: ivg_kg.schema, ivg_kg.data.graph_store, stdlib only.
No provider SDKs, no network, no pickle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ivg_kg.data.graph_store import freeze_snapshot, load_snapshot
from ivg_kg.schema import ContentLabel, GradingReference, KGSnapshot, Modality

# ---------------------------------------------------------------------------
# Core assembly
# ---------------------------------------------------------------------------


def assemble_reference(
    snapshot: KGSnapshot,
    content_labels: list[ContentLabel],
) -> GradingReference:
    """Construct a GradingReference from a KG-full snapshot + curated ContentLabels.

    The snapshot passed in MUST be the KG-full (never an ablated subgraph).
    Perturbations that withhold triples or text content act solely on the
    generation context (GenerationContext) and never on this reference.  That
    separation is the load-bearing invariant of SPEC-text §3.2.

    Parameters
    ----------
    snapshot:
        KG-full snapshot for the domain entity.  Must not be an ablated
        subgraph.
    content_labels:
        Curated content-only labels (TEXT for books; IMAGE for the gated image
        axis, post-M-BOOKS).  May be empty for snapshots with no content-only facts.

    Returns
    -------
    GradingReference containing the snapshot and content labels.
    """
    return GradingReference(snapshot=snapshot, content_labels=content_labels)


# ---------------------------------------------------------------------------
# Books content-only-label authoring helpers (P0 / TEXT only)
# ---------------------------------------------------------------------------


def make_text_content_label(
    entity_id: str,
    fact: str,
    *,
    source: str = "description",
) -> ContentLabel:
    """Create a single TEXT-modality ContentLabel for a content-only book fact.

    Books content-only facts are facts the triples omit but the description
    carries: genre/form ("is this a play or a novel?"), tradition/affiliation,
    scope/structure ("how many volumes?"), and descriptive role (SPEC-text §4.1).

    Stamping modality=TEXT is done here unconditionally.  Do NOT use this
    helper to author IMAGE labels; those belong to the gated image axis
    (artwork-primary / taxa-fallback) and are handled post-M-BOOKS.

    Parameters
    ----------
    entity_id:
        Wikidata QID of the book entity (e.g. "Q571").
    fact:
        The content-only textual fact string (e.g. "is a play").
    source:
        Provenance of the fact; defaults to ``"description"`` (the Wikipedia
        description field).  Pass a custom string when the fact comes from
        another structured field.

    Returns
    -------
    ContentLabel with modality=TEXT.
    """
    return ContentLabel(
        entity_id=entity_id,
        modality=Modality.TEXT,
        fact=fact,
        source=source,
    )


def author_books_content_labels(
    facts: list[tuple[str, str, str]],
) -> list[ContentLabel]:
    """Batch authoring helper: produce TEXT ContentLabels from a fact list.

    Accepts a list of ``(entity_id, fact, source)`` triples and returns
    one ``ContentLabel`` per entry with ``modality=TEXT``, in the SAME order
    as the input (deterministic; no sorting).  This is hand-curation support,
    not extraction — the caller controls ordering.

    Only TEXT modality labels are produced here (books-first gate).  Do NOT pass
    image-derived facts; those belong to the gated image axis (artwork-primary /
    taxa-fallback), built post-M-BOOKS.

    Parameters
    ----------
    facts:
        List of ``(entity_id, fact, source)`` tuples.  Each tuple describes
        one content-only textual fact for a book entity.

        Example::

            [
                ("Q571", "is a play", "description"),
                ("Q571", "central to the Western tradition", "description"),
                ("Q42",  "comprises three volumes", "infobox"),
            ]

    Returns
    -------
    list[ContentLabel] with modality=TEXT, in the same order as *facts*.
    """
    return [
        make_text_content_label(entity_id, fact, source=source)
        for entity_id, fact, source in facts
    ]


# ---------------------------------------------------------------------------
# Stable reference identity
# ---------------------------------------------------------------------------


def reference_id(reference: GradingReference) -> str:
    """Derive a stable, deterministic id for a GradingReference.

    The id is derived from:
      1. The snapshot_id of the contained snapshot.
      2. A SHA-256 hash of the sorted, canonical JSON of the content labels.

    Two GradingReferences with the same snapshot_id and the same set of
    content labels (regardless of list order) will receive the SAME id.
    Changing any label or the snapshot_id yields a different id.

    The id is formatted as::

        "<snapshot_id>:<hex8>"

    where ``<hex8>`` is the first 16 hex characters of the SHA-256 digest
    of the sorted content labels.

    No random, no time, no network.  Fully deterministic.

    Parameters
    ----------
    reference:
        The GradingReference to identify.

    Returns
    -------
    Stable string id.
    """
    snapshot_id = reference.snapshot.snapshot_id

    # Serialize each label to a canonical dict, sort for order-independence,
    # then produce a deterministic JSON blob for hashing.
    label_dicts = sorted(
        [lb.model_dump() for lb in reference.content_labels],
        key=lambda d: (d["entity_id"], d["modality"], d["fact"], d["source"]),
    )
    labels_json = json.dumps(label_dicts, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(labels_json.encode("utf-8")).hexdigest()

    return f"{snapshot_id}:{digest[:16]}"


# ---------------------------------------------------------------------------
# Freeze / load (JSON only — no pickle)
# ---------------------------------------------------------------------------


def freeze_reference(reference: GradingReference, dir_path: Path | str) -> Path:
    """Persist a GradingReference to a directory in canonical JSON format.

    Writes two files:
      - ``<dir_path>/snapshot.json``       via DA2's ``freeze_snapshot``
      - ``<dir_path>/content_labels.json`` a JSON array of label dicts,
        ordered as stored in the reference (deterministic from authoring).

    The directory is created (with parents) if it does not exist.

    No pickle is used anywhere (Invariant #10).

    Parameters
    ----------
    reference:
        The GradingReference to freeze.  Should be the KG-full reference
        (never ablated).
    dir_path:
        Target directory.

    Returns
    -------
    Path to the directory that was written (same as dir_path, as a Path).
    """
    target = Path(dir_path)
    # freeze_snapshot creates the directory and writes snapshot.json
    freeze_snapshot(reference.snapshot, target)

    # Write content_labels.json as a canonical JSON array, preserving
    # the authoring order (deterministic given a fixed reference).
    labels_data = [lb.model_dump() for lb in reference.content_labels]
    labels_json = json.dumps(labels_data, sort_keys=True, ensure_ascii=True, indent=None)
    (target / "content_labels.json").write_text(labels_json, encoding="utf-8")

    return target


def load_reference(dir_path: Path | str) -> GradingReference:
    """Load a GradingReference from a directory written by ``freeze_reference``.

    Reads:
      - ``<dir_path>/snapshot.json``       via DA2's ``load_snapshot``
      - ``<dir_path>/content_labels.json`` parsed and validated via Pydantic

    No pickle is used (Invariant #10).

    Parameters
    ----------
    dir_path:
        Directory containing snapshot.json and content_labels.json
        (as written by freeze_reference).

    Returns
    -------
    Validated GradingReference instance equal to the one that was frozen.
    """
    target = Path(dir_path)
    snapshot = load_snapshot(target)
    raw = (target / "content_labels.json").read_text(encoding="utf-8")
    labels_raw: list[dict] = json.loads(raw)
    content_labels = [ContentLabel.model_validate(item) for item in labels_raw]
    return assemble_reference(snapshot, content_labels)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
__all__ = [
    "assemble_reference",
    "make_text_content_label",
    "author_books_content_labels",
    "reference_id",
    "freeze_reference",
    "load_reference",
]
