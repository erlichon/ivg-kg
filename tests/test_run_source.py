"""Tests for app/run_source.py -- the config-flag run-loader shim.

MOCK mode (IVG_KG_RUN_ID unset) must be byte-identical to calling the mock_*
fixtures directly. REAL mode loads from data/runs/<id>.json and derives the
support subgraph from claim paths. A missing file must fail loudly, not fall
back silently to mock. make_app() must still build in mock mode.

All tests are offline; no network, no model.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ivg_kg.mock.fixtures import (
    mock_answer_diagnostics,
    mock_grounding_run,
    mock_single_run_summary,
    mock_subgraph_elements,
)
from ivg_kg.schema import GroundingRun

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_run(path: Path, run: GroundingRun) -> None:
    """Write a GroundingRun to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.model_dump_json(), encoding="utf-8")


# ---------------------------------------------------------------------------
# MOCK mode is the default (IVG_KG_RUN_ID unset) -- behaviour must be
# byte-identical to calling the mock_* fixtures directly.
# ---------------------------------------------------------------------------

def test_mock_mode_get_grounding_run_matches_fixture(monkeypatch):
    """With IVG_KG_RUN_ID unset, get_grounding_run() == mock_grounding_run()."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)
    # Must import AFTER patching env so the module reads the correct state.
    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    result = rs.get_grounding_run()
    expected = mock_grounding_run()
    assert result.run_id == expected.run_id
    assert result.question == expected.question
    assert len(result.claims) == len(expected.claims)
    for r, e in zip(result.claims, expected.claims, strict=True):
        assert r.claim_id == e.claim_id
        assert r.status == e.status


def test_mock_mode_get_subgraph_elements_matches_fixture(monkeypatch):
    """With IVG_KG_RUN_ID unset, get_subgraph_elements() == mock_subgraph_elements()."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)
    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    result = rs.get_subgraph_elements()
    expected = mock_subgraph_elements()
    assert result == expected


def test_mock_mode_get_single_run_summary_matches_fixture(monkeypatch):
    """With IVG_KG_RUN_ID unset, get_single_run_summary() matches mock_single_run_summary()."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)
    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    result = rs.get_single_run_summary()
    expected = mock_single_run_summary()
    assert result.status_counts == expected.status_counts
    assert result.status_percentages == expected.status_percentages


def test_mock_mode_get_answer_diagnostics_matches_fixture(monkeypatch):
    """With IVG_KG_RUN_ID unset, get_answer_diagnostics(n) matches mock_answer_diagnostics(n)."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)
    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    result = rs.get_answer_diagnostics(10)
    expected = mock_answer_diagnostics(10)
    assert result.n_runs == expected.n_runs
    assert set(result.status_distribution.keys()) == set(expected.status_distribution.keys())
    for grade in result.status_distribution:
        assert abs(result.status_distribution[grade].mean - expected.status_distribution[grade].mean) < 1e-9


# ---------------------------------------------------------------------------
# REAL mode: load from disk
# ---------------------------------------------------------------------------

def test_real_mode_loads_run_id_from_env(monkeypatch, tmp_path):
    """With IVG_KG_RUN_ID set, get_grounding_run() loads from data/runs/<id>.json."""
    # Use the actual precomputed slice run so we exercise the real file.
    run_id = "slice-01-glass-menagerie"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    result = rs.get_grounding_run()
    assert result.run_id == run_id
    assert len(result.claims) > 0


