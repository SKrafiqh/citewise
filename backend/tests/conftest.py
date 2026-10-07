import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))  # for the eval package


def call_or_skip(fn, *args, **kwargs):
    """Run a not-yet-implemented function; skip the test instead of failing."""
    try:
        return fn(*args, **kwargs)
    except NotImplementedError as exc:
        pytest.skip(f"TODO: {exc}")
