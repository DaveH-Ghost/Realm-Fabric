"""
In-memory Session holder for the realm-studio demo (single-player, one process).
"""

from __future__ import annotations

import os

from realm_fabric import Session, load_profile
from src.area import Area

_store: SessionStore | None = None

_DEV_STACK_ENV = "REALM_STUDIO_DEV_STACK"
_DEV_STACK_TILE = (3, 3)
_DEV_STACK_COUNT = 10


def _maybe_dev_stack_seed(session: Session) -> None:
    """
    Temporary dev helper: stack objects on one tile to test grid scrolling.

    Enable: REALM_STUDIO_DEV_STACK=1 uv run realm-studio
    Remove when no longer needed for UI testing.
    """
    flag = os.environ.get(_DEV_STACK_ENV, "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    x, y = _DEV_STACK_TILE
    for i in range(1, _DEV_STACK_COUNT + 1):
        session.run_command(
            f'create-object name "Stack{i}" pdesc "Stack test item {i}." '
            f'desc "Dev stack object {i}." at {x},{y}'
        )


def _seed_studio_hall(session: Session) -> None:
    """Second empty area so the area dropdown is exercisable (V0.4.0c2)."""
    if "hall" not in session.areas:
        session.areas["hall"] = Area(
            area_description="A narrow stone hall with worn flagstones.",
        )


class SessionStore:
    """Owns one engine ``Session`` for the lifetime of the server process."""

    def __init__(self) -> None:
        profile = load_profile("default_compound")
        self._session = Session.from_profile(profile)
        _seed_studio_hall(self._session)
        _maybe_dev_stack_seed(self._session)

    @property
    def session(self) -> Session:
        return self._session


def get_session_store() -> SessionStore:
    """Return the process-wide session store (lazy singleton)."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store() -> None:
    """Reset store (tests only)."""
    global _store
    _store = None
