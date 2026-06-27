"""Player agents — human-controlled turns without LLM."""

from src.actions.move import move as do_move
from src.area import create_initial_area
from src.area_edit import create_agent_from_args, edit_agent_from_args
from src.llm.schemas import AgentCompoundTurn
from src.session import Session


def test_create_agent_with_player_flag():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Tester" personality "x" player true at 0,0',
    )
    assert agent is not None
    assert agent.is_player is True
    assert agent.id.startswith("agent_")
    assert "Tester" in msg


def test_edit_agent_player_flag():
    area = create_initial_area()
    agent, _ = create_agent_from_args(
        area,
        'name "Tester" personality "x" at 0,0',
    )
    assert agent is not None
    assert agent.is_player is False

    result = edit_agent_from_args(area, f"{agent.id} player true")
    assert result.ok
    assert agent.is_player is True


def test_session_snapshot_includes_is_player():
    session = Session.from_default()
    session.run_command(
        'create-agent name "Tester" personality "x" player true at 0,0'
    )
    agent = next(
        item for item in session.snapshot()["agents"] if item["name"] == "Tester"
    )
    assert agent["is_player"] is True


def test_manual_compound_turn_moves_player_agent():
    area = create_initial_area()
    agent, _ = create_agent_from_args(
        area,
        'name "Tester" personality "x" player true move-speed 1 at 0,0',
    )
    assert agent is not None
    agent.position = (0, 0)

    session = Session.from_default()
    session.areas["room"] = area
    session.agent_area[agent.id] = "room"
    session.active_agent_id = agent.id

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="Path test.",
            move="3,1",
            action="none",
        ),
        agent_id=agent.id,
    )
    assert result.ok
    assert agent.position != (0, 0)
