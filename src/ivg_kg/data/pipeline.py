"""DA3 — Books slice pipeline: enumerate, filter, build, freeze (SPEC §4.1, §8).

Public API
----------
enumeration_query() -> str
    Returns a SPARQL SELECT query that enumerates books (P31=Q571) with their
    sitelink count.  Compatible with both WDQS and QLever (uses rdfs:label and
    schema:description, NOT the wikibase:label SERVICE).

triples_query(qids: list[str]) -> str
    Returns a SPARQL SELECT query that fetches outgoing truthy statements for
    a given set of selected book QIDs, including property datatype so that
    keep_property_type / datatype_to_value_type can be applied.  Also fetches
    subject label, description, and sitelink count.  Compatible with both
    WDQS and QLever (no wikibase:label SERVICE).

build_books_slice(client, *, slice_id, limit=50, band=SITELINK_BAND) -> KGSnapshot
    Orchestrates the full pull-filter-build pipeline:
    1. Run enumeration query via client.run_query().
    2. Parse candidates (QID + sitelink count); apply sitelink_band_filter (Python
       re-check; SPEC §4.1 requires both server-side and Python filter).
    3. Sort candidates by QID for determinism; take the first `limit`.
    4. Run the per-entity triples query for the selected QIDs.
    5. Apply keep_property_type filter; map kept datatype -> value_type via
       datatype_to_value_type.  Keep description rows on subject nodes (content
       axis; not dropped as if they were triples).
    6. Build and return a KGSnapshot via DA2 build_snapshot().

freeze_books_slice(client, *, slice_id, limit=50, band=SITELINK_BAND,
                  frozen_root=Path("data/frozen")) -> KGSnapshot
    Wrapper: runs build_books_slice, freezes via DA2 freeze_snapshot to
    <frozen_root>/books/<slice_id>/, and returns the KGSnapshot.

content_structure_overlap_report(snapshot: KGSnapshot) -> dict
    Deterministic descriptive report over a frozen books snapshot.
    Returns a JSON-serializable dict with:
      num_entities          int   total subject entities (nodes authored as subjects)
      num_with_description  int   subjects with a non-empty description
      num_without_description int subjects lacking a description
      num_with_triples      int   subjects with at least one outgoing triple
      num_with_both         int   subjects with BOTH a description and triples
      triple_counts_per_entity  dict[str, int]  subject_id -> outgoing triple count

main() / __main__ entry point
    Constructs a real WikidataClient and freezes a small real books slice to
    data/frozen/books/<slice_id>/.  Intended for one-off build-time use only.

Design invariants
-----------------
- Books only: Q571 (Invariant #8).  No taxa slice, no range-map properties,
  no image fetch.
- WDQS + QLever compatible: no wikibase:label SERVICE in any query.
- No pickle.  No network in tests (client injected as parameter).
- Deterministic: candidates sorted by QID; frozen output stable for fixed input.
- Description is CONTENT (§11) and must survive to the KGNode; it is NOT
  treated as a triple to be property-type-filtered.
- Live SPARQL is build-time only (Invariant #9); this module must not be
  imported at demo time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ivg_kg.config import SITELINK_BAND
from ivg_kg.data.graph_store import build_snapshot, freeze_snapshot
from ivg_kg.data.wikidata import datatype_to_value_type, keep_property_type, sitelink_band_filter
from ivg_kg.schema import KGSnapshot

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BOOKS_DOMAIN_QID = "Q571"
_FROZEN_BOOKS_SUBDIR = "books"
_DEFAULT_LIMIT = 50

# Wikidata entity URI prefix (for normalisation when parsing enumeration rows)
_ENTITY_URI_PREFIX = "http://www.wikidata.org/entity/"
_PROP_URI_PREFIX_DIRECT = "http://www.wikidata.org/prop/direct/"
_PROP_URI_PREFIX = "http://www.wikidata.org/prop/"

# ---------------------------------------------------------------------------
# Internal URI normalisation (lightweight; mirrors graph_store._normalise_id)
# ---------------------------------------------------------------------------


def _strip_uri(uri: str | None) -> str | None:
    """Strip a Wikidata entity or property URI to a bare QID/PID."""
    if uri is None:
        return None
    if uri.startswith(_ENTITY_URI_PREFIX):
        return uri[len(_ENTITY_URI_PREFIX):]
    if uri.startswith(_PROP_URI_PREFIX_DIRECT):
        return uri[len(_PROP_URI_PREFIX_DIRECT):]
    if uri.startswith(_PROP_URI_PREFIX):
        return uri[len(_PROP_URI_PREFIX):]
    return uri


# ---------------------------------------------------------------------------
# SPARQL query builders
# ---------------------------------------------------------------------------


def enumeration_query() -> str:
    """Return a SPARQL query enumerating books (P31=Q571) with sitelink counts.

    Compatible with WDQS and QLever.  Does NOT use the wikibase:label SERVICE
    (not available on QLever).  Returns sitelinks via wikibase:sitelinks.

    Sitelink band is applied server-side with a FILTER; Python re-check is
    performed in build_books_slice via sitelink_band_filter (SPEC §4.1).

    Result columns: item (URI), sitelinks (literal integer string).
    """
    lo, hi = SITELINK_BAND
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?item ?sitelinks
WHERE {{
  ?item wdt:P31 wd:Q571 .
  ?item wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= {lo} && ?sitelinks <= {hi})
}}
ORDER BY ?item
LIMIT 200
"""


