"""
Tests for src/ivg_kg/data/wikidata.py.

All tests run with NO network and do NOT require the `data` extra.
Pure-function tests (band filter, property-type filter, cache key) only
use stdlib + ivg_kg.config/ivg_kg.schema.
Client tests inject a fake _fetch callable to avoid real HTTP.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ivg_kg.config import BAND_HI, BAND_LO

# ---------------------------------------------------------------------------
# Pure-function imports — must work without requests installed
# ---------------------------------------------------------------------------
from ivg_kg.data.wikidata import (
    WikidataClient,
    datatype_to_value_type,
    keep_property_type,
    query_cache_key,
    sitelink_band_filter,
)
from ivg_kg.schema import ValueType

# ===========================================================================
# sitelink_band_filter
# ===========================================================================


class TestSitelinkBandFilter:
    def _make_items(self, counts: list[int | None]) -> list[dict]:
        return [{"id": f"Q{i}", "sitelinks": c} for i, c in enumerate(counts)]

    def test_empty_input_returns_empty(self) -> None:
        assert sitelink_band_filter([]) == []

    def test_lo_boundary_kept(self) -> None:
        items = self._make_items([BAND_LO])
        result = sitelink_band_filter(items)
        assert len(result) == 1

    def test_hi_boundary_kept(self) -> None:
        items = self._make_items([BAND_HI])
        result = sitelink_band_filter(items)
        assert len(result) == 1

    def test_lo_minus_one_dropped(self) -> None:
        items = self._make_items([BAND_LO - 1])
        result = sitelink_band_filter(items)
        assert result == []

    def test_hi_plus_one_dropped(self) -> None:
        items = self._make_items([BAND_HI + 1])
        result = sitelink_band_filter(items)
        assert result == []

    def test_none_count_dropped(self) -> None:
        items = self._make_items([None])
        result = sitelink_band_filter(items)
        assert result == []

    def test_missing_key_dropped(self) -> None:
        items = [{"id": "Q1"}]  # no 'sitelinks' key
        result = sitelink_band_filter(items)
        assert result == []

    def test_mid_range_kept(self) -> None:
        mid = (BAND_LO + BAND_HI) // 2
        items = self._make_items([BAND_LO - 1, mid, BAND_HI + 1])
        result = sitelink_band_filter(items)
        assert len(result) == 1
        assert result[0]["sitelinks"] == mid

    def test_custom_band(self) -> None:
        items = self._make_items([10, 20, 30])
        result = sitelink_band_filter(items, band=(15, 25))
        assert len(result) == 1
        assert result[0]["sitelinks"] == 20

    def test_custom_count_key(self) -> None:
        items = [{"id": "Q1", "links": 10}, {"id": "Q2", "links": 3}]
        result = sitelink_band_filter(items, band=(5, 40), count_key="links")
        assert len(result) == 1
        assert result[0]["id"] == "Q1"

    def test_returns_original_item_dicts(self) -> None:
        item = {"id": "Q1", "sitelinks": BAND_LO, "extra": "data"}
        result = sitelink_band_filter([item])
        assert result[0] is item


# ===========================================================================
# keep_property_type
# ===========================================================================


class TestKeepPropertyType:
    # Short names (as returned by WDQS "datatype" field)
    def test_wikibase_item_kept(self) -> None:
        assert keep_property_type("WikibaseItem") is True

    def test_time_kept(self) -> None:
        assert keep_property_type("Time") is True

    def test_quantity_kept(self) -> None:
        assert keep_property_type("Quantity") is True

    def test_monolingualtext_kept(self) -> None:
        assert keep_property_type("Monolingualtext") is True

    def test_string_kept(self) -> None:
        assert keep_property_type("String") is True

    def test_external_id_dropped(self) -> None:
        assert keep_property_type("ExternalId") is False

    def test_url_dropped(self) -> None:
        assert keep_property_type("Url") is False

    def test_commons_media_dropped(self) -> None:
        assert keep_property_type("CommonsMedia") is False

    def test_globe_coordinate_dropped(self) -> None:
        assert keep_property_type("GlobeCoordinate") is False

    def test_unknown_type_dropped(self) -> None:
        assert keep_property_type("SomethingElse") is False

    # URI / prefixed forms
    def test_uri_wikibase_item_kept(self) -> None:
        assert keep_property_type("http://wikiba.se/ontology#WikibaseItem") is True

    def test_uri_time_kept(self) -> None:
        assert keep_property_type("http://wikiba.se/ontology#Time") is True

    def test_uri_quantity_kept(self) -> None:
        assert keep_property_type("http://wikiba.se/ontology#Quantity") is True

    def test_uri_monolingualtext_kept(self) -> None:
        assert keep_property_type("http://wikiba.se/ontology#Monolingualtext") is True

    def test_uri_string_kept(self) -> None:
        assert keep_property_type("http://wikiba.se/ontology#String") is True

    # Hyphenated forms (wikibase-item style, seen in some integrator outputs)
    def test_hyphen_wikibase_item_kept(self) -> None:
        assert keep_property_type("wikibase-item") is True

    def test_hyphen_time_kept(self) -> None:
        assert keep_property_type("time") is True

    def test_hyphen_quantity_kept(self) -> None:
        assert keep_property_type("quantity") is True

    def test_hyphen_monolingualtext_kept(self) -> None:
        assert keep_property_type("monolingualtext") is True

    def test_hyphen_string_kept(self) -> None:
        assert keep_property_type("string") is True

    def test_empty_string_dropped(self) -> None:
        assert keep_property_type("") is False


# ===========================================================================
# datatype_to_value_type
# ===========================================================================


class TestDatatypeToValueType:
    def test_wikibase_item_maps_to_item(self) -> None:
        assert datatype_to_value_type("WikibaseItem") == ValueType.ITEM

    def test_time_maps_to_time(self) -> None:
        assert datatype_to_value_type("Time") == ValueType.TIME

    def test_quantity_maps_to_quantity(self) -> None:
        assert datatype_to_value_type("Quantity") == ValueType.QUANTITY

    def test_monolingualtext_maps_to_monolingual(self) -> None:
        assert datatype_to_value_type("Monolingualtext") == ValueType.MONOLINGUAL

    def test_string_maps_to_string(self) -> None:
        assert datatype_to_value_type("String") == ValueType.STRING

    def test_uri_form_maps_correctly(self) -> None:
        assert datatype_to_value_type("http://wikiba.se/ontology#WikibaseItem") == ValueType.ITEM

    def test_hyphen_form_maps_correctly(self) -> None:
        assert datatype_to_value_type("wikibase-item") == ValueType.ITEM

    def test_non_kept_type_returns_none(self) -> None:
        assert datatype_to_value_type("ExternalId") is None

    def test_unknown_returns_none(self) -> None:
        assert datatype_to_value_type("Gibberish") is None


# ===========================================================================
# query_cache_key
# ===========================================================================


class TestQueryCacheKey:
    def test_same_inputs_same_key(self) -> None:
        k1 = query_cache_key("SELECT ?x WHERE {}", "https://example.com/sparql")
        k2 = query_cache_key("SELECT ?x WHERE {}", "https://example.com/sparql")
        assert k1 == k2

    def test_different_query_different_key(self) -> None:
        k1 = query_cache_key("SELECT ?x WHERE {}", "https://example.com/sparql")
        k2 = query_cache_key("SELECT ?y WHERE {}", "https://example.com/sparql")
        assert k1 != k2

    def test_different_endpoint_different_key(self) -> None:
        k1 = query_cache_key("SELECT ?x WHERE {}", "https://endpoint-a.com/sparql")
        k2 = query_cache_key("SELECT ?x WHERE {}", "https://endpoint-b.com/sparql")
        assert k1 != k2

    def test_key_is_hex_string(self) -> None:
        k = query_cache_key("q", "e")
        assert isinstance(k, str)
        int(k, 16)  # must be valid hex

    def test_key_length_is_64(self) -> None:
        # sha256 hexdigest = 64 chars
        k = query_cache_key("q", "e")
        assert len(k) == 64

    def test_matches_manual_sha256(self) -> None:
        query = "SELECT ?item WHERE {}"
        endpoint = "https://query.wikidata.org/sparql"
        expected = hashlib.sha256((endpoint + "\n" + query).encode()).hexdigest()
        assert query_cache_key(query, endpoint) == expected


# ===========================================================================
# WikidataClient — injected fetch, no network
# ===========================================================================


def _sparql_response(bindings: list[dict[str, Any]]) -> dict:
    """Build a minimal SPARQL JSON response."""
    return {
        "results": {
            "bindings": bindings
        }
    }


def _item_binding(item_uri: str, label: str) -> dict[str, Any]:
    return {
        "item": {"type": "uri", "value": item_uri},
        "itemLabel": {"type": "literal", "value": label},
    }


class TestWikidataClientCache:
    def test_cache_hit_skips_fetch(self, tmp_path: Path) -> None:
        call_count = 0

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            nonlocal call_count
            call_count += 1
            return _sparql_response([_item_binding("http://www.wikidata.org/entity/Q571", "book")])

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        query = "SELECT ?item WHERE { wd:Q571 wdt:P31 ?item }"

        rows1 = client.run_query(query)
        rows2 = client.run_query(query)  # should hit cache

        assert call_count == 1
        assert rows1 == rows2

    def test_cache_written_to_disk(self, tmp_path: Path) -> None:
        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            return _sparql_response([_item_binding("http://www.wikidata.org/entity/Q571", "book")])

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        query = "SELECT ?item WHERE { wd:Q571 wdt:P31 ?item }"
        client.run_query(query)

        cache_files = list(tmp_path.glob("*.json"))
        assert len(cache_files) == 1

    def test_cached_file_is_valid_json(self, tmp_path: Path) -> None:
        payload = _sparql_response([_item_binding("http://www.wikidata.org/entity/Q571", "book")])

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            return payload

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        client.run_query("SELECT ?item WHERE {}")

        cache_file = next(tmp_path.glob("*.json"))
        with cache_file.open() as f:
            data = json.load(f)
        assert "results" in data

    def test_different_queries_different_cache_files(self, tmp_path: Path) -> None:
        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            return _sparql_response([])

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        client.run_query("SELECT ?a WHERE {}")
        client.run_query("SELECT ?b WHERE {}")

        assert len(list(tmp_path.glob("*.json"))) == 2


class TestWikidataClientRetry:
    def test_retries_on_429_then_succeeds(self, tmp_path: Path) -> None:
        attempt = 0

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise _HttpError(429, "Too Many Requests")
            return _sparql_response([_item_binding("http://www.wikidata.org/entity/Q1", "item")])

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        rows = client.run_query("SELECT ?item WHERE {}")
        assert attempt == 2
        assert len(rows) == 1

    def test_retries_on_503_then_succeeds(self, tmp_path: Path) -> None:
        attempt = 0

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            nonlocal attempt
            attempt += 1
            if attempt <= 2:
                raise _HttpError(503, "Service Unavailable")
            return _sparql_response([])

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        rows = client.run_query("SELECT ?item WHERE {}")
        assert attempt == 3
        assert rows == []

    def test_exhausted_retries_falls_back_to_qlever(self, tmp_path: Path) -> None:
        wdqs_calls = 0
        qlever_calls = 0

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            nonlocal wdqs_calls, qlever_calls
            from ivg_kg.config import QLEVER_ENDPOINT
            if url == QLEVER_ENDPOINT:
                qlever_calls += 1
                return _sparql_response([
                    _item_binding("http://www.wikidata.org/entity/Q2", "qlever-item")
                ])
            else:
                wdqs_calls += 1
                raise _HttpError(503, "Service Unavailable")

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        rows = client.run_query("SELECT ?item WHERE {}")

        assert qlever_calls == 1
        assert len(rows) == 1

    def test_sleep_called_between_retries(self, tmp_path: Path) -> None:
        sleep_calls: list[float] = []
        attempt = 0

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise _HttpError(429, "Too Many Requests")
            return _sparql_response([])

        def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=fake_sleep)
        client.run_query("SELECT ?item WHERE {}")
        assert len(sleep_calls) >= 1


class TestWikidataClientDeterminism:
    def test_rows_sorted_stably(self, tmp_path: Path) -> None:
        bindings = [
            _item_binding("http://www.wikidata.org/entity/Q3", "c"),
            _item_binding("http://www.wikidata.org/entity/Q1", "a"),
            _item_binding("http://www.wikidata.org/entity/Q2", "b"),
        ]

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            return _sparql_response(bindings)

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        rows = client.run_query("SELECT ?item WHERE {}")

        # The rows must come back in a stable, deterministic order.
        keys = [list(r.values())[0] for r in rows]
        assert keys == sorted(keys)


class TestWikidataClientRowShape:
    def test_row_is_dict_of_string_values(self, tmp_path: Path) -> None:
        bindings = [
            {
                "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q571"},
                "itemLabel": {"type": "literal", "value": "book"},
                "itemDescription": {"type": "literal", "value": "written work"},
            }
        ]

        def fake_fetch(url: str, params: dict, headers: dict) -> dict:
            return _sparql_response(bindings)

        client = WikidataClient(cache_dir=tmp_path, _fetch=fake_fetch, _sleep=lambda s: None)
        rows = client.run_query("SELECT ?item ?itemLabel ?itemDescription WHERE {}")

        assert len(rows) == 1
        row = rows[0]
        assert isinstance(row, dict)
        # Each value is the raw string from the SPARQL binding "value" field
        assert row["item"] == "http://www.wikidata.org/entity/Q571"
        assert row["itemLabel"] == "book"
        assert row["itemDescription"] == "written work"


# ---------------------------------------------------------------------------
# Helper: minimal HTTP error used by fake_fetch implementations
# ---------------------------------------------------------------------------


class _HttpError(Exception):
    """Simulated HTTP error with a status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
