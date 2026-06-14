"""Conftest for the ivg-kg test suite.

Contains a single autouse fixture that guards against a known sys.modules
corruption introduced by test_entailment_module_imports_without_transformers
in test_entailment_gate.py.

That test temporarily removes torch from sys.modules and its finally-block
cleanup leaves the top-level sys.modules["torch"] key absent while all
torch.* submodules (including the C extension torch._C) are restored.
Subsequent tests that trigger any torch dispatch code (even via tensor
instance methods like .softmax()) cause torch/__init__.py to be re-executed,
which tries to re-register the "triton" namespace in the C dispatch registry
and raises:

    RuntimeError: Only a single TORCH_LIBRARY can be used to register
    the namespace triton ...

Fix: import torch HERE at conftest load time so _TORCH_MODULE holds the
real module reference.  conftest.py is loaded before any test file is
collected, so this is the canonical point to stash the reference.  The
fixture then restores sys.modules["torch"] before each test if it was
removed, without re-executing torch/__init__.py.

If torch is not installed, the import silently fails and the fixture is
a no-op for the whole session.
"""
from __future__ import annotations

import sys
from typing import Any

import pytest

# Attempt to import torch at conftest load time to stash the module reference.
# This runs before any test file is collected/imported, which is the earliest
# point where we can grab the reference and keep it alive.
# pylint: disable=wrong-import-position
try:
    import torch as _torch_import  # noqa: F401
    _TORCH_MODULE: Any = sys.modules.get("torch")
except ImportError:
    _TORCH_MODULE = None


@pytest.fixture(autouse=True)
def _guard_torch_sys_modules():
    """Restore sys.modules['torch'] before each test if it was removed.

    When _TORCH_MODULE is None (torch not installed), this is a pure no-op.
    When torch IS installed but its sys.modules entry has been removed by a
    prior test's cleanup (the destructive import test), this fixture puts the
    original module reference back BEFORE the current test runs, ensuring that
    tensor dispatch code does not trigger a re-import of torch/__init__.py
    (which would attempt to double-register the triton dispatch namespace).
    """
    if _TORCH_MODULE is not None and "torch" not in sys.modules:
        sys.modules["torch"] = _TORCH_MODULE
    yield