def triples_query(qids: list[str]) -> str:
    """Return a SPARQL query fetching outgoing triples for the given book QIDs.

    Fetches per-entity: label (rdfs:label, English), description
    (schema:description, English), sitelink count, plus outgoing truthy
    statements (wdt: prefix) with property label (rdfs:label) and property
    datatype (wikibase:propertyType), and value label or literal.

    Compatible with WDQS and QLever.  Does NOT use the wikibase:label SERVICE.

    Result columns:
      item        entity URI of the subject book
      itemLabel   English rdfs:label
      itemDescription  English schema:description (may be absent)
      sitelinks   wikibase:sitelinks count
      prop        property URI (wdt: direct)
      propLabel   English rdfs:label of the property
      value       object entity URI (for WikibaseItem) or empty string
      valueLabel  English rdfs:label of value (for items) or literal string
      pt          property type URI (e.g. http://wikiba.se/ontology#WikibaseItem)

    Args:
        qids: List of bare QIDs (e.g. ["Q101", "Q102"]).

    Returns:
        SPARQL SELECT string ready to pass to WikidataClient.run_query().
    """
    if not qids:
        # Return a trivially valid SPARQL that produces no rows
        return "SELECT ?item WHERE { FILTER(false) }"

    # Build VALUES clause: wd:Q101 wd:Q102 ...
    values = " ".join(f"wd:{q}" for q in qids)

    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX wdata: <http://www.wikidata.org/wiki/Special:EntityData/>

SELECT ?item ?itemLabel ?itemDescription ?sitelinks ?prop ?propLabel ?value ?valueLabel ?pt
WHERE {{
  VALUES ?item {{ {values} }}

  # Subject label (English)
  ?item rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "en")

  # Subject description (optional, English)
  OPTIONAL {{
    ?item schema:description ?itemDescription .
    FILTER(LANG(?itemDescription) = "en")
  }}

  # Sitelink count
  ?item wikibase:sitelinks ?sitelinks .

  # Outgoing truthy statements
  ?item ?prop ?value .
  # Restrict to wdt: (direct) properties only
  FILTER(STRSTARTS(STR(?prop), "http://www.wikidata.org/prop/direct/"))

  # Property entity (for label and type lookup)
  BIND(IRI(REPLACE(STR(?prop),
    "http://www.wikidata.org/prop/direct/",
    "http://www.wikidata.org/entity/")) AS ?propEntity)

  # Property label (English)
  OPTIONAL {{
    ?propEntity rdfs:label ?propLabel .
    FILTER(LANG(?propLabel) = "en")
  }}

  # Property datatype
  OPTIONAL {{
    ?propEntity wikibase:propertyType ?pt .
  }}

  # Value label (English) for entity-valued objects; empty for literals
  OPTIONAL {{
    ?value rdfs:label ?valueLabel .
    FILTER(LANG(?valueLabel) = "en")
  }}
}}
ORDER BY ?item ?prop
"""


# ---------------------------------------------------------------------------
# Row parsing helpers
# ---------------------------------------------------------------------------


def _parse_enum_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert raw SPARQL enum rows to candidate dicts with int sitelink counts.

    Each returned dict has:
      qid:       str   bare QID (e.g. "Q101")
      sitelinks: int   sitelink count (parsed from string)
    """
    candidates: list[dict[str, Any]] = []
    for row in rows:
        raw_qid = row.get("item", "")
        raw_sitelinks = row.get("sitelinks", "")
        if not raw_qid or not raw_sitelinks:
            continue
        qid = _strip_uri(raw_qid) or raw_qid
        try:
            count = int(raw_sitelinks)
        except (ValueError, TypeError):
            continue
        candidates.append({"qid": qid, "sitelinks": count})
    return candidates


