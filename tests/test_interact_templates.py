"""Interact result/passive template placeholders."""

from campaign_rpg_engine.actions.interact import interact
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.interact_templates import (
    InteractTemplateContext,
    format_interact_template,
    interact_template_var_help,
)
from campaign_rpg_engine.session import Session


def test_interact_template_var_help_lists_all_placeholders():
    help_items = interact_template_var_help()
    names = {item["name"] for item in help_items}
    assert names == {
        "actor",
        "object",
        "object_start",
        "object_end",
        "actor_start",
        "actor_end",
        "object_start_area",
        "object_end_area",
        "actor_start_area",
        "actor_end_area",
    }
    for item in help_items:
        assert item["placeholder"] == "{" + item["name"] + "}"
        assert item["description"]


def test_format_interact_template_substitutes_all_placeholders():
    ctx = InteractTemplateContext(
        actor="Explorer",
        object_name="Door",
        object_start=(1, 1),
        object_end=(1, 1),
        actor_start=(1, 2),
        actor_end=(0, 0),
        object_start_area="room",
        object_end_area="room",
        actor_start_area="room",
        actor_end_area="hall",
    )
    template = (
        "{actor} uses {object} at {object_start} in {object_start_area}; "
        "ends at {actor_end} in {actor_end_area}."
    )
    assert format_interact_template(template, ctx) == (
        "Explorer uses Door at (1, 1) in room; ends at (0, 0) in hall."
    )


def test_interact_move_area_substitutes_actor_area_placeholders():
    room = Area(area_description="Room.")
    hall = Area(area_description="Hall.")
    explorer = Agent(
        id="agent_01",
        name="Explorer",
        position=(1, 2),
        personality="Curious.",
    )
    room.add_agent(explorer)
    session = Session(
        areas={"room": room, "hall": hall},
        active_area_id="room",
        agent_area={"agent_01": "room"},
        active_agent_id="agent_01",
    )
    create_object_from_args(
        room,
        'name "Door" pdesc "A door." desc "Hall door." at 1,1 '
        "action enter range 1 handler move_area dest-area hall dest-at 0,0 "
        'result "You leave {actor_start_area} at {actor_start} and arrive in '
        '{actor_end_area} at {actor_end}." '
        'passive "{actor} travels from {actor_start_area} to {actor_end_area}."',
    )
    door = room.get_objects()[0]

    outcome = interact(
        explorer,
        room,
        door.id,
        "enter",
        session=session,
        source_area_id="room",
    )
    assert outcome.result == ("You leave room at (1, 2) and arrive in hall at (0, 0).")
    assert outcome.passive_result == "Explorer travels from room to hall."
