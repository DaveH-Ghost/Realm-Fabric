"""Process-wide session holder with typed demo bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from realm_fabric import Session, load_profile

_EXAMPLES = Path(__file__).resolve().parent.parent.parent
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

_store: SessionStore | None = None


def _bootstrap_demo_world(session: Session) -> None:
    """Small scenario built with typed API only."""
    if any(agent.name == "Explorer" for area in session.areas.values() for agent in area.agents):
        return
    main_area_id = session.active_area_id
    session.create_agent(
        name="Explorer",
        position=(0, 0),
        personality="A cautious wanderer.",
        passive_description="Someone in travel gear.",
        is_player=True,
    )
    session.create_object(
        name="Sign",
        position=(2, 1),
        passive_description="A wooden signpost.",
        description="The sign reads: WELCOME.",
    )
    session.create_area("hall", description="A side hall.", width=5, height=5)
    session.set_active_area(main_area_id)


class SessionStore:
    def __init__(self) -> None:
        from reference_handlers import register_reference_handlers

        register_reference_handlers()
        self._session = Session.from_profile(load_profile("default_compound"))
        _bootstrap_demo_world(self._session)

    @property
    def session(self) -> Session:
        return self._session

    def export_session(self) -> dict:
        return self._session.to_save_dict()

    def import_session(self, data: dict) -> None:
        self._session = Session.from_snapshot(data)


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store() -> None:
    global _store
    _store = None