def _parse_triple_rows(
    rows: list[dict[str, str]],
    selected_qids: set[str],
) -> list[dict[str, Any]]:
    """Convert raw SPARQL triple rows to DA2-compatible row dicts.

    Applies keep_property_type / datatype_to_value_type to filter and map
    each row.  Drops rows whose property datatype fails keep_property_type.
    Drops rows for subjects not in selected_qids (safety guard).

    Descriptions are carried on subject nodes (not emitted as separate rows);
    the description is preserved in subject_description on each row for the
    subject, so DA2 build_snapshot can attach it to the KGNode.

    Returns:
        List of row dicts conforming to DA2's row-key contract.
    """
    result: list[dict[str, Any]] = []

    for row in rows:
        raw_item = row.get("item", "")
        subject_qid = _strip_uri(raw_item) or raw_item
        if subject_qid not in selected_qids:
            continue

        raw_prop = row.get("prop", "")
        property_id = _strip_uri(raw_prop) or raw_prop
        if not property_id:
            continue

        # Property datatype filter (SPEC §4.1; Invariant #4 extension)
        raw_pt = row.get("pt", "")
        if not keep_property_type(raw_pt):
            continue

        value_type_enum = datatype_to_value_type(raw_pt)
        if value_type_enum is None:
            # Should not happen after keep_property_type passed, but guard anyway
            continue

        # Build row according to DA2 row-key contract
        subject_label = row.get("itemLabel", subject_qid)
        subject_description = row.get("itemDescription") or None
        subject_sitelinks = row.get("sitelinks") or None

        prop_label = row.get("propLabel", property_id)

        raw_value = row.get("value", "")
        value_label = row.get("valueLabel", raw_value)

        # For WikibaseItem, value is a URI; for literals, value is empty or the literal
        if value_type_enum.value == "item":
            object_id: str | None = _strip_uri(raw_value) or raw_value or None
            # Use value label as object label; fall back to bare QID
            object_label = value_label or object_id or ""
        else:
            object_id = None
            # For literal types, valueLabel IS the display value
            object_label = value_label or raw_value or ""

        da2_row: dict[str, Any] = {
            "subject_id": subject_qid,
            "subject_label": subject_label,
            "property_id": property_id,
            "property_label": prop_label,
            "object_label": object_label,
            "value_type": value_type_enum.value,
        }
        if subject_description:
            da2_row["subject_description"] = subject_description
        if subject_sitelinks:
            da2_row["subject_sitelinks"] = subject_sitelinks
        if object_id:
            da2_row["object_id"] = object_id

        result.append(da2_row)

    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_books_slice(
    client: Any,
    *,
    slice_id: str,
    limit: int = _DEFAULT_LIMIT,
    band: tuple[int, int] = SITELINK_BAND,
) -> KGSnapshot:
    """Orchestrate the books slice pipeline: enumerate -> filter -> build.

    Parameters
    ----------
    client:
        A WikidataClient (or any object with a run_query(query: str) ->
        list[dict[str, str]] method).  Injected so tests can pass a fake.
    slice_id:
        Unique identifier for this snapshot (stored as KGSnapshot.snapshot_id).
    limit:
        Maximum number of book entities to include.  Candidates are sorted by
        QID for determinism; the first `limit` after sorting are taken.
    band:
        Sitelink band (lo, hi) inclusive.  Applied both server-side (in the
        SPARQL FILTER) and as a Python re-check via sitelink_band_filter.

    Returns
    -------
    KGSnapshot with slice="books", domain_qid="Q571", snapshot_id=slice_id.
    """
    # Step 1: Enumerate candidate books
    enum_q = enumeration_query()
    raw_enum_rows = client.run_query(enum_q)

    # Step 2: Parse candidates and apply Python sitelink re-check (SPEC §4.1)
    candidates = _parse_enum_rows(raw_enum_rows)
    # Adapt to sitelink_band_filter's expected dict shape (count_key="sitelinks")
    in_band = sitelink_band_filter(candidates, band=band, count_key="sitelinks")

    # Step 3: Sort by QID for determinism; take first `limit`
    in_band_sorted = sorted(in_band, key=lambda c: c["qid"])
    selected = in_band_sorted[:limit]
    selected_qids = {c["qid"] for c in selected}

    if not selected_qids:
        # No candidates: return an empty but valid snapshot
        return build_snapshot(
            [],
            snapshot_id=slice_id,
            slice=_FROZEN_BOOKS_SUBDIR,
            domain_qid=_BOOKS_DOMAIN_QID,
            meta={"limit": limit, "band": list(band), "num_selected": 0},
        )

    # Step 4: Fetch triples for selected QIDs
    # Sort QIDs for deterministic query text (reproducible cache key)
    sorted_qids = sorted(selected_qids)
    triples_q = triples_query(sorted_qids)
    raw_triple_rows = client.run_query(triples_q)

    # Step 5: Parse triple rows, applying property-type filter
    da2_rows = _parse_triple_rows(raw_triple_rows, selected_qids)

    # Step 6: Build KGSnapshot via DA2
    return build_snapshot(
        da2_rows,
        snapshot_id=slice_id,
        slice=_FROZEN_BOOKS_SUBDIR,
        domain_qid=_BOOKS_DOMAIN_QID,
        meta={
            "limit": limit,
            "band": list(band),
            "num_selected": len(selected_qids),
            "selected_qids": sorted_qids,
        },
    )


