"""Typed Session world-editing API (V0.7.0b/c)."""

from __future__ import annotations

import pytest

from campaign_rpg_engine import ObjectAction, Session, WorldMutationResult, load_profile


@pytest.fixture
def session() -> Session:
    return Session.from_profile(load_profile("default_compound"))


def test_create_object_typed(session: Session) -> None:
    result = session.create_object(
        name="Console",
        position=(2, 2),
        passive_description="A dusty console.",
        description="Buttons and lights.",
    )
    assert isinstance(result, WorldMutationResult)
    assert result.ok
    assert result.object is not None
    assert result.object.name == "Console"
    assert result.object.position == (2, 2)


def test_create_object_typed_adds_second_object(session: Session) -> None:
    first = session.create_object(name="A", position=(1, 1), passive_description="pa")
    second = session.create_object(name="B", position=(3, 3), passive_description="pb")
    assert first.ok and second.ok
    assert session.area.get_object_by_id(first.object.id) is not None
    objects = [o.name for o in session.area.get_objects()]
    assert "A" in objects and "B" in objects


def test_create_agent_registers_index(session: Session) -> None:
    result = session.create_agent(
        name="Scout",
        position=(0, 0),
        personality="Curious.",
        is_player=True,
    )
    assert result.ok
    assert result.agent is not None
    assert session.get_agent(result.agent.id) is result.agent
    assert session.agent_area[result.agent.id] == session.active_area_id


def test_delete_object_session_wide(session: Session) -> None:
    created = session.create_object(name="Temp", position=(1, 1))
    assert created.ok and created.object is not None
    deleted = session.delete_object(created.object.id)
    assert deleted.ok
    assert session.area.get_object_by_id(created.object.id) is None


def test_add_object_action(session: Session) -> None:
    created = session.create_object(name="Door", position=(2, 2))
    assert created.object is not None
    action = ObjectAction(
        name="open",
        range=1,
        result="The door opens.",
        passive_result="A closed door.",
        handler_id="delete_self",
        handler_params={},
    )
    result = session.add_object_action(created.object.id, action)
    assert result.ok
    obj = session.area.get_object_by_id(created.object.id)
    assert obj is not None
    assert "open" in obj.actions
    assert obj.actions["open"].handler_id == "delete_self"


def test_create_area_typed(session: Session) -> None:
    result = session.create_area("rooftop", description="Windy roof.", width=4, height=4)
    assert result.ok
    assert result.area_id == "rooftop"
    assert "rooftop" in session.areas
    assert session.active_area_id == "rooftop"


def test_edit_object_typed(session: Session) -> None:
    created = session.create_object(name="Sign", position=(1, 1), description="Old text.")
    assert created.object is not None
    edited = session.edit_object(
        created.object.id,
        description="New text.",
        position=(2, 2),
    )
    assert edited.ok
    obj = session.area.get_object_by_id(created.object.id)
    assert obj is not None
    assert obj.description == "New text."
    assert obj.position == (2, 2)
