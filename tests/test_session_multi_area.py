"""Multi-area Session (V0.4.0c1)."""

from src.agent import Agent
from src.area import Area
from src.llm.schemas import AgentCompoundTurn
from src.session import Session
from src.snapshot import DEFAULT_AREA_ID, build_session_snapshot


def _two_area_session() -> Session:
    room = Area(area_description="The main room.")
    hall = Area(area_description="A narrow hall.")
    room.add_agent(Agent(
        id="agent_01",
        name="Explorer",
        position=(1, 1),
        personality="Curious.",
    ))
    hall.add_agent(Agent(
        id="agent_02",
        name="Guard",
        position=(0, 0),
        personality="Alert.",
    ))
    return Session(
        areas={"room": room, "hall": hall},
        active_area_id="room",
        agent_area={"agent_01": "room", "agent_02": "hall"},
        active_agent_id="agent_01",
    )


def test_default_session_single_area():
    session = Session.from_default()
    assert DEFAULT_AREA_ID in session.areas
    assert session.active_area_id == DEFAULT_AREA_ID
    assert session.area is session.areas[DEFAULT_AREA_ID]
    snap = session.snapshot()
    assert snap["active_area_id"] == DEFAULT_AREA_ID
    assert DEFAULT_AREA_ID in snap["areas"]
    assert snap["agents"][0]["area_id"] == DEFAULT_AREA_ID


def test_session_area_property_is_active_area():
    session = _two_area_session()
    assert session.area is session.areas["room"]
    session.set_active_area("hall")
    assert session.area is session.areas["hall"]


def test_set_active_area_unknown_rejected():
    session = _two_area_session()
    result = session.set_active_area("attic")
    assert not result.ok
    assert session.active_area_id == "room"


def test_run_command_create_object_scoped_to_active_area():
    session = _two_area_session()
    session.set_active_area("hall")
    result = session.run_command(
        'create-object name "Bench" pdesc "A bench." at 2,2'
    )
    assert result.ok
    names = {o.name for o in session.areas["hall"].get_objects()}
    assert "Bench" in names
    assert "Bench" not in {o.name for o in session.areas["room"].get_objects()}


def test_run_command_create_agent_registers_area():
    session = _two_area_session()
    session.set_active_area("hall")
    result = session.run_command(
        'create-agent name "Visitor" personality "Quiet." at 1,1'
    )
    assert result.ok
    visitor = session.get_agent("Visitor")
    assert visitor is not None
    assert session.agent_area[visitor.id] == "hall"


def test_compound_turn_uses_agent_area_not_active_area():
    session = _two_area_session()
    session.set_active_area("hall")
    guard = session.get_agent("agent_02")
    assert guard is not None
    assert guard.position == (0, 0)

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="patrol",
            move_target="0,1",
            turn_action="none",
        ),
        agent_id="agent_02",
    )
    assert result.ok
    assert guard.position == (0, 1)
    explorer = session.get_agent("agent_01")
    assert explorer is not None
    assert explorer.position == (1, 1)


def test_emit_event_scoped_to_active_area():
    session = _two_area_session()
    session.set_active_area("hall")
    result = session.emit_area_event("A draft blows through.")
    assert result.ok
    assert len(session.areas["hall"].recent_events) == 1
    assert len(session.areas["room"].recent_events) == 0


def test_transfer_agent_between_areas():
    session = _two_area_session()
    result = session.transfer_agent("agent_01", "hall", (2, 2))
    assert result.ok
    assert session.agent_area["agent_01"] == "hall"
    assert session.areas["room"].get_agent_by_id("agent_01") is None
    agent = session.areas["hall"].get_agent_by_id("agent_01")
    assert agent is not None
    assert agent.position == (2, 2)


def test_transfer_agent_invalid_destination():
    session = _two_area_session()
    result = session.transfer_agent("agent_01", "attic", (0, 0))
    assert not result.ok
    assert session.agent_area["agent_01"] == "room"


def test_get_agent_finds_across_areas():
    session = _two_area_session()
    assert session.get_agent("Guard") is not None
    assert session.get_agent("agent_02") is not None


def test_build_session_snapshot_shape():
    session = _two_area_session()
    snap = build_session_snapshot(session)
    assert snap["session_turn"] == 0
    assert snap["active_agent_id"] == "agent_01"
    assert snap["active_area_id"] == "room"
    assert set(snap["areas"]) == {"room", "hall"}
    assert "grid" in snap["areas"]["room"]
    assert "objects" in snap["areas"]["hall"]
    assert len(snap["agents"]) == 2
    by_id = {a["id"]: a for a in snap["agents"]}
    assert by_id["agent_01"]["area_id"] == "room"
    assert by_id["agent_02"]["area_id"] == "hall"
    assert "passive_vision" in snap


def test_run_command_areas_listing():
    session = _two_area_session()
    result = session.run_command("areas")
    assert result.ok
    assert "room" in result.message
    assert "hall" in result.message


def test_run_command_active_area():
    session = _two_area_session()
    result = session.run_command("active-area hall")
    assert result.ok
    assert session.active_area_id == "hall"


def test_edit_object_moves_between_areas():
    from src.area_edit import create_object_from_args, edit_object_for_session

    session = _two_area_session()
    obj, _ = create_object_from_args(
        session.areas["room"],
        'name "Crate" desc "A crate." at 2,2',
    )
    assert obj is not None

    message = edit_object_for_session(
        session,
        f"{obj.id} area hall pos 0,1",
    )
    assert message.startswith("Updated object")
    assert "area" in message
    assert session.areas["room"].get_object_by_id(obj.id) is None
    moved = session.areas["hall"].get_object_by_id(obj.id)
    assert moved is not None
    assert moved.position == (0, 1)


def test_edit_object_area_rejected_when_out_of_bounds():
    from src.area_edit import create_object_from_args, edit_object_for_session

    session = _two_area_session()
    obj, _ = create_object_from_args(
        session.areas["room"],
        'name "Crate" desc "A crate." at 2,2',
    )
    assert obj is not None

    message = edit_object_for_session(session, f"{obj.id} area hall pos 9,9")
    assert "Invalid position" in message
    assert session.areas["room"].get_object_by_id(obj.id) is not None


def test_edit_agent_moves_between_areas():
    from src.area_edit import edit_agent_for_session

    session = _two_area_session()

    result = edit_agent_for_session(session, "agent_01 area hall pos 2,2")
    assert result.ok
    assert "area" in result.message
    assert session.areas["room"].get_agent_by_id("agent_01") is None
    moved = session.areas["hall"].get_agent_by_id("agent_01")
    assert moved is not None
    assert moved.position == (2, 2)
    assert session.agent_area["agent_01"] == "hall"


def test_edit_agent_area_rejected_when_out_of_bounds():
    from src.area_edit import edit_agent_for_session

    session = _two_area_session()

    result = edit_agent_for_session(session, "agent_01 area hall pos 9,9")
    assert not result.ok
    assert "outside" in result.message.lower() or "Invalid position" in result.message
    assert session.areas["room"].get_agent_by_id("agent_01") is not None


def test_run_command_edit_agent_moves_between_areas():
    session = _two_area_session()

    result = session.run_command("edit-agent agent_01 area hall pos 1,0")
    assert result.ok
    assert session.areas["room"].get_agent_by_id("agent_01") is None
    assert session.areas["hall"].get_agent_by_id("agent_01") is not None
