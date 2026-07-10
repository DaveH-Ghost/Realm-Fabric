"""Interact pathing overwrites compound move (V0.6.0b)."""

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.simulation import execute_nav_phase, run_compound_turn


def test_nav_phase_skips_move_when_interact():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (0, 0)

    steps = execute_nav_phase(
        agent,
        area,
        AgentCompoundTurn(
            reasoning="kick",
            move="3,3",
            action="interact",
            target="obj_ball_01",
            verb="kick",
        ),
    )

    assert steps == []
    assert agent.position == (0, 0)


def test_interact_paths_then_kicks_ball():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 3

    record = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="kick from afar",
            move="0,0",
            action="interact",
            target="obj_ball_01",
            verb="kick",
        ),
    )

    assert record.ok
    assert agent.position == (1, 1)
    move_steps = [step for step in record.record.steps if step.kind == "move"]
    interact_steps = [step for step in record.record.steps if step.kind == "interact"]
    assert len(move_steps) == 1
    assert len(interact_steps) == 1
    assert "Ceramic Ball" in move_steps[0].result
    assert move_steps[0].passive_result
    assert "kick" in record.message.lower() or "ball" in record.message.lower()
    assert "Ceramic Ball" in record.record.result