def freeze_books_slice(
    client: Any,
    *,
    slice_id: str,
    limit: int = _DEFAULT_LIMIT,
    band: tuple[int, int] = SITELINK_BAND,
    frozen_root: Path | str = Path("data/frozen"),
) -> KGSnapshot:
    """Build and freeze a books slice to <frozen_root>/books/<slice_id>/.

    Parameters
    ----------
    client:
        WikidataClient or fake.  See build_books_slice.
    slice_id:
        Unique identifier; used as both snapshot_id and directory name.
    limit:
        Maximum number of book entities.
    band:
        Sitelink band.
    frozen_root:
        Root directory for frozen data.  Defaults to data/frozen (relative to
        the current working directory).  Override in tests to avoid polluting
        the repo's data directory.

    Returns
    -------
    The built KGSnapshot (also written to disk as JSON).
    """
    snapshot = build_books_slice(client, slice_id=slice_id, limit=limit, band=band)
    target_dir = Path(frozen_root) / _FROZEN_BOOKS_SUBDIR / slice_id
    freeze_snapshot(snapshot, target_dir)
    return snapshot


# ---------------------------------------------------------------------------
# Content / structure overlap report
# ---------------------------------------------------------------------------


def content_structure_overlap_report(snapshot: KGSnapshot) -> dict[str, Any]:
    """Return a descriptive overlap report for a frozen books snapshot.

    Checks whether each subject entity has:
    - A non-empty description (CONTENT axis, SPEC §11).
    - At least one outgoing triple (STRUCTURE axis).

    The report re-confirms that the books slice carries content (descriptions)
    alongside structure (triples), the non-redundancy rationale of SPEC §10/§11.

    Parameters
    ----------
    snapshot:
        A KGSnapshot as produced by build_books_slice() or load_snapshot().

    Returns
    -------
    JSON-serializable dict with keys:
      num_entities               int
      num_with_description       int
      num_without_description    int
      num_with_triples           int
      num_with_both              int
      triple_counts_per_entity   dict[str, int]  subject_id -> count
    """
    # Collect all subject IDs (entities that appear as the subject of an edge)
    subject_ids: set[str] = {e.subject_id for e in snapshot.edges}

    # If no edges, fall back to all entity nodes as subjects
    if not subject_ids:
        subject_ids = {n.id for n in snapshot.nodes}

    # Build a lookup: subject_id -> KGNode (for description)
    node_by_id = {n.id: n for n in snapshot.nodes}

    # Count outgoing triples per subject
    triple_counts: dict[str, int] = dict.fromkeys(subject_ids, 0)
    for edge in snapshot.edges:
        if edge.subject_id in triple_counts:
            triple_counts[edge.subject_id] += 1

    num_entities = len(subject_ids)
    num_with_description = 0
    num_without_description = 0
    num_with_triples = 0
    num_with_both = 0

    for qid in subject_ids:
        node = node_by_id.get(qid)
        has_desc = bool(node and node.description and node.description.strip())
        has_triples = triple_counts.get(qid, 0) > 0

        if has_desc:
            num_with_description += 1
        else:
            num_without_description += 1

        if has_triples:
            num_with_triples += 1

        if has_desc and has_triples:
            num_with_both += 1

    return {
        "num_entities": num_entities,
        "num_with_description": num_with_description,
        "num_without_description": num_without_description,
        "num_with_triples": num_with_triples,
        "num_with_both": num_with_both,
        "triple_counts_per_entity": dict(sorted(triple_counts.items())),
    }


