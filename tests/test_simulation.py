"""
test_simulation.py

Compound turn simulation tests.
"""

from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.simulation import next_turn_number_for_agent, run_compound_turn
from campaign_rpg_engine.area import create_initial_area


def compound(**kwargs) -> AgentCompoundTurn:
    defaults = {"reasoning": "Test reasoning.", "action": "none"}
    defaults.update(kwargs)
    return AgentCompoundTurn(**defaults)


def test_compound_turn_creates_and_records_turn_record():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent,
        area,
        compound(look="obj_ball_01"),
        turn_number=1,
    )

    assert record.turn_number == 1
    assert record.steps[0].kind == "look"
    assert record.steps[0].target == "obj_ball_01"
    assert "You looked at" in record.result
    assert len(agent.memory.turns) == 1
    assert agent.last_action == "look"


def test_compound_preserves_reasoning():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent,
        area,
        compound(reasoning="Full turn thoughts.", look="obj_ball_01"),
        turn_number=42,
    )

    assert record.reasoning == "Full turn thoughts."


def test_compound_move_success():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent, area, compound(move="2,3"), turn_number=1
    )

    assert agent.position == (2, 3)
    assert record.result == "You moved to (2, 3)."
    assert agent.passive_result == "Explorer moves to (2, 3)."


def test_compound_move_failure_off_grid():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent, area, compound(move="5,5"), turn_number=1
    )

    assert agent.position == (1, 1)
    assert "outside the room" in record.result.lower()
    assert agent.last_action == "move"


def test_compound_look_marks_object():
    area = create_initial_area()
    agent = area.get_agent()
    assert not agent.memory.has_looked_at("obj_ball_01")

    run_compound_turn(
        agent,
        area,
        compound(look="obj_ball_01"),
        turn_number=1,
    )

    assert agent.memory.has_looked_at("obj_ball_01")


def test_compound_speak_records_text():
    area = create_initial_area()
    agent = area.get_agent()
    spoken = "This ball feels familiar."

    record = run_compound_turn(
        agent,
        area,
        compound(action="none", say=spoken),
        turn_number=1,
    )

    assert f'You said: "{spoken}"' in record.result
    assert agent.position == (1, 1)


def test_multiple_compound_turns_accumulate():
    area = create_initial_area()
    agent = area.get_agent()

    for i in range(5):
        run_compound_turn(
            agent,
            area,
            compound(move="2,1"),
            turn_number=i + 1,
        )

    assert len(agent.memory.turns) == 5
    assert agent.last_action == "move"


def test_build_compound_prompt_sections():
    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area, include_examples=True)

    assert "You are Explorer" in prompt
    assert "Passive Vision:" in prompt
    assert prompt.index("Passive Vision:") < prompt.index("Compound turn order")
    assert "compound turn" in prompt.lower()
    assert '"move"' in prompt
    assert '"action"' in prompt
    assert "Memory:" in prompt
    assert "Example 1: Move, look, and speak" in prompt
