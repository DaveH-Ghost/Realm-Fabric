"""Area snapshot / JSON serialization (V0.3.0b)."""

import json

from src.llm.schemas import AgentCompoundTurn
from src.session import Session
from src.snapshot import build_area_snapshot, serialize_agent


def test_snapshot_default_shape():
    session = Session.from_default()
    snap = session.snapshot()

    assert snap["grid"] == {"min_x": 0, "max_x": 4, "min_y": 0, "max_y": 4}
    assert "hardwood floor" in snap["area_description"].lower()
    assert snap["session_turn"] == 0
    assert snap["active_agent_id"] == "agent_01"
    assert len(snap["agents"]) == 1
    assert len(snap["objects"]) == 2
    assert snap["recent_events"] == []

    explorer = snap["agents"][0]
    assert explorer["id"] == "agent_01"
    assert explorer["name"] == "Explorer"
    assert explorer["position"] == [1, 1]
    assert explorer["memory_module"] == "recent_turns"

    ball = next(o for o in snap["objects"] if o["id"] == "obj_ball_01")
    assert ball["position"] == [2, 2]
    assert "kick" in ball["actions"]


def test_snapshot_is_json_serializable():
    session = Session.from_default()
    text = json.dumps(session.snapshot())
    assert "Explorer" in text


def test_snapshot_omits_personality_by_default():
    session = Session.from_default()
    snap = session.snapshot()
    assert "personality" not in snap["agents"][0]


def test_snapshot_include_private_adds_personality():
    session = Session.from_default()
    agent_data = session.snapshot(include_private=True)["agents"][0]
    assert "personality" in agent_data
    assert "curious explorer" in agent_data["personality"].lower()


def test_snapshot_passive_vision_for_active_agent():
    session = Session.from_default()
    snap = session.snapshot()
    assert "passive_vision" in snap
    assert "Ceramic Ball (obj_ball_01)" in snap["passive_vision"]
    assert "You are at (1, 1)." in snap["passive_vision"]


def test_snapshot_no_passive_vision_when_disabled():
    session = Session.from_default()
    snap = session.snapshot(include_passive_vision=False)
    assert "passive_vision" not in snap


def test_snapshot_after_move_updates_position_and_session_turn():
    session = Session.from_default()
    session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="move",
            move_target="2,2",
            turn_action="none",
        ),
    )
    snap = session.snapshot()
    assert snap["session_turn"] == 1
    explorer = snap["agents"][0]
    assert explorer["position"] == [2, 2]


def test_snapshot_after_create_object():
    session = Session.from_default()
    session.run_command(
        'create-object name "Cookie" pdesc "A cookie." at 3,3 '
        'action eat range 0 effect delete_self '
        'result "You ate it." passive "{actor} ate it."'
    )
    snap = session.snapshot()
    names = {o["name"] for o in snap["objects"]}
    assert "Cookie" in names


def test_snapshot_active_agent_after_switch():
    session = Session.from_default()
    session.run_command(
        'create-agent name "Goblin" personality "Grumpy." at 0,0'
    )
    session.set_active_agent("Goblin")
    snap = session.snapshot()
    assert snap["active_agent_id"] == session.get_agent("Goblin").id
    assert "passive_vision" in snap
    assert "You are at (0, 0)" in snap["passive_vision"]
    assert "Goblin" not in snap["passive_vision"]  # active agent does not see self


def test_build_area_snapshot_standalone():
    session = Session.from_default()
    snap = build_area_snapshot(
        session.area,
        active_agent_id="agent_01",
        session_turn=5,
    )
    assert snap["session_turn"] == 5
    assert snap["agents"][0]["id"] == "agent_01"


def test_serialize_agent_public_fields():
    session = Session.from_default()
    agent = session.get_active_agent()
    data = serialize_agent(agent, include_private=False)
    assert set(data.keys()) == {
        "id",
        "name",
        "position",
        "passive_result",
        "memory_module",
    }
