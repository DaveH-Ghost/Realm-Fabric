"""move_area interaction handler (V0.4.0d / V0.6.1)."""

from campaign_rpg_engine.actions.interact import interact
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.simulation import run_compound_turn


def _two_room_with_door() -> Session:
    room = Area(area_description="The main room.")
    hall = Area(area_description="A narrow hall.")
    explorer = Agent(
        id="agent_01",
        name="Explorer",
        position=(1, 1),
        personality="Curious.",
    )
    room.add_agent(explorer)
    door_args = (
        'name "Door" pdesc "A wooden door." desc "It leads to the hall." at 1,1 '
        "action walk_through range 0 handler move_area dest-area hall dest-at 0,0 "
        'result "You walk through the door." '
        'passive "{actor} walks through the door."'
    )
    create_object_from_args(room, door_args)
    return Session(
        areas={"room": room, "hall": hall},
        active_area_id="room",
        agent_area={"agent_01": "room"},
        active_agent_id="agent_01",
    )


def test_create_object_move_area_parses_handler_params():
    session = _two_room_with_door()
    door = session.areas["room"].get_objects()[0]
    action = door.actions["walk_through"]
    assert action.handler_id == "move_area"
    assert action.handler_params["dest-area"] == "hall"
    assert action.handler_params["dest-at"] == "0,0"


def test_interact_move_area_transfers_agent():
    session = _two_room_with_door()
    room = session.areas["room"]
    explorer = room.get_agent()
    door = room.get_objects()[0]

    outcome = interact(
        explorer,
        room,
        door.id,
        "walk_through",
        session=session,
        source_area_id="room",
    )
    assert "You walk through the door." in outcome.result
    assert explorer not in room.agents
    assert session.areas["hall"].get_agent_by_id("agent_01") is explorer
    assert explorer.position == (0, 0)
    assert session.agent_area["agent_01"] == "hall"


def test_interact_move_area_unknown_destination_fails():
    session = _two_room_with_door()
    room = session.areas["room"]
    explorer = room.get_agent()
    door = room.get_objects()[0]
    door.actions["walk_through"].handler_params = {
        "dest-area": "attic",
        "dest-at": "0,0",
    }

    outcome = interact(
        explorer,
        room,
        door.id,
        "walk_through",
        session=session,
        source_area_id="room",
    )
    assert "Unknown destination area" in outcome.result
    assert session.agent_area["agent_01"] == "room"


def test_interact_move_area_out_of_bounds_fails():
    session = _two_room_with_door()
    room = session.areas["room"]
    explorer = room.get_agent()
    door = room.get_objects()[0]
    door.actions["walk_through"].handler_params = {
        "dest-area": "hall",
        "dest-at": "9,9",
    }

    outcome = interact(
        explorer,
        room,
        door.id,
        "walk_through",
        session=session,
        source_area_id="room",
    )
    assert "outside" in outcome.result.lower()
    assert session.agent_area["agent_01"] == "room"


def test_create_object_move_area_missing_dest_rejected():
    session = Session.from_default()
    obj, err = create_object_from_args(
        session.area,
        'name "Door" at 1,1 action use range 0 handler move_area '
        'result "Go." passive "{actor} goes."',
    )
    assert obj is None
    assert "dest-area" in err


def test_compound_turn_interact_move_area_via_session():
    session = _two_room_with_door()
    room = session.areas["room"]
    explorer = room.get_agent()
    door = room.get_objects()[0]

    turn = AgentCompoundTurn(
        reasoning="Leave the room.",
        action="interact",
        target=door.id,
        verb="walk_through",
    )
    record = run_compound_turn(
        explorer,
        room,
        turn,
        turn_number=1,
        session=session,
        source_area_id="room",
    )
    assert "walk through" in record.result.lower()
    assert session.agent_area["agent_01"] == "hall"
