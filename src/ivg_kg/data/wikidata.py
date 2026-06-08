"""
Wikidata pull client for IVG-KG (SPEC §4.1).

Public API
----------
sitelink_band_filter(items, band=SITELINK_BAND, *, count_key="sitelinks")
    Pure filter: keep items whose sitelink count falls in [lo, hi] inclusive.
    Items with missing/None count are dropped.

keep_property_type(datatype: str) -> bool
    Pure predicate: True if the Wikidata datatype string represents one of
    the kept types (WikibaseItem, Time, Quantity, Monolingualtext, String).
    Handles short names, URI forms, and lower-case/hyphen forms.

datatype_to_value_type(datatype: str) -> ValueType | None
    Maps a kept Wikidata datatype to schema.ValueType.  Returns None for
    dropped or unknown types.

query_cache_key(query: str, endpoint: str) -> str
    Returns sha256(endpoint + "\\n" + query) as a 64-char hex string.

WikidataClient
    Runs a SPARQL SELECT against WDQS with User-Agent, rate-limiting,
    exponential backoff on 429/5xx, disk cache (data/cache/<key>.json),
    and automatic fallback to QLever when WDQS exhausts retries.

Row shape contract
------------------
run_query returns list[dict[str, str]].  Each dict mirrors the SPARQL JSON
bindings: keys are the variable names from the SELECT clause; values are the
raw "value" strings (URI strings for items, literal strings for labels/descs).
Rows are sorted by the string value of the first column for determinism.

    Example row:
    {
        "item":            "http://www.wikidata.org/entity/Q571",
        "itemLabel":       "book",
        "itemDescription": "written work published as a single unit",
        "propLabel":       "instance of",
        "valueLabel":      "written work",
        "datatype":        "WikibaseItem",
    }

DA2 (graph_store.py) consumes these rows to build KGSnapshot.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ivg_kg.config import (
    QLEVER_ENDPOINT,
    SITELINK_BAND,
    WDQS_ENDPOINT,
    WDQS_USER_AGENT,
)
from ivg_kg.schema import ValueType

# ---------------------------------------------------------------------------
# Internals: datatype normalisation tables
# ---------------------------------------------------------------------------

# Canonical short names that are KEPT.
_KEPT_SHORT: frozenset[str] = frozenset(
    {"WikibaseItem", "Time", "Quantity", "Monolingualtext", "String"}
)

# Mapping: normalised short name -> ValueType
_SHORT_TO_VALUE_TYPE: dict[str, ValueType] = {
    "WikibaseItem": ValueType.ITEM,
    "Time": ValueType.TIME,
    "Quantity": ValueType.QUANTITY,
    "Monolingualtext": ValueType.MONOLINGUAL,
    "String": ValueType.STRING,
}

# URI prefix used by WDQS / wikiba.se ontology
_WIKIBASE_URI_PREFIX = "http://wikiba.se/ontology#"

# Lower-case / hyphen aliases seen in WikibaseIntegrator and WDQS output
_ALIAS_MAP: dict[str, str] = {
    "wikibase-item": "WikibaseItem",
    "item": "WikibaseItem",
    "time": "Time",
    "quantity": "Quantity",
    "monolingualtext": "Monolingualtext",
    "string": "String",
}


def _normalise_datatype(datatype: str) -> str | None:
    """Return the canonical short name for a Wikidata datatype, or None."""
    if not datatype:
        return None
    # Already a short canonical name
    if datatype in _KEPT_SHORT:
        return datatype
    # URI form: http://wikiba.se/ontology#WikibaseItem
    if datatype.startswith(_WIKIBASE_URI_PREFIX):
        short = datatype[len(_WIKIBASE_URI_PREFIX):]
        if short in _KEPT_SHORT:
            return short
    # Lower-case / hyphen alias
    return _ALIAS_MAP.get(datatype.lower())


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def sitelink_band_filter(
    items: list[dict[str, Any]],
    band: tuple[int, int] = SITELINK_BAND,
    *,
    count_key: str = "sitelinks",
) -> list[dict[str, Any]]:
    """Keep items whose sitelink count is in [lo, hi] inclusive.

    Items that are missing the count key or have a None count are dropped.

    Args:
        items:     List of item dicts (arbitrary payloads).
        band:      (lo, hi) inclusive range; defaults to config.SITELINK_BAND.
        count_key: Dict key holding the sitelink count; defaults to "sitelinks".

    Returns:
        Filtered list preserving original dict identity (no copies).
    """
    lo, hi = band
    result: list[dict[str, Any]] = []
    for item in items:
        count = item.get(count_key)
        if count is None:
            continue
        if lo <= count <= hi:
            result.append(item)
    return result


def keep_property_type(datatype: str) -> bool:
    """Return True if this Wikidata datatype should be kept.

    Kept types: WikibaseItem, Time, Quantity, Monolingualtext, String.
    Handles short names, URI forms (http://wikiba.se/ontology#…), and
    lower-case/hyphen aliases (wikibase-item, time, etc.).
    """
    return _normalise_datatype(datatype) is not None


def datatype_to_value_type(datatype: str) -> ValueType | None:
    """Map a Wikidata datatype string to schema.ValueType.

    Returns None for dropped or unknown datatypes.
    """
    canonical = _normalise_datatype(datatype)
    if canonical is None:
        return None
    return _SHORT_TO_VALUE_TYPE.get(canonical)


def query_cache_key(query: str, endpoint: str) -> str:
    """Return a 64-char SHA-256 hex digest keyed by endpoint + query.

    Deterministic: identical inputs always produce the same key.
    Different queries or endpoints always produce different keys.
    """
    payload = (endpoint + "\n" + query).encode()
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# HTTP helpers (lazy imports — only loaded when doing network I/O)
# ---------------------------------------------------------------------------


def _default_fetch(url: str, params: dict, headers: dict) -> dict:
    """Send a GET request and return the parsed JSON body.

    Raises _HttpError on non-2xx status.
    This is the DEFAULT fetch implementation; tests inject a replacement.
    Lazy import of `requests` so the module can be imported without the
    `data` extra installed.
    """
    import requests  # noqa: PLC0415  (lazy import — intentional)

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if not resp.ok:
        raise _HttpError(resp.status_code, resp.text)
    return resp.json()


class _HttpError(Exception):
    """Raised by _default_fetch and injected fakes on non-2xx responses."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# WikidataClient
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds; doubles each retry


class WikidataClient:
    """SPARQL client for Wikidata with caching, retry, and QLever fallback.

    Constructor parameters
    ----------------------
    cache_dir : Path
        Directory for JSON cache files.  Created on first use.  Defaults to
        ``data/cache`` relative to the current working directory.
    _fetch : callable, optional
        Injectable HTTP fetch function with signature
        ``(url: str, params: dict, headers: dict) -> dict``.
        Defaults to a real requests.get wrapper.  Override in tests to avoid
        network I/O.
    _sleep : callable, optional
        Injectable sleep function ``(seconds: float) -> None``.
        Defaults to ``time.sleep``.  Override in tests to skip actual waiting.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        _fetch: Callable[[str, dict, dict], dict] | None = None,
        _sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir is not None else Path("data/cache")
        self._fetch = _fetch if _fetch is not None else _default_fetch
        self._sleep = _sleep if _sleep is not None else time.sleep

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run_query(
        self,
        query: str,
        endpoint: str = WDQS_ENDPOINT,
    ) -> list[dict[str, str]]:
        """Run a SPARQL SELECT query and return a list of row dicts.

        Checks the disk cache first.  On a miss, fetches from ``endpoint``
        with backoff retry.  Falls back to QLever if WDQS exhausts retries.
        Results are always sorted by the first column value for determinism.

        Row shape: dict[variable_name -> raw_value_string]
        """
        cache_key = query_cache_key(query, endpoint)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return self._bindings_to_rows(cached)

        response = self._fetch_with_retry(query, endpoint)
        self._save_cache(cache_key, response)
        return self._bindings_to_rows(response)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, query: str, endpoint: str) -> dict:
        """Fetch with exponential backoff; fall back to QLever on exhaustion."""
        headers = {
            "User-Agent": WDQS_USER_AGENT,
            "Accept": "application/sparql-results+json",
        }
        params = {"query": query, "format": "json"}

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return self._fetch(endpoint, params, headers)
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None)
                if status is not None and status in (429, 500, 502, 503, 504):
                    last_exc = exc
                    backoff = _BASE_BACKOFF * (2**attempt)
                    self._sleep(backoff)
                elif status is not None:
                    # Non-retryable HTTP error — re-raise immediately
                    raise
                elif isinstance(exc, OSError):
                    # Connection-level errors (timeout, DNS, etc.)
                    last_exc = exc
                    backoff = _BASE_BACKOFF * (2**attempt)
                    self._sleep(backoff)
                else:
                    raise

        # WDQS exhausted — fall back to QLever if not already using it
        if endpoint != QLEVER_ENDPOINT:
            return self._fetch_with_retry(query, QLEVER_ENDPOINT)

        # QLever also failed — re-raise the last error
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("SPARQL fetch failed with no error recorded")

    def _load_cache(self, cache_key: str) -> dict | None:
        """Return the cached JSON dict, or None on cache miss."""
        cache_file = self._cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with cache_file.open() as f:
                return json.load(f)
        return None

    def _save_cache(self, cache_key: str, response: dict) -> None:
        """Write the SPARQL JSON response to disk (raw JSON, never pickle)."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / f"{cache_key}.json"
        with cache_file.open("w") as f:
            json.dump(response, f)

    @staticmethod
    def _bindings_to_rows(response: dict) -> list[dict[str, str]]:
        """Convert SPARQL JSON bindings to a sorted list of flat string dicts.

        Each binding dict like ``{"item": {"type": "uri", "value": "..."}}``
        becomes ``{"item": "..."}``.  Rows are sorted by the first key's value
        so that results are deterministic regardless of endpoint order.
        """
        bindings: list[dict] = response.get("results", {}).get("bindings", [])
        rows: list[dict[str, str]] = [
            {var: cell["value"] for var, cell in binding.items()}
            for binding in bindings
        ]
        if not rows:
            return rows
        # Sort by first column value for stable, reproducible ordering
        first_key = next(iter(rows[0]))
        rows.sort(key=lambda r: r.get(first_key, ""))
        return rows
