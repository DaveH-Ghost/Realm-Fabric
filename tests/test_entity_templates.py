"""Entity template export and spawn (1.2.1)."""

from __future__ import annotations

import pytest
from campaign_rpg_engine import (
    ObjectAction,
    Session,
    TurnRecord,
    export_agent_template,
    export_object_template,
    load_profile,
    spawn_agent_from_template,
    spawn_object_from_template,
)
from campaign_rpg_engine.memory_modules.recent_turns import RecentTurnsModule


@pytest.fixture(autouse=True)
def _handlers():
    from reference_handlers import register_reference_handlers

    register_reference_handlers()


@pytest.fixture
def session() -> Session:
    return Session.from_profile(load_profile("default_compound"))


def test_export_object_template_omits_id_and_position(session: Session) -> None:
    created = session.create_object(
        name="Mug",
        position=(2, 3),
        passive_description="Coffee.",
        description="A mug.",
    )
    assert created.ok and created.object is not None
    obj = created.object
    session.add_object_action(
        obj.id,
        ObjectAction(
            name="kick",
            range=1,
            handler_id="random_move_self",
            result="You kick {object}.",
            passive_result="{actor} kicks {object}.",
        ),
    )
    obj = session.area.get_object_by_id(obj.id)
    assert obj is not None

    template = export_object_template(obj)
    assert template["kind"] == "object"
    assert template["name"] == "Mug"
    assert "id" not in template
    assert "position" not in template
    assert "kick" in template["actions_detail"]


def test_spawn_object_generates_new_id(session: Session) -> None:
    created = session.create_object(name="Table", position=(1, 1), passive_description="Wood.")
    obj = created.object
    assert obj is not None
    template = export_object_template(obj)

    first = spawn_object_from_template(session, template, (2, 2))
    second = spawn_object_from_template(session, template, (3, 3))
    assert first.ok and second.ok
    assert first.object is not None and second.object is not None
    assert first.object.id != second.object.id
    assert first.object.id != obj.id
    assert session.area.get_object_by_id(obj.id) is not None


def test_export_agent_without_memory(session: Session) -> None:
    created = session.create_agent(
        name="Goblin",
        position=(0, 1),
        personality="Mean.",
        passive_description="Green.",
    )
    agent = created.agent
    assert agent is not None
    agent.memory.record_turn(
        TurnRecord(turn_number=1, steps=[], result="", reasoning="test"),
        agent_id=agent.id,
        agent_name=agent.name,
    )

    template = export_agent_template(agent, include_memory=False)
    assert template["kind"] == "agent"
    assert template["memory_module"]
    assert "memory" not in template
    assert "id" not in template


def test_export_agent_with_memory(session: Session) -> None:
    created = session.create_agent(name="Shopkeeper", position=(1, 1), personality="Friendly.")
    agent = created.agent
    assert agent is not None
    agent.memory.mark_looked_at("obj_sign_01")

    template = export_agent_template(agent, include_memory=True)
    assert template.get("include_memory") is True
    assert "memory" in template
    assert "obj_sign_01" in template["memory"]["looked_at"]


def test_spawn_agent_restores_memory(session: Session) -> None:
    created = session.create_agent(name="Bram", position=(1, 1), personality="Remembers.")
    agent = created.agent
    assert agent is not None
    agent.memory.mark_looked_at("agent_player_01")
    template = export_agent_template(agent, include_memory=True)

    placed = spawn_agent_from_template(session, template, (3, 3))
    assert placed.ok and placed.agent is not None
    assert placed.agent.id != agent.id
    assert "agent_player_01" in placed.agent.memory.looked_at


def test_spawn_agent_fresh_memory_when_template_has_none(session: Session) -> None:
    created = session.create_agent(name="Clone", position=(0, 0), personality=".")
    agent = created.agent
    assert agent is not None
    agent.memory.record_turn(
        TurnRecord(turn_number=1, steps=[], result="", reasoning="test"),
        agent_id=agent.id,
        agent_name=agent.name,
    )
    template = export_agent_template(agent, include_memory=False)

    placed = spawn_agent_from_template(session, template, (2, 2))
    assert placed.ok and placed.agent is not None
    module = placed.agent.memory.module
    assert isinstance(module, RecentTurnsModule)
    assert module.stored_turns == []


def test_spawn_rejects_wrong_kind(session: Session) -> None:
    created = session.create_object(name="Rock", position=(0, 0), passive_description=".")
    obj = created.object
    assert obj is not None
    template = export_object_template(obj)
    result = spawn_agent_from_template(session, template, (0, 0))
    assert not result.ok
