"""Interact pathing records a move step when the agent changes tiles."""

from src.area import create_initial_area
from src.llm.schemas import AgentCompoundTurn
from src.session import Session


def test_interact_path_move_appears_in_turn_memory_result():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 2

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="Path to kick.",
            action="interact",
            target="obj_ball_01",
            verb="kick",
        ),
    )

    assert result.ok
    assert result.record is not None
    move_lines = [
        step.result
        for step in result.record.steps
        if step.kind == "move"
    ]
    assert len(move_lines) == 1
    assert "Ceramic Ball" in move_lines[0]
    assert "Ceramic Ball" in result.record.result


def test_interact_in_range_does_not_add_move_step():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.position = (1, 1)
    agent.move_speed = 1

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="Kick from here.",
            action="interact",
            target="obj_ball_01",
            verb="kick",
        ),
    )

    assert result.ok
    assert result.record is not None
    assert not any(step.kind == "move" for step in result.record.steps)
