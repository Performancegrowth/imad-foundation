"""Shared pytest fixtures and path configuration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `app` importable when running pytest from the repo root or tests dir.
ROOT = Path(__file__).resolve().parents[1]  # backend/
BACKEND_APP = ROOT / "app"
for candidate in (ROOT, ROOT.parent):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def temp_storage(tmp_path_factory):
    """Session-scoped storage dir used by plan/survey persistence tests."""
    return str(tmp_path_factory.mktemp("imad-storage"))