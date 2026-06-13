"""
test_compound_turn.py

V0.2.5: compound agent turns (single LLM call schema, sequential execution).
"""

from src.compound_stepper import parse_compound_step_arg
from src.llm.prompt import build_compound_prompt
from src.llm.schemas import AgentCompoundTurn
from src.perception import build_passive_vision
from src.simulation import (
    execute_action_phase,
    execute_nav_phase,
    next_turn_number_for_agent,
    run_compound_turn,
)
from src.area import create_initial_area
from src.area_edit import create_agent_from_args


def compound(
    *,
    move_target=None,
    look_target=None,
    turn_action="none",
    content=None,
    reasoning="reasoning",
    confidence=None,
    emotion=None,
) -> AgentCompoundTurn:
    return AgentCompoundTurn(
        reasoning=reasoning,
        move_target=move_target,
        look_target=look_target,
        turn_action=turn_action,
        content=content,
        confidence=confidence,
        emotion=emotion,
    )


def test_nav_null_action_speak_only():
    area = create_initial_area()
    agent = area.get_agent()
    start = agent.position

    record = run_compound_turn(
        agent,
        area,
        compound(turn_action="speak", content="Hello."),
        turn_number=1,
    )

    assert agent.position == start
    assert len(record.steps) == 1
    assert record.steps[0].kind == "speak"
    assert agent.memory.turn_count == 1


def test_move_look_speak_in_order():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent,
        area,
        compound(
            move_target="2,3",
            look_target="obj_ball_01",
            turn_action="speak",
            content="Hi.",
        ),
        turn_number=1,
    )

    assert agent.position == (2, 3)
    kinds = [s.kind for s in record.steps]
    assert kinds == ["move", "look", "speak"]
    assert agent.memory.has_looked_at("obj_ball_01")


def test_post_move_look_on_same_tile_as_object():
    """After moving onto the ball's tile, look succeeds with full detail."""
    area = create_initial_area()
    agent = area.get_agent()

    execute_nav_phase(agent, area, compound(move_target="2,2"))
    steps = execute_action_phase(
        agent, area, compound(look_target="obj_ball_01", turn_action="none")
    )
    assert steps[0].result.startswith("You looked at")
    assert "scuffs" in steps[0].result


def test_invalid_look_after_valid_move_keeps_move():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent,
        area,
        compound(
            move_target="2,3",
            look_target="obj_missing_99",
            turn_action="none",
        ),
        turn_number=1,
    )

    assert agent.position == (2, 3)
    assert record.steps[0].kind == "move"
    assert "don't see" in record.steps[1].result.lower()


def test_turn_record_has_structured_steps():
    area = create_initial_area()
    agent = area.get_agent()

    record = run_compound_turn(
        agent,
        area,
        compound(
            move_target="2,3",
            look_target="obj_ball_01",
            turn_action="speak",
            content="Hi.",
            reasoning="full turn",
        ),
        turn_number=1,
    )

    assert record.reasoning == "full turn"
    assert len(record.steps) == 3
    assert "\n" in record.result


def test_passive_result_look_wins_over_move():
    area = create_initial_area()
    agent = area.get_agent()

    run_compound_turn(
        agent,
        area,
        compound(move_target="2,2", look_target="obj_ball_01", turn_action="none"),
        turn_number=1,
    )

    assert "examines" in agent.passive_result
    assert "moves to" not in agent.passive_result


def test_passive_result_speak_wins_over_move_and_look():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")
    goblin.position = (1, 1)

    run_compound_turn(
        goblin,
        area,
        compound(
            move_target="2,3",
            look_target="obj_ball_01",
            turn_action="speak",
            content="Hi.",
        ),
        next_turn_number_for_agent(goblin),
    )

    vision = build_passive_vision(explorer, area)
    assert "Goblin (agent_goblin_01), (2, 3)" in vision
    assert 'Goblin says: "Hi."' not in vision
    assert "moves to" not in vision
    assert "examines" not in vision


def test_step_compound_parser():
    parsed = parse_compound_step_arg('2,3 look obj_ball_01 speak Hello.')
    assert parsed.turn.move_target == "2,3"
    assert parsed.turn.look_target == "obj_ball_01"
    assert parsed.turn.content == "Hello."
    assert parsed.turn.turn_action == "speak"

    stay = parse_compound_step_arg("- look obj_ball_01")
    assert stay.turn.move_target is None

    interact = parse_compound_step_arg("2,3 interact obj_cookie_01 eat")
    assert interact.turn.move_target == "2,3"
    assert interact.turn.turn_action == "interact"
    assert interact.turn.target == "obj_cookie_01"
    assert interact.turn.action_name == "eat"


def test_compound_prompt_includes_turn_fields():
    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area)
    assert "compound turn" in prompt.lower()
    assert "move_target" in prompt
    assert "turn_action" in prompt
    assert "look_target" in prompt
    assert "Memory:" in prompt