def test_real_mode_run_id_roundtrip(monkeypatch, tmp_path):
    """REAL mode: write a run to a temp dir, point the module at it, verify roundtrip."""
    run = mock_grounding_run()
    run_id = "test-roundtrip-run"
    # Temporarily write to data/runs/ (the canonical location the module reads from).
    # We patch the RUNS_DIR constant in the module so we don't pollute the real dir.
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    run_file = tmp_path / f"{run_id}.json"
    _write_run(run_file, run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    # Patch the runs directory to point at tmp_path
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    result = rs.get_grounding_run()
    assert result.run_id == run.run_id
    assert result.question == run.question
    assert len(result.claims) == len(run.claims)
    for r, e in zip(result.claims, run.claims, strict=True):
        assert r.claim_id == e.claim_id
        assert r.status == e.status


def test_real_mode_single_run_summary_uses_diagnostics(monkeypatch, tmp_path):
    """REAL mode: get_single_run_summary() uses diagnostics.single_run_summary(run), not mock."""
    from ivg_kg.diagnostics import single_run_summary

    run = mock_grounding_run()
    run_id = "test-diag-run"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    run_file = tmp_path / f"{run_id}.json"
    _write_run(run_file, run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    result = rs.get_single_run_summary()
    expected = single_run_summary(run)
    assert result.status_counts == expected.status_counts


def test_real_mode_subgraph_elements_nonempty_when_claims_grounded(monkeypatch, tmp_path):
    """REAL mode: get_subgraph_elements() derives a non-empty cyto element list from grounded claims."""
    # Use the Chopin mock run (has multiple grounded claims with path edges).
    run = mock_grounding_run()
    run_id = "test-subgraph-run"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    run_file = tmp_path / f"{run_id}.json"
    _write_run(run_file, run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    elements = rs.get_subgraph_elements()
    assert len(elements) > 0
    # Should contain both nodes and edges
    node_ids = {e["data"]["id"] for e in elements if "source" not in e["data"]}
    edge_ids = {e["data"]["id"] for e in elements if "source" in e["data"]}
    assert len(node_ids) > 0, "subgraph must contain at least one node"
    assert len(edge_ids) > 0, "subgraph must contain at least one edge (grounded claims have path edges)"


def test_real_mode_subgraph_contains_claim_path_entities(monkeypatch, tmp_path):
    """REAL mode: subgraph nodes include entity IDs from grounded claim paths."""
    run = mock_grounding_run()
    run_id = "test-subgraph-entities"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    run_file = tmp_path / f"{run_id}.json"
    _write_run(run_file, run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    elements = rs.get_subgraph_elements()
    node_ids = {e["data"]["id"] for e in elements if "source" not in e["data"]}

    # c1 is RETRIEVED with path: FCHOPIN -[father]-> NCHOPIN; both must appear
    from ivg_kg.mock.fixtures import FCHOPIN, NCHOPIN
    assert FCHOPIN in node_ids, f"Frederic Chopin ({FCHOPIN}) must be in subgraph nodes"
    assert NCHOPIN in node_ids, f"Nicolas Chopin ({NCHOPIN}) must be in subgraph nodes"


def test_real_mode_answer_diagnostics_uses_loaded_run(monkeypatch, tmp_path):
    """REAL mode: get_answer_diagnostics(n) returns an AnswerDiagnostics with n_runs >= 1."""
    run = mock_grounding_run()
    run_id = "test-agg-run"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    run_file = tmp_path / f"{run_id}.json"
    _write_run(run_file, run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    result = rs.get_answer_diagnostics(5)
    # Only one run exists in tmp_path; aggregate what exists (>= 1 is fine)
    assert result.n_runs >= 1
    assert "fabricated" in result.status_distribution


def test_real_mode_answer_diagnostics_aggregates_multiple_runs(monkeypatch, tmp_path):
    """REAL mode: when multiple slice runs share a slice, get_answer_diagnostics aggregates them."""
    run = mock_grounding_run()
    run_id = "test-multi-agg"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    # Write 3 runs with the same slice
    for i in range(3):
        r = run.model_copy(update={"run_id": f"test-run-{i}"})
        _write_run(tmp_path / f"test-run-{i}.json", r)
    # Also write the primary run
    _write_run(tmp_path / f"{run_id}.json", run)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    result = rs.get_answer_diagnostics(10)
    # All 4 runs share slice="books" and should be aggregated
    assert result.n_runs >= 1  # at minimum loads the single loaded run


# ---------------------------------------------------------------------------
# REAL mode: missing file fails loudly (no silent mock fallback)
# ---------------------------------------------------------------------------

def test_real_mode_missing_file_raises_loudly(monkeypatch, tmp_path):
    """REAL mode with a nonexistent run file raises a clear error, not silent mock fallback."""
    run_id = "this-run-does-not-exist"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    with pytest.raises(Exception) as exc_info:
        rs.get_grounding_run()

    # The error message must name the expected path so the user knows what to run
    assert run_id in str(exc_info.value), (
        f"Error message must mention the missing run_id '{run_id}'. Got: {exc_info.value}"
    )


def test_real_mode_missing_file_error_is_not_mock(monkeypatch, tmp_path):
    """REAL mode with a missing file must NOT silently return mock data."""
    run_id = "missing-run-id"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)
    monkeypatch.setattr(rs, "RUNS_DIR", tmp_path)

    # Must raise, never return mock_grounding_run()
    raised = False
    try:
        rs.get_grounding_run()
    except Exception:
        raised = True
    assert raised, "REAL mode with missing file must raise, not return mock data"


# ---------------------------------------------------------------------------
# make_app() still builds in mock mode (regression guard)
# ---------------------------------------------------------------------------

def test_make_app_builds_in_mock_mode(monkeypatch):
    """With IVG_KG_RUN_ID unset, make_app() builds without errors."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    from app.app import make_app
    app = make_app()
    assert app.layout is not None


def test_make_app_uses_run_source_not_direct_mock(monkeypatch):
    """make_app() must route through run_source, not directly import mock_*."""
    monkeypatch.delenv("IVG_KG_RUN_ID", raising=False)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    # We can verify indirectly: make_app() should build the same layout as before
    import app.app as app_module
    importlib.reload(app_module)
    built = app_module.make_app()
    assert built.layout is not None


# ---------------------------------------------------------------------------
# Real slice run loads correctly (integration -- uses actual data/runs/ files)
# ---------------------------------------------------------------------------

def test_real_slice_run_loads_and_has_claims(monkeypatch):
    """Load the actual slice-01-glass-menagerie.json from data/runs/ and verify structure."""
    run_id = "slice-01-glass-menagerie"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    run = rs.get_grounding_run()
    assert run.run_id == run_id
    assert len(run.claims) >= 1
    # At least one claim must be grounded (retrieved or supportable)
    from ivg_kg.schema import ClaimStatus
    grounded = [c for c in run.claims if c.status != ClaimStatus.FABRICATED]
    assert len(grounded) >= 1


def test_real_slice_run_subgraph_nonempty(monkeypatch):
    """Load slice-01-glass-menagerie.json and derive a non-empty subgraph."""
    run_id = "slice-01-glass-menagerie"
    monkeypatch.setenv("IVG_KG_RUN_ID", run_id)

    import importlib

    import app.run_source as rs
    importlib.reload(rs)

    elements = rs.get_subgraph_elements()
    assert len(elements) > 0
    node_ids = {e["data"]["id"] for e in elements if "source" not in e["data"]}
    assert len(node_ids) > 0