def write_overlap_report(
    snapshot: KGSnapshot,
    frozen_root: Path | str = Path("data/frozen"),
) -> Path:
    """Write the overlap report for a snapshot to its frozen directory.

    Writes to <frozen_root>/books/<snapshot_id>/overlap_report.json.

    Returns the path of the written file.
    """
    report = content_structure_overlap_report(snapshot)
    target = Path(frozen_root) / _FROZEN_BOOKS_SUBDIR / snapshot.snapshot_id
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "overlap_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Entry point (build-time only; do NOT import at demo time)
# ---------------------------------------------------------------------------


def main() -> None:
    """Freeze a small real books slice to data/frozen/books/<slice_id>/.

    Constructs a real WikidataClient with the default fetch function.
    Attempts to contact WDQS (falls back to QLever automatically).

    Slice ID: books-p0-v1
    Target: data/frozen/books/books-p0-v1/
    Limit: 50 entities (small, deterministic)

    Run from the repo root:
        python -m ivg_kg.data.pipeline
    """
    import sys

    # Lazy import to avoid hard-requiring `requests` at module load time.
    try:
        from ivg_kg.data.wikidata import WikidataClient
    except ImportError as exc:
        print(f"ERROR: could not import WikidataClient: {exc}", file=sys.stderr)
        print("Install the data extra: pip install -e '.[data]'", file=sys.stderr)
        sys.exit(1)

    slice_id = "books-p0-v1"
    limit = 50
    frozen_root = Path("data/frozen")

    print(f"Building books slice '{slice_id}' (limit={limit})...")
    client = WikidataClient()

    try:
        snapshot = freeze_books_slice(
            client, slice_id=slice_id, limit=limit, frozen_root=frozen_root
        )
        target = frozen_root / _FROZEN_BOOKS_SUBDIR / slice_id
        print(f"Frozen to {target}/snapshot.json")
        print(f"  Nodes: {len(snapshot.nodes)}")
        print(f"  Edges: {len(snapshot.edges)}")

        report_path = write_overlap_report(snapshot, frozen_root=frozen_root)
        print(f"  Overlap report: {report_path}")

        report = content_structure_overlap_report(snapshot)
        print(
            f"  Entities: {report['num_entities']}, "
            f"with description: {report['num_with_description']}, "
            f"with triples: {report['num_with_triples']}, "
            f"with both: {report['num_with_both']}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR during freeze: {exc}", file=sys.stderr)
        print(
            "Network may be unavailable.  "
            "Run this script where WDQS / QLever is reachable.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
