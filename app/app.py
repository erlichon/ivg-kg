"""Dash application entry point for IVG-KG (SPEC §4.5).

make_app() builds and returns a fully configured Dash instance (useful for
testing without starting a server).

The module-level ``app`` is the production instance; running this file
directly starts the dev server.
"""
from __future__ import annotations

import dash

from app.callbacks import register_callbacks
from app.layout import get_layout
from ivg_kg.mock.fixtures import mock_grounding_run, mock_subgraph_elements


def make_app() -> dash.Dash:
    """Build and return a fully wired Dash app (no server started).

    Fed entirely by mock fixtures (P0 — no real grounding).
    """
    run = mock_grounding_run()
    elements = mock_subgraph_elements()

    _app = dash.Dash(__name__)
    _app.layout = get_layout(run, elements)
    register_callbacks(_app, run)
    return _app


# Module-level app instance for WSGI / gunicorn and direct execution.
app = make_app()

if __name__ == "__main__":
    app.run(debug=True)
