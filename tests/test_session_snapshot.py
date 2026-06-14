"""Area snapshot / JSON serialization (V0.3.0b, V0.4.0c1 multi-area)."""

import json

from src.llm.schemas import AgentCompoundTurn
from src.session import Session
from src.snapshot import DEFAULT_AREA_ID, build_area_snapshot, build_session_snapshot, serialize_agent


def _room(snap: dict) -> dict:
    return snap["areas"][DEFAULT_AREA_ID]


def test_snapshot_default_shape():
    session = Session.from_default()
    snap = session.snapshot()

    room = _room(snap)
    assert room["grid"] == {"min_x": 0, "max_x": 4, "min_y": 0, "max_y": 4}
    assert "hardwood floor" in room["area_description"].lower()
    assert snap["session_turn"] == 0
    assert snap["active_agent_id"] == "agent_01"
    assert snap["active_area_id"] == DEFAULT_AREA_ID
    assert len(snap["agents"]) == 1
    assert len(room["objects"]) == 2
    assert room["recent_events"] == []

    explorer = snap["agents"][0]
    assert explorer["id"] == "agent_01"
    assert explorer["name"] == "Explorer"
    assert explorer["area_id"] == DEFAULT_AREA_ID
    assert explorer["position"] == [1, 1]
    assert explorer["memory_module"] == "recent_turns"
    assert explorer["appearance"] == "tokens/explorer.svg"
    assert explorer["move_speed"] is None

    ball = next(o for o in room["objects"] if o["id"] == "obj_ball_01")
    assert ball["position"] == [2, 2]
    assert ball["appearance"] == "tokens/ball.svg"
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
    assert "passive_description" in agent_data
    assert "description" in agent_data


def test_snapshot_include_private_adds_object_descriptions():
    session = Session.from_default()
    objects = _room(session.snapshot(include_private=True))["objects"]
    ball = next(o for o in objects if o["id"] == "obj_ball_01")
    sign = next(o for o in objects if o["id"] == "obj_sign_01")
    assert "passive_description" in ball
    assert "description" in ball
    assert "ceramic ball" in ball["description"].lower()
    assert sign["passive_description"]
    assert sign["description"]


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
    names = {o["name"] for o in _room(snap)["objects"]}
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


def test_build_session_snapshot_from_session():
    session = Session.from_default()
    snap = build_session_snapshot(session)
    assert snap["active_area_id"] == DEFAULT_AREA_ID
    assert DEFAULT_AREA_ID in snap["areas"]


def test_snapshot_appearance_round_trip():
    session = Session.from_default()
    session.run_command('edit-agent agent_01 appearance "tokens/explorer.png"')
    session.run_command(
        'create-object name "Crate" appearance "tokens/crate.png" at 3,3'
    )
    snap = session.snapshot()
    explorer = snap["agents"][0]
    assert explorer["appearance"] == "tokens/explorer.png"
    crate = next(o for o in _room(snap)["objects"] if o["name"] == "Crate")
    assert crate["appearance"] == "tokens/crate.png"


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
        "appearance",
        "move_speed",
    }


def test_serialize_agent_includes_area_id_when_set():
    session = Session.from_default()
    agent = session.get_active_agent()
    data = serialize_agent(agent, area_id=DEFAULT_AREA_ID)
    assert data["area_id"] == DEFAULT_AREA_ID
