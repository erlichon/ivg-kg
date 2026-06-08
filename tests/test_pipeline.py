"""Tests for DA3: pipeline.py.

All tests run offline (no network, no pickle).
A fake WikidataClient is injected via dependency injection; no real SPARQL calls.

Covers:
- Enumeration query string: must be non-empty, valid-looking SPARQL, no Q16521/P181.
- Per-entity triples query builder: must not reference Q16521/P181 or the
  wikibase:label SERVICE.
- build_books_slice:
  - Out-of-band candidates dropped (Python sitelink re-check).
  - Selected subset is deterministic and capped at `limit`.
  - Dropped-datatype triples excluded; kept ones present with correct value_type.
  - Descriptions preserved on nodes (content axis intact).
  - Returns KGSnapshot with slice=="books" and domain_qid=="Q571".
- freeze_books_slice:
  - Writes snapshot.json under the given root dir.
  - load_snapshot round-trip returns equal snapshot.
- content_structure_overlap_report:
  - Returns a deterministic dict with the required keys.
  - Counts match the canned snapshot.
  - Identical input -> identical report.
- Determinism: running build_books_slice twice with same fake client yields
  identical snapshots.
- Invariant #8: pipeline module must not reference Q16521/P181 or image-fetch logic.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

from ivg_kg.schema import KGSnapshot

# ---------------------------------------------------------------------------
# Minimal fake WikidataClient
# ---------------------------------------------------------------------------


class FakeClient:
    """Fake WikidataClient that returns pre-baked rows.

    The first call returns enumeration rows; subsequent calls return triples rows.
    This mirrors the real two-query pattern: one enumeration call, then one
    per-entity triples call.
    """

    def __init__(
        self,
        enum_rows: list[dict[str, str]],
        triple_rows: list[dict[str, str]],
    ) -> None:
        self._enum_rows = enum_rows
        self._triple_rows = triple_rows
        self._call_count = 0

    def run_query(self, query: str) -> list[dict[str, str]]:
        self._call_count += 1
        if self._call_count == 1:
            return list(self._enum_rows)
        return list(self._triple_rows)


# ---------------------------------------------------------------------------
# Canned enumeration rows (mix of in-band and out-of-band sitelink counts)
# ---------------------------------------------------------------------------
# SITELINK_BAND = (5, 40); in-band = [5, 40] inclusive.
# Q100 (4 sitelinks) -- TOO FEW, dropped
# Q101 (5 sitelinks) -- in-band, kept
# Q102 (20 sitelinks) -- in-band, kept
# Q103 (40 sitelinks) -- in-band, kept
# Q104 (41 sitelinks) -- TOO MANY, dropped

_ENUM_ROWS: list[dict[str, str]] = [
    {"item": "http://www.wikidata.org/entity/Q100", "sitelinks": "4"},
    {"item": "http://www.wikidata.org/entity/Q101", "sitelinks": "5"},
    {"item": "http://www.wikidata.org/entity/Q102", "sitelinks": "20"},
    {"item": "http://www.wikidata.org/entity/Q103", "sitelinks": "40"},
    {"item": "http://www.wikidata.org/entity/Q104", "sitelinks": "41"},
]

# In-band QIDs (bare, sorted): Q101, Q102, Q103
_INBAND_QIDS = ["Q101", "Q102", "Q103"]

# ---------------------------------------------------------------------------
# Canned triples rows (mix of KEPT and DROPPED datatypes)
# ---------------------------------------------------------------------------
# KEPT datatypes: WikibaseItem, Time, Quantity, Monolingualtext, String
# DROPPED datatypes: ExternalId, CommonsMedia, Url

_TRIPLE_ROWS: list[dict[str, str]] = [
    # Q101: author (WikibaseItem) -- KEPT -> value_type="item"
    {
        "item": "http://www.wikidata.org/entity/Q101",
        "itemLabel": "Book Alpha",
        "itemDescription": "a novel about alpha",
        "sitelinks": "5",
        "prop": "http://www.wikidata.org/prop/direct/P50",
        "propLabel": "author",
        "value": "http://www.wikidata.org/entity/Q200",
        "valueLabel": "Jane Doe",
        "pt": "http://wikiba.se/ontology#WikibaseItem",
    },
    # Q101: publication date (Time) -- KEPT -> value_type="time"
    {
        "item": "http://www.wikidata.org/entity/Q101",
        "itemLabel": "Book Alpha",
        "itemDescription": "a novel about alpha",
        "sitelinks": "5",
        "prop": "http://www.wikidata.org/prop/direct/P577",
        "propLabel": "publication date",
        "value": "",
        "valueLabel": "1990-01-01",
        "pt": "http://wikiba.se/ontology#Time",
    },
    # Q101: GoodReads ID (ExternalId) -- DROPPED
    {
        "item": "http://www.wikidata.org/entity/Q101",
        "itemLabel": "Book Alpha",
        "itemDescription": "a novel about alpha",
        "sitelinks": "5",
        "prop": "http://www.wikidata.org/prop/direct/P8383",
        "propLabel": "Goodreads work ID",
        "value": "",
        "valueLabel": "12345",
        "pt": "http://wikiba.se/ontology#ExternalId",
    },
    # Q102: pages (Quantity) -- KEPT -> value_type="quantity"
    {
        "item": "http://www.wikidata.org/entity/Q102",
        "itemLabel": "Book Beta",
        "itemDescription": "another great book",
        "sitelinks": "20",
        "prop": "http://www.wikidata.org/prop/direct/P1104",
        "propLabel": "number of pages",
        "value": "",
        "valueLabel": "320",
        "pt": "http://wikiba.se/ontology#Quantity",
    },
    # Q102: cover image (CommonsMedia) -- DROPPED
    {
        "item": "http://www.wikidata.org/entity/Q102",
        "itemLabel": "Book Beta",
        "itemDescription": "another great book",
        "sitelinks": "20",
        "prop": "http://www.wikidata.org/prop/direct/P18",
        "propLabel": "image",
        "value": "",
        "valueLabel": "BookBeta.jpg",
        "pt": "http://wikiba.se/ontology#CommonsMedia",
    },
    # Q103: title (Monolingualtext) -- KEPT -> value_type="monolingual"
    {
        "item": "http://www.wikidata.org/entity/Q103",
        "itemLabel": "Book Gamma",
        "itemDescription": "the third book",
        "sitelinks": "40",
        "prop": "http://www.wikidata.org/prop/direct/P1476",
        "propLabel": "title",
        "value": "",
        "valueLabel": "Book Gamma",
        "pt": "http://wikiba.se/ontology#Monolingualtext",
    },
    # Q103: official website (Url) -- DROPPED
    {
        "item": "http://www.wikidata.org/entity/Q103",
        "itemLabel": "Book Gamma",
        "itemDescription": "the third book",
        "sitelinks": "40",
        "prop": "http://www.wikidata.org/prop/direct/P856",
        "propLabel": "official website",
        "value": "",
        "valueLabel": "https://bookgamma.com",
        "pt": "http://wikiba.se/ontology#Url",
    },
]


def _make_fake_client(
    enum_rows: list[dict[str, str]] | None = None,
    triple_rows: list[dict[str, str]] | None = None,
) -> FakeClient:
    return FakeClient(
        enum_rows=enum_rows if enum_rows is not None else list(_ENUM_ROWS),
        triple_rows=triple_rows if triple_rows is not None else list(_TRIPLE_ROWS),
    )


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------


def _import_pipeline() -> Any:
    """Import pipeline module; skip tests if import fails (module not yet written)."""
    return importlib.import_module("ivg_kg.data.pipeline")


# ===========================================================================
# Query string sanity tests
# ===========================================================================


class TestQueryStrings:
    def test_enumeration_query_is_nonempty_string(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.enumeration_query()
        assert isinstance(q, str)
        assert len(q.strip()) > 0

    def test_enumeration_query_contains_q571(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.enumeration_query()
        assert "Q571" in q, "Enumeration query must filter on Q571 (book)"

    def test_enumeration_query_no_taxa_qid(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.enumeration_query()
        assert "Q16521" not in q, "Enumeration query must NOT reference taxa QID Q16521"

    def test_enumeration_query_no_p181(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.enumeration_query()
        assert "P181" not in q, "Enumeration query must NOT reference P181 (range map)"

    def test_enumeration_query_no_wikibase_label_service(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.enumeration_query()
        assert "wikibase:label" not in q.lower(), (
            "Enumeration query must NOT use wikibase:label SERVICE (not QLever-compatible)"
        )

    def test_triples_query_is_nonempty_string(self) -> None:
        pipeline = _import_pipeline()
        qids = ["Q101", "Q102"]
        q = pipeline.triples_query(qids)
        assert isinstance(q, str)
        assert len(q.strip()) > 0

    def test_triples_query_includes_qids(self) -> None:
        pipeline = _import_pipeline()
        qids = ["Q101", "Q102"]
        q = pipeline.triples_query(qids)
        assert "Q101" in q
        assert "Q102" in q

    def test_triples_query_no_taxa_qid(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.triples_query(["Q101"])
        assert "Q16521" not in q

    def test_triples_query_no_p181(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.triples_query(["Q101"])
        assert "P181" not in q

    def test_triples_query_no_wikibase_label_service(self) -> None:
        pipeline = _import_pipeline()
        q = pipeline.triples_query(["Q101"])
        assert "wikibase:label" not in q.lower(), (
            "Triples query must NOT use wikibase:label SERVICE (not QLever-compatible)"
        )


# ===========================================================================
# build_books_slice tests
# ===========================================================================


class TestBuildBooksSlice:
    def test_returns_kgsnapshot(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        assert isinstance(snap, KGSnapshot)

    def test_slice_field_is_books(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        assert snap.slice == "books"

    def test_domain_qid_is_q571(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        assert snap.domain_qid == "Q571"

    def test_snapshot_id_matches_slice_id(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="my-slice-42")
        assert snap.snapshot_id == "my-slice-42"

    def test_out_of_band_candidates_dropped(self) -> None:
        """Q100 (4 sitelinks) and Q104 (41 sitelinks) must not appear in the snapshot."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        node_ids = {n.id for n in snap.nodes}
        assert "Q100" not in node_ids, "Q100 (4 sitelinks, below band) must be dropped"
        assert "Q104" not in node_ids, "Q104 (41 sitelinks, above band) must be dropped"

    def test_in_band_candidates_present(self) -> None:
        """Q101, Q102, Q103 are all in-band and must appear as subject nodes."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        node_ids = {n.id for n in snap.nodes}
        for qid in _INBAND_QIDS:
            assert qid in node_ids, f"{qid} (in-band) must be present in snapshot"

    def test_limit_caps_number_of_subjects(self) -> None:
        """With limit=2, only 2 books (deterministically lowest QIDs) are included."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001", limit=2)
        subject_ids = {e.subject_id for e in snap.edges}
        assert len(subject_ids) <= 2, f"Expected at most 2 subjects; got {subject_ids}"

    def test_limit_selection_is_deterministic_by_qid_sort(self) -> None:
        """With limit=2, the 2 lowest-sorted QIDs are picked: Q101, Q102."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001", limit=2)
        subject_ids = {e.subject_id for e in snap.edges}
        # Q101 < Q102 < Q103 lexicographically after sorting
        assert "Q101" in subject_ids
        assert "Q102" in subject_ids
        assert "Q103" not in subject_ids

    def test_dropped_datatype_triples_excluded(self) -> None:
        """ExternalId, CommonsMedia, Url property rows must be excluded."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        prop_ids = {e.property_id for e in snap.edges}
        # P8383 (ExternalId), P18 (CommonsMedia), P856 (Url) must be absent
        assert "P8383" not in prop_ids, "ExternalId property must be dropped"
        assert "P18" not in prop_ids, "CommonsMedia property must be dropped"
        assert "P856" not in prop_ids, "Url property must be dropped"

    def test_kept_datatype_triples_present(self) -> None:
        """WikibaseItem (P50), Time (P577), Quantity (P1104), Monolingualtext (P1476) kept."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        prop_ids = {e.property_id for e in snap.edges}
        assert "P50" in prop_ids, "WikibaseItem property (author) must be kept"
        assert "P577" in prop_ids, "Time property (publication date) must be kept"
        assert "P1104" in prop_ids, "Quantity property (pages) must be kept"
        assert "P1476" in prop_ids, "Monolingualtext property (title) must be kept"

    def test_value_type_item_correct(self) -> None:
        """P50 (author, WikibaseItem) must produce value_type='item'."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        from ivg_kg.schema import ValueType

        p50_edges = [e for e in snap.edges if e.property_id == "P50"]
        assert p50_edges, "Expected at least one P50 edge"
        assert all(e.value_type == ValueType.ITEM for e in p50_edges)

    def test_value_type_time_correct(self) -> None:
        """P577 (publication date, Time) must produce value_type='time'."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        from ivg_kg.schema import ValueType

        p577_edges = [e for e in snap.edges if e.property_id == "P577"]
        assert p577_edges
        assert all(e.value_type == ValueType.TIME for e in p577_edges)

    def test_value_type_quantity_correct(self) -> None:
        """P1104 (number of pages, Quantity) must produce value_type='quantity'."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        from ivg_kg.schema import ValueType

        p1104_edges = [e for e in snap.edges if e.property_id == "P1104"]
        assert p1104_edges
        assert all(e.value_type == ValueType.QUANTITY for e in p1104_edges)

    def test_value_type_monolingual_correct(self) -> None:
        """P1476 (title, Monolingualtext) must produce value_type='monolingual'."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        from ivg_kg.schema import ValueType

        p1476_edges = [e for e in snap.edges if e.property_id == "P1476"]
        assert p1476_edges
        assert all(e.value_type == ValueType.MONOLINGUAL for e in p1476_edges)

    def test_descriptions_preserved_on_nodes(self) -> None:
        """Subject nodes must carry their description (content axis)."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        # Q101 has description "a novel about alpha" in our canned triples
        q101 = next((n for n in snap.nodes if n.id == "Q101"), None)
        assert q101 is not None
        assert q101.description is not None
        assert len(q101.description) > 0

    def test_determinism_same_client_same_result(self) -> None:
        """Two calls with the same fake client yield identical snapshots."""
        pipeline = _import_pipeline()

        def make_client() -> FakeClient:
            return FakeClient(
                enum_rows=list(_ENUM_ROWS),
                triple_rows=list(_TRIPLE_ROWS),
            )

        snap1 = pipeline.build_books_slice(make_client(), slice_id="det-test")
        snap2 = pipeline.build_books_slice(make_client(), slice_id="det-test")
        assert snap1 == snap2, "build_books_slice must be deterministic"

    def test_nodes_list_not_empty(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        assert len(snap.nodes) > 0

    def test_edges_list_not_empty(self) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.build_books_slice(client, slice_id="test-001")
        assert len(snap.edges) > 0


# ===========================================================================
# freeze_books_slice tests
# ===========================================================================


class TestFreezeBooksSlice:
    def test_writes_snapshot_json(self, tmp_path: Path) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        pipeline.freeze_books_slice(
            client, slice_id="freeze-001", frozen_root=tmp_path
        )
        snap_file = tmp_path / "books" / "freeze-001" / "snapshot.json"
        assert snap_file.exists(), f"snapshot.json must be written to {snap_file}"

    def test_snapshot_json_is_valid_json(self, tmp_path: Path) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        pipeline.freeze_books_slice(
            client, slice_id="freeze-001", frozen_root=tmp_path
        )
        snap_file = tmp_path / "books" / "freeze-001" / "snapshot.json"
        data = json.loads(snap_file.read_text())
        assert isinstance(data, dict)

    def test_load_snapshot_roundtrip(self, tmp_path: Path) -> None:
        from ivg_kg.data.graph_store import load_snapshot

        pipeline = _import_pipeline()
        client = _make_fake_client()
        snap = pipeline.freeze_books_slice(
            client, slice_id="rt-001", frozen_root=tmp_path
        )
        loaded = load_snapshot(tmp_path / "books" / "rt-001")
        assert loaded == snap, "Loaded snapshot must equal the one that was frozen"

    def test_no_pickle_files_written(self, tmp_path: Path) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        pipeline.freeze_books_slice(
            client, slice_id="pkl-test", frozen_root=tmp_path
        )
        pkl_files = list(tmp_path.rglob("*.pkl")) + list(tmp_path.rglob("*.pickle"))
        assert pkl_files == [], f"No pickle files must be written; found: {pkl_files}"

    def test_freeze_does_not_pollute_repo_data_dir(self, tmp_path: Path) -> None:
        """freeze_books_slice with a tmp frozen_root must NOT write to data/frozen."""
        pipeline = _import_pipeline()
        client = _make_fake_client()
        pipeline.freeze_books_slice(
            client, slice_id="isolation-test", frozen_root=tmp_path
        )
        # The real repo data dir must remain untouched
        real_dir = (
            Path(__file__).parent.parent / "data" / "frozen" / "books" / "isolation-test"
        )
        assert not real_dir.exists()

    def test_returns_kgsnapshot(self, tmp_path: Path) -> None:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        result = pipeline.freeze_books_slice(
            client, slice_id="ret-test", frozen_root=tmp_path
        )
        assert isinstance(result, KGSnapshot)


# ===========================================================================
# content_structure_overlap_report tests
# ===========================================================================


class TestContentStructureOverlapReport:
    def _build_snap(self) -> KGSnapshot:
        pipeline = _import_pipeline()
        client = _make_fake_client()
        return pipeline.build_books_slice(client, slice_id="report-snap")

    def test_returns_dict(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        assert isinstance(report, dict)

    def test_required_keys_present(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        required = {
            "num_entities",
            "num_with_description",
            "num_without_description",
            "num_with_triples",
            "num_with_both",
            "triple_counts_per_entity",
        }
        missing = required - set(report.keys())
        assert not missing, f"Report missing required keys: {missing}"

    def test_num_entities_correct(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        # The snapshot has subject nodes: Q101, Q102, Q103 (all in-band)
        # (object items like Q200 are also nodes, but report counts SUBJECT nodes)
        # We just check the total is positive and consistent
        assert report["num_entities"] > 0

    def test_num_with_description_plus_without_equals_total(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        total = report["num_entities"]
        with_desc = report["num_with_description"]
        without_desc = report["num_without_description"]
        assert with_desc + without_desc == total

    def test_num_with_both_leq_num_with_description(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        assert report["num_with_both"] <= report["num_with_description"]

    def test_num_with_both_leq_num_with_triples(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        assert report["num_with_both"] <= report["num_with_triples"]

    def test_triple_counts_per_entity_is_dict(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        assert isinstance(report["triple_counts_per_entity"], dict)

    def test_triple_counts_values_are_ints(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        for _qid, count in report["triple_counts_per_entity"].items():
            assert isinstance(count, int) and count >= 0

    def test_determinism_identical_input(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        r1 = pipeline.content_structure_overlap_report(snap)
        r2 = pipeline.content_structure_overlap_report(snap)
        assert r1 == r2, "Report must be deterministic for identical input"

    def test_json_serializable(self) -> None:
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        # Must be JSON-serializable without error
        json.dumps(report)

    def test_descriptions_present_in_canned_snapshot(self) -> None:
        """The canned triple rows all carry descriptions; report must reflect this."""
        pipeline = _import_pipeline()
        snap = self._build_snap()
        report = pipeline.content_structure_overlap_report(snap)
        # All three in-band books have descriptions in the canned data
        assert report["num_with_description"] >= 3


# ===========================================================================
# Invariant #8: no taxa / image / Q16521 / P181 references in source
# ===========================================================================


class TestInvariantNoBooksOnly:
    def test_module_source_no_q16521(self) -> None:
        pipeline = _import_pipeline()
        source = inspect.getsource(pipeline)
        assert "Q16521" not in source, "pipeline.py must not reference Q16521 (taxa)"

    def test_module_source_no_p181(self) -> None:
        pipeline = _import_pipeline()
        source = inspect.getsource(pipeline)
        assert "P181" not in source, "pipeline.py must not reference P181 (range map)"

    def test_module_source_no_fetch_image(self) -> None:
        pipeline = _import_pipeline()
        source = inspect.getsource(pipeline)
        # Very rough guard: no image-fetch patterns
        assert "fetch_image" not in source.lower()
        assert "rasterize" not in source.lower()

    def test_module_source_no_pickle(self) -> None:
        pipeline = _import_pipeline()
        source = inspect.getsource(pipeline)
        assert "import pickle" not in source
        assert "pickle.dump" not in source
        assert "pickle.load" not in source
