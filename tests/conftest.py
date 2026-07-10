"""Pytest fixtures for CampAIgn-RPG-Engine tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))


@pytest.fixture(autouse=True, scope="session")
def _register_reference_handlers():
    from reference_handlers import register_reference_handlers

    register_reference_handlers()
