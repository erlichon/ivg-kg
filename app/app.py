"""Dash application entry point for the IVG-KG mockup (SPEC-text §4.5).

make_app() builds a fully wired Dash instance. By default it uses offline MOCK
data (the Chopin scenario) — no model, no SPARQL, no network. Set the env var
IVG_KG_RUN_ID to load a real precomputed GroundingRun from data/runs/<id>.json.

Run (mock mode, default):
    uv run python -m app.app

Run (real mode against a slice run):
    IVG_KG_RUN_ID=slice-01-glass-menagerie uv run python -m app.app
"""
from __future__ import annotations

import dash

from app.callbacks import register_callbacks
from app.layout import get_layout
from app.run_source import get_grounding_run, get_single_run_summary, get_subgraph_elements


def make_app() -> dash.Dash:
    """Build and return the wired Dash app (no server started).

    Data is sourced from run_source: MOCK mode when IVG_KG_RUN_ID is unset,
    REAL mode (loading data/runs/<IVG_KG_RUN_ID>.json) when it is set.
    """
    run = get_grounding_run()
    elements = get_subgraph_elements()
    single_summary = get_single_run_summary()

    _app = dash.Dash(__name__, title="ivg-kg mockup", suppress_callback_exceptions=True)
    _app.layout = get_layout(run, elements, single_summary)
    register_callbacks(_app, run, elements)
    return _app


app = make_app()
server = app.server  # for gunicorn / WSGI if ever needed

if __name__ == "__main__":
    app.run(debug=True)
