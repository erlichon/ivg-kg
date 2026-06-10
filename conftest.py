"""Root conftest.py — puts the repo root on sys.path so that the app/ package
(a sibling of src/) is importable under pytest.

pytest rootdir is the repo root, but the app/ directory is not installed via
pyproject.toml (only src/ivg_kg is).  Inserting the repo root at sys.path[0]
makes `import app.layout` work without installing the package.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Insert repo root so that app/ (at the same level as src/) is importable.
repo_root = str(Path(__file__).parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
