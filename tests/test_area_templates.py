"""Area template export and spawn (1.3.1)."""

from __future__ import annotations

import pytest

from campaign_rpg_engine import (
    Session,
    export_area_template,
    load_profile,
    spawn_area_from_template,
    validate_area_template,
)
from campaign_rpg_engine.world_edit_api import collect_object_ids_in_session


@pytest.fixture(autouse=True)
def _handlers():
    from reference_handlers import register_reference_handlers

    register_reference_handlers()


@pytest.fixture
def session() -> Session:
    return Session.from_profile(load_profile("default_compound"))


def test_export_area_template_includes_layout_without_ids(session: Session) -> None:
    base_objects = len(session.area.get_objects())

    session.create_object(name="Table", position=(1, 1), passive_description="Wood.")
    session.create_decoration(
        kind="sprite",
        image="assets/tree.png",
        x=10,
        y=20,
        width=32,
        height=48,
        z_index=1,
    )

    template = export_area_template(session, session.active_area_id, name="Tavern")
    assert template["kind"] == "area"
    assert template["name"] == "Tavern"
    assert template["grid"]["max_x"] >= 0
    assert len(template["objects"]) == base_objects + 1
    assert "agents" not in template
    assert len(template["decorations"]) == 1
    table = next(item for item in template["objects"] if item["name"] == "Table")
    assert "id" not in table
    assert table["position"] == [1, 1]
    assert "id" not in template["decorations"][0]
    assert validate_area_template(template) is None


def test_export_area_template_can_omit_hidden_objects(session: Session) -> None:
    base_objects = len(session.area.get_objects())

    session.create_object(
        name="Hidden Chest",
        position=(0, 0),
        passive_description="Secret.",
        hidden=True,
    )

    full = export_area_template(session, session.active_area_id)
    trimmed = export_area_template(
        session,
        session.active_area_id,
        include_hidden_objects=False,
    )
    assert len(full["objects"]) == base_objects + 1
    assert trimmed["objects"] == [o for o in full["objects"] if not o.get("hidden")]


def test_spawn_area_from_template_new_area_generates_unique_object_ids(session: Session) -> None:
    created = session.create_object(name="Barrel", position=(1, 1), passive_description=".")
    assert created.ok and created.object is not None
    original_id = created.object.id
    template = export_area_template(session, session.active_area_id)

    result = spawn_area_from_template(session, template, area_id="warehouse", mode="new")
    assert result.ok
    warehouse = session.areas["warehouse"]
    spawned = next(obj for obj in warehouse.get_objects() if obj.name == "Barrel")
    assert spawned.id != original_id
    assert spawned.position == (1, 1)
    assert len(collect_object_ids_in_session(session)) == len(
        {obj.id for area in session.areas.values() for obj in area.get_objects()}
    )


def test_spawn_area_from_template_replace_keeps_agents(session: Session) -> None:
    created = session.create_area(area_id="staging", description="Staging.", width=5, height=5)
    assert created.ok
    session.set_active_area("staging")
    session.create_agent(name="Keeper", position=(1, 1), personality=".")
    session.create_object(name="Old", position=(0, 0), passive_description=".")
    agent_ids_before = {agent.id for agent in session.areas["staging"].agents}

    template = export_area_template(session, "staging", name="Reset Room")
    template["objects"] = []

    result = spawn_area_from_template(session, template, area_id="staging", mode="replace")
    assert result.ok
    area = session.areas["staging"]
    assert area.get_objects() == []
    assert {agent.id for agent in area.agents} == agent_ids_before


def test_spawn_area_from_template_restores_decorations(session: Session) -> None:
    session.create_decoration(
        kind="background",
        image="assets/floor.png",
        repeat="repeat",
    )
    session.create_decoration(
        kind="sprite",
        image="assets/sign.png",
        x=-5,
        y=10,
        width=40,
        height=40,
        z_index=2,
    )
    template = export_area_template(session, session.active_area_id)

    result = spawn_area_from_template(session, template, area_id="decor_room", mode="new")
    assert result.ok
    area = session.areas["decor_room"]
    assert len(area.decorations) == 2
    kinds = {d.kind for d in area.decorations}
    assert kinds == {"background", "sprite"}
    for decoration in area.decorations:
        assert decoration.id.startswith("decor_")


def test_spawn_rejects_existing_area_in_new_mode(session: Session) -> None:
    template = export_area_template(session, session.active_area_id)
    result = spawn_area_from_template(session, template, area_id=session.active_area_id, mode="new")
    assert not result.ok
    assert "already exists" in result.message
