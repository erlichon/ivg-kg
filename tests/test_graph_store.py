"""Tests for DA2: graph_store.py.

All tests run offline (no network, no pickle).  Covers:
- build_snapshot: row -> KGSnapshot (deduplication, value_type mapping, tolerant keys,
  URI normalisation, determinism, unknown value_type error).
- freeze/load round-trip via JSON only (no pickle).
- build_networkx: entity nodes, literal nodes (kind="literal"), shared-literal structure,
  directed edges, edge attributes.
- nx_to_cyto_elements: referential integrity, edge-id convention, determinism.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import networkx as nx
import pytest

from ivg_kg.data.graph_store import (
    build_networkx,
    build_snapshot,
    freeze_snapshot,
    load_snapshot,
    nx_to_cyto_elements,
)
from ivg_kg.schema import KGEdge, KGNode, KGSnapshot, ValueType

# ---------------------------------------------------------------------------
# Helpers — shared row fixtures
# ---------------------------------------------------------------------------

_BOOK_QID = "Q571"
_AUTHOR_QID = "Q5921"
_PUBLISHER_QID = "Q7094"


def _item_row(
    *,
    subject_id: str = _BOOK_QID,
    subject_label: str = "book",
    subject_description: str | None = "written work",
    subject_sitelinks: str | None = "37",
    property_id: str = "P50",
    property_label: str = "author",
    object_id: str | None = _AUTHOR_QID,
    object_label: str = "Douglas Adams",
    value_type: str = "item",
) -> dict:
    row: dict = {
        "subject_id": subject_id,
        "subject_label": subject_label,
        "property_id": property_id,
        "property_label": property_label,
        "object_label": object_label,
        "value_type": value_type,
    }
    if subject_description is not None:
        row["subject_description"] = subject_description
    if subject_sitelinks is not None:
        row["subject_sitelinks"] = subject_sitelinks
    if object_id is not None:
        row["object_id"] = object_id
    return row


def _literal_row(
    *,
    subject_id: str = _BOOK_QID,
    subject_label: str = "book",
    property_id: str = "P577",
    property_label: str = "publication date",
    object_label: str = "1979-03-12",
    value_type: str = "time",
) -> dict:
    return {
        "subject_id": subject_id,
        "subject_label": subject_label,
        "property_id": property_id,
        "property_label": property_label,
        "object_label": object_label,
        "value_type": value_type,
        # object_id deliberately absent for literals
    }


def _minimal_snapshot() -> KGSnapshot:
    """Two rows: one item-valued edge, one literal-valued edge."""
    rows = [_item_row(), _literal_row()]
    return build_snapshot(rows, snapshot_id="snap-001", slice="books", domain_qid=_BOOK_QID)


# ---------------------------------------------------------------------------
# build_snapshot tests
# ---------------------------------------------------------------------------


class TestBuildSnapshot:
    def test_returns_kgsnapshot(self):
        snap = _minimal_snapshot()
        assert isinstance(snap, KGSnapshot)
        assert snap.snapshot_id == "snap-001"
        assert snap.slice == "books"
        assert snap.domain_qid == _BOOK_QID

    def test_one_edge_per_row(self):
        rows = [_item_row(), _literal_row()]
        snap = build_snapshot(rows, snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        assert len(snap.edges) == 2

    def test_item_edge_has_object_id(self):
        snap = _minimal_snapshot()
        item_edge = next(e for e in snap.edges if e.property_id == "P50")
        assert item_edge.object_id == _AUTHOR_QID
        assert item_edge.value_type == ValueType.ITEM

    def test_literal_edge_has_no_object_id(self):
        snap = _minimal_snapshot()
        lit_edge = next(e for e in snap.edges if e.property_id == "P577")
        assert lit_edge.object_id is None
        assert lit_edge.value_type == ValueType.TIME

    def test_nodes_contain_subject_and_item_objects(self):
        snap = _minimal_snapshot()
        node_ids = {n.id for n in snap.nodes}
        # Subject must be present
        assert _BOOK_QID in node_ids
        # Item-valued object must be present
        assert _AUTHOR_QID in node_ids

    def test_no_literal_node_in_snapshot(self):
        snap = _minimal_snapshot()
        node_ids = {n.id for n in snap.nodes}
        # The literal (publication date) must NOT produce a node in the snapshot
        # (literal nodes are derived at nx-build time only)
        for nid in node_ids:
            assert not nid.startswith("lit:"), f"Found literal node in snapshot: {nid}"

    def test_node_carries_subject_description_and_sitelinks(self):
        snap = _minimal_snapshot()
        book_node = next(n for n in snap.nodes if n.id == _BOOK_QID)
        assert book_node.label == "book"
        assert book_node.description == "written work"
        assert book_node.sitelinks == 37

    def test_item_object_node_has_label(self):
        snap = _minimal_snapshot()
        author_node = next(n for n in snap.nodes if n.id == _AUTHOR_QID)
        assert author_node.label == "Douglas Adams"

    def test_deduplication_same_subject_multiple_rows(self):
        rows = [_item_row(), _literal_row()]
        # Both rows share _BOOK_QID as subject
        snap = build_snapshot(rows, snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        subject_nodes = [n for n in snap.nodes if n.id == _BOOK_QID]
        assert len(subject_nodes) == 1, "Subject node must be deduplicated"

    def test_deduplication_subject_also_appears_as_object(self):
        """When a QID appears as both subject and item-valued object, still one node."""
        rows = [
            _item_row(subject_id="Q1", subject_label="A", object_id="Q2", object_label="B"),
            _item_row(
                subject_id="Q2",
                subject_label="B",
                object_id="Q1",
                object_label="A",
                property_id="P99",
                property_label="related",
            ),
        ]
        snap = build_snapshot(rows, snapshot_id="s", slice="books", domain_qid="Q1")
        ids = [n.id for n in snap.nodes]
        assert ids.count("Q1") == 1
        assert ids.count("Q2") == 1

    def test_tolerant_missing_description(self):
        row = _item_row(subject_description=None)
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        book_node = next(n for n in snap.nodes if n.id == _BOOK_QID)
        assert book_node.description is None

    def test_tolerant_missing_sitelinks(self):
        row = _item_row(subject_sitelinks=None)
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        book_node = next(n for n in snap.nodes if n.id == _BOOK_QID)
        assert book_node.sitelinks is None

    def test_tolerant_missing_object_id(self):
        row = _item_row(object_id=None, value_type="string")
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        assert snap.edges[0].object_id is None

    def test_sitelinks_parsed_from_string(self):
        row = _item_row(subject_sitelinks="42")
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        book_node = next(n for n in snap.nodes if n.id == _BOOK_QID)
        assert book_node.sitelinks == 42

    def test_uri_normalisation_subject(self):
        row = _item_row(subject_id="http://www.wikidata.org/entity/Q571")
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        node_ids = {n.id for n in snap.nodes}
        assert _BOOK_QID in node_ids
        assert "http://www.wikidata.org/entity/Q571" not in node_ids

    def test_uri_normalisation_object(self):
        row = _item_row(object_id="http://www.wikidata.org/entity/Q5921")
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        node_ids = {n.id for n in snap.nodes}
        assert _AUTHOR_QID in node_ids
        assert "http://www.wikidata.org/entity/Q5921" not in node_ids

    def test_uri_normalisation_property(self):
        row = _item_row(property_id="http://www.wikidata.org/prop/direct/P50")
        snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
        assert snap.edges[0].property_id == "P50"

    def test_unknown_value_type_raises(self):
        row = _item_row(value_type="bogus_type")
        with pytest.raises((ValueError, KeyError)):
            build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)

    def test_deterministic_ordering_nodes(self):
        import random

        rows = [
            _item_row(subject_id="Q3", subject_label="C", object_id="Q1", object_label="A"),
            _item_row(
                subject_id="Q1",
                subject_label="A",
                object_id="Q2",
                object_label="B",
                property_id="P99",
                property_label="rel",
            ),
            _item_row(
                subject_id="Q2",
                subject_label="B",
                object_id="Q3",
                object_label="C",
                property_id="P88",
                property_label="has",
            ),
        ]
        snap1 = build_snapshot(rows, snapshot_id="s", slice="books", domain_qid="Q1")
        shuffled = rows[:]
        random.shuffle(shuffled)
        snap2 = build_snapshot(shuffled, snapshot_id="s", slice="books", domain_qid="Q1")
        assert [n.id for n in snap1.nodes] == [n.id for n in snap2.nodes]
        assert [
            (e.subject_id, e.property_id, e.object_id) for e in snap1.edges
        ] == [(e.subject_id, e.property_id, e.object_id) for e in snap2.edges]

    def test_value_type_all_valid_variants(self):
        valid_types = ["item", "time", "quantity", "monolingual", "string"]
        for vt in valid_types:
            row = _item_row(value_type=vt, object_id=None if vt != "item" else _AUTHOR_QID)
            snap = build_snapshot([row], snapshot_id="s", slice="books", domain_qid=_BOOK_QID)
            assert snap.edges[0].value_type == ValueType(vt)

    def test_meta_default_is_dict(self):
        snap = _minimal_snapshot()
        assert isinstance(snap.meta, dict)

    def test_meta_custom_passed_through(self):
        rows = [_item_row()]
        snap = build_snapshot(
            rows, snapshot_id="s", slice="books", domain_qid=_BOOK_QID, meta={"source": "test"}
        )
        assert snap.meta["source"] == "test"


# ---------------------------------------------------------------------------
# freeze / load round-trip tests
# ---------------------------------------------------------------------------


class TestFreezeLoad:
    def test_roundtrip_reconstructs_equal_snapshot(self, tmp_path: Path):
        snap = _minimal_snapshot()
        out_dir = freeze_snapshot(snap, tmp_path)
        loaded = load_snapshot(out_dir)
        assert loaded == snap

    def test_freeze_writes_snapshot_json(self, tmp_path: Path):
        snap = _minimal_snapshot()
        out_dir = freeze_snapshot(snap, tmp_path)
        assert (out_dir / "snapshot.json").exists()

    def test_freeze_file_is_valid_json(self, tmp_path: Path):
        snap = _minimal_snapshot()
        out_dir = freeze_snapshot(snap, tmp_path)
        raw = (out_dir / "snapshot.json").read_text()
        parsed = json.loads(raw)  # must not raise
        assert isinstance(parsed, dict)

    def test_freeze_returns_path(self, tmp_path: Path):
        snap = _minimal_snapshot()
        result = freeze_snapshot(snap, tmp_path)
        assert isinstance(result, Path)

    def test_freeze_creates_dir_if_missing(self, tmp_path: Path):
        snap = _minimal_snapshot()
        new_dir = tmp_path / "nested" / "subdir"
        assert not new_dir.exists()
        freeze_snapshot(snap, new_dir)
        assert new_dir.exists()

    def test_no_pickle_file_written(self, tmp_path: Path):
        snap = _minimal_snapshot()
        out_dir = freeze_snapshot(snap, tmp_path)
        pkl_files = list(out_dir.rglob("*.pkl")) + list(out_dir.rglob("*.pickle"))
        assert pkl_files == [], f"Pickle files must not be written: {pkl_files}"

    def test_no_pickle_import_in_module(self):
        import ivg_kg.data.graph_store as gs_module

        source = inspect.getsource(gs_module)
        assert "import pickle" not in source, "graph_store.py must not import pickle"
        assert "pickle.dump" not in source
        assert "pickle.load" not in source

    def test_roundtrip_nodes_match(self, tmp_path: Path):
        snap = _minimal_snapshot()
        loaded = load_snapshot(freeze_snapshot(snap, tmp_path))
        assert len(loaded.nodes) == len(snap.nodes)
        assert {n.id for n in loaded.nodes} == {n.id for n in snap.nodes}

    def test_roundtrip_edges_match(self, tmp_path: Path):
        snap = _minimal_snapshot()
        loaded = load_snapshot(freeze_snapshot(snap, tmp_path))
        assert len(loaded.edges) == len(snap.edges)

    def test_roundtrip_deterministic_twice(self, tmp_path: Path):
        snap = _minimal_snapshot()
        d1 = tmp_path / "a"
        d2 = tmp_path / "b"
        freeze_snapshot(snap, d1)
        freeze_snapshot(snap, d2)
        text1 = (d1 / "snapshot.json").read_text()
        text2 = (d2 / "snapshot.json").read_text()
        assert text1 == text2, "Freeze output must be byte-identical on repeat calls"


# ---------------------------------------------------------------------------
# build_networkx tests
# ---------------------------------------------------------------------------


def _hand_built_snapshot(*, shared_literal: bool = False) -> KGSnapshot:
    """Snapshot with:
    - Q1 -P50-> Q2 (item edge)
    - Q1 -P577-> <literal: time 1979-03-12> (literal edge)
    - Q3 -P577-> <literal: time 1979-03-12> (shared literal, if shared_literal=True)
    """
    nodes = [
        KGNode(id="Q1", label="book", description="a book", kind="entity"),
        KGNode(id="Q2", label="author", kind="entity"),
    ]
    edges = [
        KGEdge(
            subject_id="Q1",
            property_id="P50",
            property_label="author",
            object_id="Q2",
            object_label="author",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q1",
            property_id="P577",
            property_label="publication date",
            object_id=None,
            object_label="1979-03-12",
            value_type=ValueType.TIME,
        ),
    ]
    if shared_literal:
        nodes.append(KGNode(id="Q3", label="another book", kind="entity"))
        edges.append(
            KGEdge(
                subject_id="Q3",
                property_id="P577",
                property_label="publication date",
                object_id=None,
                object_label="1979-03-12",
                value_type=ValueType.TIME,
            )
        )
    return KGSnapshot(
        snapshot_id="test-snap",
        slice="books",
        domain_qid="Q1",
        nodes=nodes,
        edges=edges,
    )


class TestBuildNetworkx:
    def test_returns_multidigraph(self):
        g = build_networkx(_hand_built_snapshot())
        assert isinstance(g, nx.MultiDiGraph)

    def test_entity_nodes_present(self):
        g = build_networkx(_hand_built_snapshot())
        assert "Q1" in g.nodes
        assert "Q2" in g.nodes

    def test_entity_node_kind_attribute(self):
        g = build_networkx(_hand_built_snapshot())
        assert g.nodes["Q1"]["kind"] == "entity"
        assert g.nodes["Q2"]["kind"] == "entity"

    def test_item_edge_directed_subject_to_object(self):
        g = build_networkx(_hand_built_snapshot())
        assert g.has_edge("Q1", "Q2"), "Directed edge Q1->Q2 must exist"

    def test_item_edge_has_property_attributes(self):
        g = build_networkx(_hand_built_snapshot())
        edge_data = list(g.get_edge_data("Q1", "Q2").values())
        assert any(e.get("property_id") == "P50" for e in edge_data)

    def test_literal_node_created(self):
        g = build_networkx(_hand_built_snapshot())
        literal_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "literal"]
        assert len(literal_nodes) >= 1, "At least one literal node must be created"

    def test_literal_node_kind_attribute(self):
        g = build_networkx(_hand_built_snapshot())
        for _n, data in g.nodes(data=True):
            if data.get("kind") == "literal":
                assert data["kind"] == "literal"

    def test_literal_edge_directed_subject_to_literal(self):
        g = build_networkx(_hand_built_snapshot())
        literal_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "literal"]
        assert len(literal_nodes) >= 1
        lit_id = literal_nodes[0]
        assert g.has_edge("Q1", lit_id), f"Directed edge Q1->{lit_id} must exist"

    def test_literal_node_id_is_stable(self):
        """Same value_type + object_label must produce the same literal node id."""
        snap = _hand_built_snapshot()
        g1 = build_networkx(snap)
        g2 = build_networkx(snap)
        lit1 = {n for n, d in g1.nodes(data=True) if d.get("kind") == "literal"}
        lit2 = {n for n, d in g2.nodes(data=True) if d.get("kind") == "literal"}
        assert lit1 == lit2

    def test_shared_literal_node_for_equal_literals(self):
        """Two subjects with identical literal values share ONE literal node."""
        snap = _hand_built_snapshot(shared_literal=True)
        g = build_networkx(snap)
        literal_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "literal"]
        # Should have exactly one literal node for 1979-03-12 (time)
        matching = [
            n
            for n in literal_nodes
            if g.nodes[n].get("object_label") == "1979-03-12"
            or "1979-03-12" in n  # id-based check as fallback
        ]
        assert len(matching) == 1, (
            "Two subjects with same literal must share ONE literal node, got: "
            f"{literal_nodes}"
        )

    def test_shared_literal_has_two_in_edges(self):
        """The shared literal node must be reachable from both subjects."""
        snap = _hand_built_snapshot(shared_literal=True)
        g = build_networkx(snap)
        literal_nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == "literal"]
        # The shared literal should have in-degree of 2 (Q1 and Q3 both point to it)
        shared = next(n for n in literal_nodes if "1979-03-12" in n or g.in_degree(n) >= 2)
        assert g.in_degree(shared) >= 2, (
            f"Shared literal node {shared} must have in-degree >= 2 (Q1 and Q3)"
        )

    def test_entity_nodes_not_marked_literal(self):
        g = build_networkx(_hand_built_snapshot())
        for qid in ["Q1", "Q2"]:
            assert g.nodes[qid].get("kind") != "literal", f"{qid} must not be marked literal"

    def test_node_label_attribute(self):
        g = build_networkx(_hand_built_snapshot())
        assert g.nodes["Q1"]["label"] == "book"

    def test_rebuilding_from_json_gives_equal_graph(self, tmp_path: Path):
        snap = _hand_built_snapshot()
        out_dir = freeze_snapshot(snap, tmp_path)
        loaded_snap = load_snapshot(out_dir)
        g_orig = build_networkx(snap)
        g_loaded = build_networkx(loaded_snap)
        assert set(g_orig.nodes()) == set(g_loaded.nodes())
        assert set(g_orig.edges()) == set(g_loaded.edges())

    def test_deterministic_node_set(self):
        snap = _hand_built_snapshot(shared_literal=True)
        g1 = build_networkx(snap)
        g2 = build_networkx(snap)
        assert set(g1.nodes()) == set(g2.nodes())
        assert set(g1.edges()) == set(g2.edges())


# ---------------------------------------------------------------------------
# nx_to_cyto_elements tests
# ---------------------------------------------------------------------------


class TestNxToCytoElements:
    def _get_node_ids(self, elements: list[dict]) -> set[str]:
        return {e["data"]["id"] for e in elements if "source" not in e["data"]}

    def _get_edges(self, elements: list[dict]) -> list[dict]:
        return [e for e in elements if "source" in e["data"]]

    def test_returns_list_of_dicts(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        assert isinstance(elements, list)
        assert all(isinstance(e, dict) for e in elements)

    def test_entity_nodes_present(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        node_ids = self._get_node_ids(elements)
        assert _BOOK_QID in node_ids
        assert _AUTHOR_QID in node_ids

    def test_literal_nodes_present_in_elements(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        node_ids = self._get_node_ids(elements)
        literal_ids = [nid for nid in node_ids if nid.startswith("lit:")]
        assert len(literal_ids) >= 1, "Literal node must appear in cytoscape elements"

    def test_referential_integrity(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        node_ids = self._get_node_ids(elements)
        for edge in self._get_edges(elements):
            src = edge["data"]["source"]
            tgt = edge["data"]["target"]
            assert src in node_ids, f"Edge source {src!r} has no node element"
            assert tgt in node_ids, f"Edge target {tgt!r} has no node element"

    def test_edge_id_convention_item_edge(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        edges = self._get_edges(elements)
        # Item edge: Q571-P50-Q5921
        item_edge = next((e for e in edges if e["data"].get("source") == _BOOK_QID
                          and e["data"].get("target") == _AUTHOR_QID), None)
        assert item_edge is not None, "Item edge Q571->Q5921 must be present"
        expected_id = f"{_BOOK_QID}-P50-{_AUTHOR_QID}"
        assert item_edge["data"]["id"] == expected_id, (
            f"Edge id must be '{expected_id}', got '{item_edge['data']['id']}'"
        )

    def test_edge_id_convention_literal_edge(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        edges = self._get_edges(elements)
        node_ids = self._get_node_ids(elements)
        lit_ids = [nid for nid in node_ids if nid.startswith("lit:")]
        assert len(lit_ids) >= 1
        lit_id = lit_ids[0]
        lit_edge = next(
            (e for e in edges if e["data"].get("target") == lit_id),
            None,
        )
        assert lit_edge is not None, f"No edge pointing to literal node {lit_id}"
        # id must follow <subject>-<property>-<literal_node_id>
        eid = lit_edge["data"]["id"]
        assert eid == f"{_BOOK_QID}-P577-{lit_id}", (
            f"Literal edge id must be '<subj>-<prop>-<lit_id>', got '{eid}'"
        )

    def test_node_data_has_id_and_label(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        for el in elements:
            if "source" not in el["data"]:
                assert "id" in el["data"]
                assert "label" in el["data"]

    def test_edge_data_has_source_target_label(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        for el in self._get_edges(elements):
            data = el["data"]
            assert "source" in data
            assert "target" in data
            assert "label" in data

    def test_deterministic_output(self):
        snap = _minimal_snapshot()
        e1 = nx_to_cyto_elements(snap)
        e2 = nx_to_cyto_elements(snap)
        assert e1 == e2, "nx_to_cyto_elements must be deterministic"

    def test_no_duplicate_node_ids(self):
        snap = _minimal_snapshot()
        elements = nx_to_cyto_elements(snap)
        node_ids = [e["data"]["id"] for e in elements if "source" not in e["data"]]
        assert len(node_ids) == len(set(node_ids)), "Duplicate node ids in cyto elements"

    def test_surfaces_image_path_and_description_when_present(self):
        """Node data carries image_path + description so the UI entity-detail
        pane can show the entity image (SPEC-text §4.5)."""
        snap = KGSnapshot(
            snapshot_id="img-snap",
            slice="books",
            domain_qid="Q571",
            nodes=[
                KGNode(
                    id="Q1",
                    label="author",
                    description="a novelist",
                    image_path="https://example.org/portrait.jpg",
                    kind="entity",
                ),
                KGNode(id="Q2", label="book", kind="entity"),
            ],
            edges=[
                KGEdge(
                    subject_id="Q2",
                    property_id="P50",
                    property_label="author",
                    object_id="Q1",
                    object_label="author",
                    value_type=ValueType.ITEM,
                ),
            ],
        )
        nodes = {
            e["data"]["id"]: e["data"]
            for e in nx_to_cyto_elements(snap)
            if "source" not in e["data"]
        }
        assert nodes["Q1"]["image_path"] == "https://example.org/portrait.jpg"
        assert nodes["Q1"]["description"] == "a novelist"
        # Node without an image_path must not carry the key (kept clean).
        assert "image_path" not in nodes["Q2"]
