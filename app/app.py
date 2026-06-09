"""Dash application entry point for the IVG-KG mockup (SPEC-text §4.5).

make_app() builds a fully wired Dash instance on offline MOCK data (the Chopin
scenario) — no model, no SPARQL, no network. The grounding backend stays a stub.

Run it:  uv run python -m app.app     (or: task run / task dev)
"""
from __future__ import annotations

import dash

from app.callbacks import register_callbacks
from app.layout import get_layout
from app.panels.analytics import DEFAULT_N
from ivg_kg.mock.fixtures import (
    N_CHOICES,
    mock_answer_diagnostics,
    mock_grounding_run,
    mock_subgraph_elements,
)


def make_app() -> dash.Dash:
    """Build and return the wired Dash app (no server started)."""
    run = mock_grounding_run()
    elements = mock_subgraph_elements()
    diagnostics_by_n = {n: mock_answer_diagnostics(n) for n in N_CHOICES}

    _app = dash.Dash(__name__, title="ivg-kg mockup", suppress_callback_exceptions=True)
    _app.layout = get_layout(run, elements, diagnostics_by_n[DEFAULT_N])
    register_callbacks(_app, run, elements, diagnostics_by_n)
    return _app


app = make_app()
server = app.server  # for gunicorn / WSGI if ever needed

if __name__ == "__main__":
    app.run(debug=True)
